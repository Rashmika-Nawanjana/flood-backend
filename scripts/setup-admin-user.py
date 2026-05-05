#!/usr/bin/env python
"""
Admin User Setup Script for FloodSense LK

This script creates or updates an admin user in the database.
The user must exist in Clerk first, then this script syncs them to the database with admin role.

Usage:
    python scripts/setup-admin-user.py <clerk_id> <email> <full_name>

Example:
    python scripts/setup-admin-user.py user_2abc123xyz admin@flodsense.lk "Flood Admin"
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.pg import get_connection


def setup_admin_user(clerk_id: str, email: str, full_name: str) -> bool:
    """Create or update an admin user in the database."""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO users (clerk_id, email, full_name, role, is_active)
                VALUES (%s, %s, %s, 'admin', TRUE)
                ON CONFLICT (clerk_id) DO UPDATE
                SET email = EXCLUDED.email,
                    full_name = EXCLUDED.full_name,
                    role = 'admin',
                    is_active = TRUE
                """,
                (clerk_id, email, full_name),
            )
            conn.commit()
            print(f"✅ Admin user created/updated successfully!")
            print(f"   Clerk ID: {clerk_id}")
            print(f"   Email: {email}")
            print(f"   Name: {full_name}")
            print(f"   Role: admin")
            return True
    except Exception as e:
        print(f"❌ Failed to create admin user: {e}")
        return False


def main():
    if len(sys.argv) != 4:
        print("Usage: python setup-admin-user.py <clerk_id> <email> <full_name>")
        print("\nExample:")
        print('  python setup-admin-user.py user_2abc123xyz admin@flodsense.lk "Flood Admin"')
        sys.exit(1)

    clerk_id = sys.argv[1]
    email = sys.argv[2]
    full_name = sys.argv[3]

    print(f"Setting up admin user...")
    print(f"Clerk ID: {clerk_id}")
    print(f"Email: {email}")
    print(f"Name: {full_name}")
    print()

    success = setup_admin_user(clerk_id, email, full_name)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
