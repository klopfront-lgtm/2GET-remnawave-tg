"""
Quick check if Alembic is installed and ready to use
"""
import sys

try:
    import alembic
    print(f"✓ Alembic {alembic.__version__} установлен")
    
    import sqlalchemy
    print(f"✓ SQLAlchemy {sqlalchemy.__version__} установлен")
    
    import asyncpg
    print(f"✓ asyncpg установлен")
    
    print("\nВсе зависимости установлены! Можно применять миграции.")
    sys.exit(0)
    
except ImportError as e:
    print(f"✗ Отсутствует зависимость: {e}")
    print("\nУстановите зависимости: pip install -r requirements.txt")
    sys.exit(1)