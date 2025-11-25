"""
Script to run Alembic migrations
Usage: python run_migrations.py
"""
import sys
from alembic.config import Config
from alembic import command

def run_migrations():
    """Run all pending Alembic migrations"""
    try:
        # Create Alembic configuration object
        alembic_cfg = Config("alembic.ini")
        
        print("Running Alembic migrations...")
        
        # Run migrations to the latest revision
        command.upgrade(alembic_cfg, "head")
        
        print("✓ Migrations applied successfully!")
        return 0
        
    except Exception as e:
        print(f"✗ Error applying migrations: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(run_migrations())