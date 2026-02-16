#!/usr/bin/env python3
"""
Migration runner script.

Usage:
    python run_migration.py [migration_file]

If no migration file is specified, runs all pending migrations in order.
"""

import os
import sys
from pathlib import Path

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import engine


def run_migration(migration_file: Path) -> bool:
    """
    Run a single SQL migration file.
    
    Returns True if successful, False otherwise.
    """
    print(f"Running migration: {migration_file.name}")
    
    try:
        sql = migration_file.read_text()
        
        with engine.connect() as conn:
            # Execute the migration
            conn.execute(text(sql))
            conn.commit()
        
        print(f"✓ Migration {migration_file.name} completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Migration {migration_file.name} failed: {e}")
        return False


def get_migrations_dir() -> Path:
    """Get the migrations directory path."""
    return Path(__file__).parent


def list_migrations() -> list[Path]:
    """List all SQL migration files in order."""
    migrations_dir = get_migrations_dir()
    migrations = sorted(migrations_dir.glob("*.sql"))
    return migrations


def main():
    """Run migrations."""
    if len(sys.argv) > 1:
        # Run specific migration
        migration_name = sys.argv[1]
        migration_path = get_migrations_dir() / migration_name
        
        if not migration_path.exists():
            print(f"Migration file not found: {migration_path}")
            sys.exit(1)
        
        success = run_migration(migration_path)
        sys.exit(0 if success else 1)
    
    else:
        # Run all migrations
        migrations = list_migrations()
        
        if not migrations:
            print("No migrations found.")
            return
        
        print(f"Found {len(migrations)} migration(s):")
        for m in migrations:
            print(f"  - {m.name}")
        print()
        
        failed = []
        for migration in migrations:
            if not run_migration(migration):
                failed.append(migration.name)
        
        print()
        if failed:
            print(f"✗ {len(failed)} migration(s) failed: {', '.join(failed)}")
            sys.exit(1)
        else:
            print(f"✓ All {len(migrations)} migration(s) completed successfully")


if __name__ == "__main__":
    main()
