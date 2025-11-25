"""
Graceful Shutdown Handler

Обеспечивает корректное завершение работы бота при остановке:
- Ожидание завершения активных задач
- Корректное закрытие соединений (Redis, БД, HTTP)
- Сохранение состояния
- Предотвращение потери данных

Author: Architecture Improvement Phase 1
Date: 2024-11-24
"""

import asyncio
import logging
import signal
from typing import Callable, Optional, List
from datetime import datetime


class GracefulShutdownManager:
    """
    Менеджер корректного завершения работы бота.
    
    Отслеживает активные задачи, управляет процессом shutdown
    и обеспечивает корректное закрытие всех ресурсов.
    """
    
    def __init__(self, timeout: int = 30):
        """
        Initialize graceful shutdown manager.
        
        Args:
            timeout: Maximum time in seconds to wait for tasks to complete
        """
        self.timeout = timeout
        self.shutdown_event = asyncio.Event()
        self.shutdown_handlers: List[Callable] = []
        self.active_tasks: set = set()
        self.is_shutting_down = False
        
        # Statistics
        self.shutdown_initiated_at: Optional[datetime] = None
        self.shutdown_completed_at: Optional[datetime] = None
        
    def register_shutdown_handler(self, handler: Callable):
        """
        Register a shutdown handler to be called during shutdown.
        
        Handlers are called in registration order.
        
        Args:
            handler: Async function to call during shutdown
        """
        self.shutdown_handlers.append(handler)
        logging.debug(f"Graceful shutdown: Registered handler {handler.__name__}")
    
    def track_task(self, task: asyncio.Task):
        """
        Track an active task for graceful completion.
        
        Args:
            task: Task to track
        """
        self.active_tasks.add(task)
        task.add_done_callback(self.active_tasks.discard)
        logging.debug(f"Graceful shutdown: Tracking task {task.get_name()}")
    
    async def initiate_shutdown(self, signal_name: Optional[str] = None):
        """
        Initiate graceful shutdown process.
        
        Args:
            signal_name: Name of the signal that triggered shutdown (optional)
        """
        if self.is_shutting_down:
            logging.warning("Graceful shutdown: Already shutting down, ignoring duplicate request")
            return
        
        self.is_shutting_down = True
        self.shutdown_initiated_at = datetime.now()
        
        signal_info = f" (signal: {signal_name})" if signal_name else ""
        logging.info(f"Graceful shutdown: Initiating shutdown{signal_info}")
        
        # Set shutdown event
        self.shutdown_event.set()
        
        # Wait for active tasks with timeout
        if self.active_tasks:
            logging.info(f"Graceful shutdown: Waiting for {len(self.active_tasks)} active tasks to complete")
            try:
                await asyncio.wait_for(
                    self._wait_for_tasks(),
                    timeout=self.timeout
                )
                logging.info("Graceful shutdown: All active tasks completed successfully")
            except asyncio.TimeoutError:
                logging.warning(
                    f"Graceful shutdown: Timeout ({self.timeout}s) reached, "
                    f"{len(self.active_tasks)} tasks still active. Cancelling..."
                )
                await self._cancel_remaining_tasks()
        
        # Execute shutdown handlers
        await self._execute_shutdown_handlers()
        
        self.shutdown_completed_at = datetime.now()
        duration = (self.shutdown_completed_at - self.shutdown_initiated_at).total_seconds()
        logging.info(f"Graceful shutdown: Completed in {duration:.2f}s")
    
    async def _wait_for_tasks(self):
        """Wait for all active tasks to complete."""
        while self.active_tasks:
            # Wait for any task to complete
            done, pending = await asyncio.wait(
                self.active_tasks,
                return_when=asyncio.FIRST_COMPLETED,
                timeout=1.0
            )
            
            # Log progress every second
            if self.active_tasks:
                logging.debug(f"Graceful shutdown: {len(self.active_tasks)} tasks remaining")
    
    async def _cancel_remaining_tasks(self):
        """Cancel all remaining active tasks."""
        for task in list(self.active_tasks):
            if not task.done():
                logging.warning(f"Graceful shutdown: Cancelling task {task.get_name()}")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logging.debug(f"Graceful shutdown: Task {task.get_name()} cancelled")
                except Exception as e:
                    logging.error(
                        f"Graceful shutdown: Error cancelling task {task.get_name()}: {e}"
                    )
    
    async def _execute_shutdown_handlers(self):
        """Execute all registered shutdown handlers."""
        if not self.shutdown_handlers:
            logging.debug("Graceful shutdown: No shutdown handlers registered")
            return
        
        logging.info(f"Graceful shutdown: Executing {len(self.shutdown_handlers)} shutdown handlers")
        
        for i, handler in enumerate(self.shutdown_handlers, 1):
            handler_name = handler.__name__
            try:
                logging.debug(f"Graceful shutdown: Executing handler {i}/{len(self.shutdown_handlers)}: {handler_name}")
                await handler()
                logging.debug(f"Graceful shutdown: Handler {handler_name} completed successfully")
            except Exception as e:
                logging.error(
                    f"Graceful shutdown: Error in handler {handler_name}: {e}",
                    exc_info=True
                )
    
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self.shutdown_event.is_set()
    
    async def wait_for_shutdown(self):
        """Wait for shutdown signal."""
        await self.shutdown_event.wait()


class SignalHandler:
    """
    Signal handler for graceful shutdown on SIGINT/SIGTERM.
    """
    
    def __init__(self, shutdown_manager: GracefulShutdownManager):
        """
        Initialize signal handler.
        
        Args:
            shutdown_manager: GracefulShutdownManager instance
        """
        self.shutdown_manager = shutdown_manager
        self._original_handlers = {}
        
    def setup_signal_handlers(self):
        """
        Setup signal handlers for SIGINT and SIGTERM.
        
        Returns:
            bool: True if handlers were setup successfully
        """
        try:
            # Store original handlers
            self._original_handlers[signal.SIGINT] = signal.signal(
                signal.SIGINT, 
                self._signal_handler
            )
            self._original_handlers[signal.SIGTERM] = signal.signal(
                signal.SIGTERM, 
                self._signal_handler
            )
            
            logging.info("Graceful shutdown: Signal handlers registered (SIGINT, SIGTERM)")
            return True
            
        except Exception as e:
            logging.error(f"Graceful shutdown: Failed to setup signal handlers: {e}")
            return False
    
    def _signal_handler(self, sig, frame):
        """Handle signals by initiating graceful shutdown."""
        signal_name = signal.Signals(sig).name
        logging.info(f"Graceful shutdown: Received signal {signal_name}")
        
        # Create task for graceful shutdown
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(self.shutdown_manager.initiate_shutdown(signal_name))
        else:
            logging.warning("Graceful shutdown: Event loop not running, cannot initiate graceful shutdown")
    
    def restore_signal_handlers(self):
        """Restore original signal handlers."""
        for sig, handler in self._original_handlers.items():
            signal.signal(sig, handler)
        logging.debug("Graceful shutdown: Original signal handlers restored")


# Global instance
_global_shutdown_manager: Optional[GracefulShutdownManager] = None


def get_shutdown_manager(timeout: int = 30) -> GracefulShutdownManager:
    """
    Get or create global shutdown manager instance.
    
    Args:
        timeout: Shutdown timeout in seconds
        
    Returns:
        GracefulShutdownManager instance
    """
    global _global_shutdown_manager
    if _global_shutdown_manager is None:
        _global_shutdown_manager = GracefulShutdownManager(timeout=timeout)
        logging.info(f"Graceful shutdown: Manager initialized with timeout={timeout}s")
    return _global_shutdown_manager


async def shutdown_task_wrapper(coro, task_name: Optional[str] = None):
    """
    Wrapper for tasks that should be tracked during shutdown.
    
    Args:
        coro: Coroutine to execute
        task_name: Optional task name for logging
        
    Returns:
        Task result
    """
    manager = get_shutdown_manager()
    task = asyncio.current_task()
    
    if task and task_name:
        task.set_name(task_name)
    
    if task:
        manager.track_task(task)
    
    try:
        return await coro
    finally:
        # Task automatically removed from tracking on completion
        pass


def create_tracked_task(coro, name: Optional[str] = None) -> asyncio.Task:
    """
    Create a task that is tracked by shutdown manager.
    
    Args:
        coro: Coroutine to execute
        name: Task name for logging
        
    Returns:
        Created task
    """
    manager = get_shutdown_manager()
    task = asyncio.create_task(coro, name=name)
    manager.track_task(task)
    return task