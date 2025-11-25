"""
Monitoring Service

Сервис для мониторинга здоровья и производительности бота.
Собирает метрики и выполняет health checks критичных компонентов.

Author: Architecture Improvement Phase 2
Date: 2024-11-24
"""

import logging
import time
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from config.settings import Settings
from bot.services.panel_api_service import PanelApiService


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class MonitoringService:
    """
    Service for monitoring bot health and performance.
    
    Features:
    - Health checks for critical components (DB, Redis, Panel API)
    - Performance metrics collection
    - Business metrics tracking
    - Alerting capabilities
    """
    
    def __init__(
        self,
        settings: Settings,
        panel_service: Optional[PanelApiService] = None,
    ):
        """
        Initialize MonitoringService.
        
        Args:
            settings: Application settings
            panel_service: Panel API service (optional)
        """
        self.settings = settings
        self.panel_service = panel_service
        
        # Metrics storage (in-memory)
        self._metrics: Dict[str, Any] = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_failed": 0,
            "avg_response_time_ms": 0.0,
            "last_health_check": None,
            "uptime_start": datetime.now(timezone.utc),
        }
        
        logging.info("MonitoringService initialized")
    
    # ==================== Health Checks ====================
    
    async def check_database_health(
        self,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Check database connectivity and performance.
        
        Args:
            session: Database session
            
        Returns:
            Dict with health status and details
        """
        start_time = time.time()
        
        try:
            # Simple query to check DB connectivity
            result = await session.execute(text("SELECT 1"))
            result.scalar()
            
            response_time_ms = (time.time() - start_time) * 1000
            
            # Determine status based on response time
            if response_time_ms < 100:
                status = HealthStatus.HEALTHY
            elif response_time_ms < 500:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY
            
            return {
                "component": "database",
                "status": status.value,
                "healthy": status == HealthStatus.HEALTHY,
                "response_time_ms": round(response_time_ms, 2),
                "message": f"Database responding in {response_time_ms:.2f}ms",
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
            
        except Exception as e:
            logging.error(f"Database health check failed: {e}")
            return {
                "component": "database",
                "status": HealthStatus.UNHEALTHY.value,
                "healthy": False,
                "response_time_ms": None,
                "message": f"Database check failed: {str(e)}",
                "error": str(e),
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
    
    async def check_redis_health(
        self,
    ) -> Dict[str, Any]:
        """
        Check Redis connectivity and performance.
        
        Returns:
            Dict with health status and details
        """
        if not self.settings.REDIS_ENABLED:
            return {
                "component": "redis",
                "status": HealthStatus.UNKNOWN.value,
                "healthy": None,
                "message": "Redis is disabled in settings",
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        
        start_time = time.time()
        
        try:
            from redis.asyncio import Redis
            
            redis = Redis(
                host=self.settings.REDIS_HOST,
                port=self.settings.REDIS_PORT,
                password=self.settings.REDIS_PASSWORD,
                socket_connect_timeout=5,
            )
            
            # Ping Redis
            await redis.ping()
            await redis.close()
            
            response_time_ms = (time.time() - start_time) * 1000
            
            # Determine status based on response time
            if response_time_ms < 50:
                status = HealthStatus.HEALTHY
            elif response_time_ms < 200:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY
            
            return {
                "component": "redis",
                "status": status.value,
                "healthy": status == HealthStatus.HEALTHY,
                "response_time_ms": round(response_time_ms, 2),
                "message": f"Redis responding in {response_time_ms:.2f}ms",
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
            
        except Exception as e:
            logging.error(f"Redis health check failed: {e}")
            return {
                "component": "redis",
                "status": HealthStatus.UNHEALTHY.value,
                "healthy": False,
                "response_time_ms": None,
                "message": f"Redis check failed: {str(e)}",
                "error": str(e),
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
    
    async def check_panel_api_health(
        self,
    ) -> Dict[str, Any]:
        """
        Check Panel API connectivity and performance.
        
        Returns:
            Dict with health status and details
        """
        if not self.panel_service:
            return {
                "component": "panel_api",
                "status": HealthStatus.UNKNOWN.value,
                "healthy": None,
                "message": "Panel service not configured",
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        
        start_time = time.time()
        
        try:
            # Try to get panel info or any lightweight endpoint
            # Assuming panel_service has a method to check health
            # For now, we'll use a simple approach
            result = await self.panel_service.get_users_by_filter(limit=1)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            # Determine status based on response time
            if response_time_ms < 500:
                status = HealthStatus.HEALTHY
            elif response_time_ms < 2000:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY
            
            return {
                "component": "panel_api",
                "status": status.value,
                "healthy": status == HealthStatus.HEALTHY,
                "response_time_ms": round(response_time_ms, 2),
                "message": f"Panel API responding in {response_time_ms:.2f}ms",
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
            
        except Exception as e:
            logging.error(f"Panel API health check failed: {e}")
            return {
                "component": "panel_api",
                "status": HealthStatus.UNHEALTHY.value,
                "healthy": False,
                "response_time_ms": None,
                "message": f"Panel API check failed: {str(e)}",
                "error": str(e),
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
    
    async def perform_full_health_check(
        self,
        session: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive health check of all components.
        
        Args:
            session: Database session (optional)
            
        Returns:
            Dict with overall health status and component details
        """
        logging.info("Performing full health check...")
        start_time = time.time()
        
        # Collect health checks
        checks = []
        
        # Database
        if session:
            db_health = await self.check_database_health(session)
            checks.append(db_health)
        else:
            checks.append({
                "component": "database",
                "status": HealthStatus.UNKNOWN.value,
                "healthy": None,
                "message": "Database session not provided",
            })
        
        # Redis
        redis_health = await self.check_redis_health()
        checks.append(redis_health)
        
        # Panel API
        panel_health = await self.check_panel_api_health()
        checks.append(panel_health)
        
        # Determine overall status
        unhealthy_count = sum(1 for c in checks if c.get("status") == HealthStatus.UNHEALTHY.value)
        degraded_count = sum(1 for c in checks if c.get("status") == HealthStatus.DEGRADED.value)
        
        if unhealthy_count > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        total_time_ms = (time.time() - start_time) * 1000
        
        # Update last check time
        self._metrics["last_health_check"] = datetime.now(timezone.utc)
        
        result = {
            "overall_status": overall_status.value,
            "healthy": overall_status == HealthStatus.HEALTHY,
            "total_check_time_ms": round(total_time_ms, 2),
            "components": checks,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": self.get_uptime_seconds(),
        }
        
        logging.info(f"Health check completed: {overall_status.value} in {total_time_ms:.2f}ms")
        return result
    
    # ==================== Metrics ====================
    
    def increment_request_counter(self, success: bool = True):
        """Increment request counters."""
        self._metrics["requests_total"] += 1
        if success:
            self._metrics["requests_success"] += 1
        else:
            self._metrics["requests_failed"] += 1
    
    def record_response_time(self, response_time_ms: float):
        """Record response time and update average."""
        current_avg = self._metrics["avg_response_time_ms"]
        total_requests = self._metrics["requests_total"]
        
        if total_requests > 0:
            # Calculate running average
            new_avg = (current_avg * (total_requests - 1) + response_time_ms) / total_requests
            self._metrics["avg_response_time_ms"] = round(new_avg, 2)
    
    def get_uptime_seconds(self) -> float:
        """Get bot uptime in seconds."""
        uptime = datetime.now(timezone.utc) - self._metrics["uptime_start"]
        return uptime.total_seconds()
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive metrics summary.
        
        Returns:
            Dict with all collected metrics
        """
        success_rate = 0.0
        if self._metrics["requests_total"] > 0:
            success_rate = (
                self._metrics["requests_success"] / self._metrics["requests_total"]
            ) * 100
        
        return {
            "requests": {
                "total": self._metrics["requests_total"],
                "success": self._metrics["requests_success"],
                "failed": self._metrics["requests_failed"],
                "success_rate_percent": round(success_rate, 2),
            },
            "performance": {
                "avg_response_time_ms": self._metrics["avg_response_time_ms"],
            },
            "system": {
                "uptime_seconds": round(self.get_uptime_seconds(), 2),
                "uptime_human": self._format_uptime(self.get_uptime_seconds()),
                "last_health_check": self._metrics["last_health_check"].isoformat()
                    if self._metrics["last_health_check"] else None,
            },
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }
    
    # ==================== Utility Methods ====================
    
    @staticmethod
    def _format_uptime(seconds: float) -> str:
        """Format uptime seconds to human-readable string."""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")
        
        return " ".join(parts)


# Global instance
_global_monitoring_service: Optional[MonitoringService] = None


def get_monitoring_service(
    settings: Settings,
    panel_service: Optional[PanelApiService] = None,
) -> MonitoringService:
    """
    Get or create global monitoring service instance.
    
    Args:
        settings: Application settings
        panel_service: Panel API service (optional)
        
    Returns:
        MonitoringService instance
    """
    global _global_monitoring_service
    if _global_monitoring_service is None:
        _global_monitoring_service = MonitoringService(settings, panel_service)
        logging.info("Global MonitoringService instance created")
    return _global_monitoring_service