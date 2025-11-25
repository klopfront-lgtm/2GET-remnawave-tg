"""
Автоматическое применение миграций с проверкой зависимостей
"""
import sys
import subprocess
import time
import io

# Устанавливаем кодировку UTF-8 для вывода
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_dependencies():
    """Проверка наличия необходимых зависимостей"""
    try:
        import alembic
        import sqlalchemy
        import asyncpg
        print("[OK] Все зависимости установлены")
        return True
    except ImportError as e:
        print(f"[ОШИБКА] Отсутствует зависимость: {e}")
        return False

def wait_for_dependencies(max_wait=300, check_interval=5):
    """Ожидание установки зависимостей"""
    print("Ожидание установки зависимостей...")
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        if check_dependencies():
            return True
        print(f"Ожидание... ({int(time.time() - start_time)}s)")
        time.sleep(check_interval)
    
    print("[ОШИБКА] Превышено время ожидания установки зависимостей")
    return False

def apply_migrations():
    """Применение миграций Alembic"""
    try:
        from alembic.config import Config
        from alembic import command
        
        print("\n" + "="*50)
        print("Применение миграций базы данных...")
        print("="*50 + "\n")
        
        # Создаем конфигурацию Alembic
        alembic_cfg = Config("alembic.ini")
        
        # Проверяем текущую версию БД
        print("Проверка текущей версии базы данных...")
        try:
            command.current(alembic_cfg)
        except Exception as e:
            print(f"Предупреждение: {e}")
        
        # Применяем миграции
        print("\nПрименение миграций до последней версии (head)...")
        command.upgrade(alembic_cfg, "head")
        
        print("\n" + "="*50)
        print("[УСПЕХ] Миграции успешно применены!")
        print("="*50)
        
        # Показываем текущую версию
        print("\nТекущая версия базы данных:")
        command.current(alembic_cfg, verbose=True)
        
        return True
        
    except Exception as e:
        print(f"\n[ОШИБКА] Ошибка при применении миграций: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Основная функция"""
    print("Автоматическое применение миграций базы данных")
    print("="*50 + "\n")
    
    # Сначала проверяем, установлены ли зависимости
    if not check_dependencies():
        print("\nЗависимости не установлены. Ожидание установки...")
        if not wait_for_dependencies():
            print("\n[ОШИБКА] Не удалось дождаться установки зависимостей")
            print("Пожалуйста, установите вручную: pip install -r requirements.txt")
            return 1
    
    # Применяем миграции
    if apply_migrations():
        print("\n[УСПЕХ] Готово! База данных обновлена.")
        return 0
    else:
        print("\n[ОШИБКА] Не удалось применить миграции")
        return 1

if __name__ == "__main__":
    sys.exit(main())