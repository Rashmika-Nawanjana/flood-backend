#!/usr/bin/env python
"""
Direct migration runner for creating users table.
Bypass Alembic to apply SQL migrations directly.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.pg import get_connection


def run_migration():
    """Load and execute the SQL migration file."""
    try:
        sql_file = Path(__file__).parent.parent / "migrations" / "sql" / "0003_users_table.sql"
        
        if not sql_file.exists():
            print(f"❌ Migration file not found: {sql_file}")
            return False
            
        with open(sql_file, 'r') as f:
            sql = f.read()
        
        with get_connection() as conn:
            conn.execute(sql)
            conn.commit()
            
        print("✅ Migration 0003_users_table applied successfully!")
        print("   - Created users table")
        print("   - Created indexes")
        print("   - Created timestamp trigger")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
