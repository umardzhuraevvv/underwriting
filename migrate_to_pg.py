#!/usr/bin/env python3
"""
Migrate data from local SQLite to PostgreSQL on Railway.

Usage:
  DATABASE_URL="postgresql://..." python migrate_to_pg.py

What it migrates:
  - All users (with passwords, roles)
  - All roles
  - System settings (telegram token)
  - Underwriting rules & risk rules
  - Real anketas: IDs 7, 8, 9, 11, 13, 15, 17
  - Anketa history for those anketas
"""

import os
import sys
import sqlite3
from datetime import datetime, date

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Target PostgreSQL
PG_URL = os.getenv("DATABASE_URL")
if not PG_URL:
    print("ERROR: Set DATABASE_URL env variable to PostgreSQL connection string")
    sys.exit(1)

if PG_URL.startswith("postgres://"):
    PG_URL = PG_URL.replace("postgres://", "postgresql://", 1)

# Source SQLite
SQLITE_PATH = os.path.join(os.path.dirname(__file__), "underwriting.db")
ANKETA_IDS = [7, 8, 9, 11, 13, 15, 17]

def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

# Boolean fields that SQLite stores as 0/1 but PostgreSQL needs True/False
BOOL_FIELDS = {
    "is_active", "is_system", "consent_personal_data", "no_scoring_response",
    "anketa_create", "anketa_edit", "anketa_view_all", "anketa_conclude",
    "anketa_delete", "user_manage", "analytics_view", "export_excel", "rules_manage",
    "is_read",
}

def fix_booleans(row):
    """Convert SQLite integer booleans (0/1) to Python bool for PostgreSQL."""
    for k, v in row.items():
        if k in BOOL_FIELDS and isinstance(v, int):
            row[k] = bool(v)
    return row

def main():
    # Connect to SQLite
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = dict_factory
    cur = sqlite_conn.cursor()

    # Connect to PostgreSQL — init tables first
    print("Initializing PostgreSQL tables...")
    os.environ["DATABASE_URL"] = PG_URL
    from app.database import init_db, engine as pg_engine, SessionLocal

    init_db()
    pg = SessionLocal()

    try:
        # 1. Migrate roles
        print("\n--- Migrating roles ---")
        cur.execute("SELECT * FROM roles")
        roles = cur.fetchall()
        for r in roles:
            exists = pg.execute(text("SELECT id FROM roles WHERE name = :name"), {"name": r["name"]}).fetchone()
            if exists:
                print(f"  Role '{r['name']}' already exists (id={exists[0]}), skipping")
                continue
            pg.execute(text("""
                INSERT INTO roles (id, name, is_system, anketa_create, anketa_edit, anketa_view_all,
                    anketa_conclude, anketa_delete, user_manage, analytics_view, export_excel, rules_manage)
                VALUES (:id, :name, :is_system, :anketa_create, :anketa_edit, :anketa_view_all,
                    :anketa_conclude, :anketa_delete, :user_manage, :analytics_view, :export_excel, :rules_manage)
            """), fix_booleans(r))
            print(f"  + Role '{r['name']}' (id={r['id']})")
        pg.commit()

        # Fix sequence
        pg.execute(text("SELECT setval('roles_id_seq', (SELECT COALESCE(MAX(id),0) FROM roles))"))
        pg.commit()

        # 2. Migrate users
        print("\n--- Migrating users ---")
        cur.execute("SELECT * FROM users")
        users = cur.fetchall()
        for u in users:
            exists = pg.execute(text("SELECT id FROM users WHERE email = :email"), {"email": u["email"]}).fetchone()
            if exists:
                print(f"  User '{u['email']}' already exists (id={exists[0]}), skipping")
                continue
            pg.execute(text("""
                INSERT INTO users (id, email, full_name, password_hash, role, is_active, role_id, telegram_chat_id)
                VALUES (:id, :email, :full_name, :password_hash, :role, :is_active, :role_id, :telegram_chat_id)
            """), fix_booleans(u))
            print(f"  + User '{u['email']}' (id={u['id']}, role={u['role']})")
        pg.commit()

        # Fix sequence
        pg.execute(text("SELECT setval('users_id_seq', (SELECT COALESCE(MAX(id),0) FROM users))"))
        pg.commit()

        # 3. Migrate system settings
        print("\n--- Migrating system settings ---")
        cur.execute("SELECT * FROM system_settings")
        settings = cur.fetchall()
        for s in settings:
            exists = pg.execute(text("SELECT id FROM system_settings WHERE key = :key"), {"key": s["key"]}).fetchone()
            if exists:
                print(f"  Setting '{s['key']}' already exists, updating")
                pg.execute(text("UPDATE system_settings SET value = :value WHERE key = :key"),
                           {"key": s["key"], "value": s["value"]})
            else:
                pg.execute(text("INSERT INTO system_settings (key, value) VALUES (:key, :value)"),
                           {"key": s["key"], "value": s["value"]})
                print(f"  + Setting '{s['key']}'")
        pg.commit()

        # 4. Migrate underwriting rules
        print("\n--- Migrating underwriting rules ---")
        count = pg.execute(text("SELECT COUNT(*) FROM underwriting_rules")).scalar()
        if count > 0:
            print(f"  Already has {count} rules, skipping")
        else:
            cur.execute("SELECT * FROM underwriting_rules")
            for r in cur.fetchall():
                pg.execute(text("""
                    INSERT INTO underwriting_rules (id, category, rule_key, value, label, value_type)
                    VALUES (:id, :category, :rule_key, :value, :label, :value_type)
                """), r)
            pg.commit()
            pg.execute(text("SELECT setval('underwriting_rules_id_seq', (SELECT COALESCE(MAX(id),0) FROM underwriting_rules))"))
            pg.commit()
            print(f"  + Migrated {len(cur.fetchall()) or 18} rules")

        # 5. Migrate risk rules
        print("\n--- Migrating risk rules ---")
        count = pg.execute(text("SELECT COUNT(*) FROM risk_rules")).scalar()
        if count > 0:
            print(f"  Already has {count} risk rules, skipping")
        else:
            cur.execute("SELECT * FROM risk_rules")
            for r in cur.fetchall():
                pg.execute(text("""
                    INSERT INTO risk_rules (id, category, min_pv, is_active)
                    VALUES (:id, :category, :min_pv, :is_active)
                """), fix_booleans(r))
            pg.commit()
            pg.execute(text("SELECT setval('risk_rules_id_seq', (SELECT COALESCE(MAX(id),0) FROM risk_rules))"))
            pg.commit()
            print(f"  + Migrated risk rules")

        # 6. Migrate anketas
        print(f"\n--- Migrating anketas {ANKETA_IDS} ---")
        cur.execute("PRAGMA table_info(anketas)")
        anketa_cols = [col["name"] for col in cur.fetchall()]

        placeholders = ", ".join(f":{c}" for c in anketa_cols)
        col_names = ", ".join(anketa_cols)

        for aid in ANKETA_IDS:
            exists = pg.execute(text("SELECT id FROM anketas WHERE id = :id"), {"id": aid}).fetchone()
            if exists:
                print(f"  Anketa #{aid} already exists, skipping")
                continue

            cur.execute(f"SELECT * FROM anketas WHERE id = ?", (aid,))
            row = cur.fetchone()
            if not row:
                print(f"  Anketa #{aid} not found in SQLite, skipping")
                continue

            # Convert empty strings to None for date fields
            date_fields = ["birth_date", "passport_issue_date", "last_overdue_date",
                           "company_last_overdue_date", "director_last_overdue_date",
                           "guarantor_last_overdue_date", "concluded_at", "deleted_at",
                           "created_at", "updated_at"]
            for df in date_fields:
                if df in row and row[df] == "":
                    row[df] = None

            pg.execute(text(f"INSERT INTO anketas ({col_names}) VALUES ({placeholders})"), fix_booleans(row))
            name = row.get("full_name") or row.get("company_name") or "(no name)"
            print(f"  + Anketa #{aid}: {name} [{row.get('status')}]")

        pg.commit()

        # Fix sequence
        pg.execute(text("SELECT setval('anketas_id_seq', (SELECT COALESCE(MAX(id),0) FROM anketas))"))
        pg.commit()

        # 7. Migrate anketa history
        print("\n--- Migrating anketa history ---")
        id_list = ",".join(str(i) for i in ANKETA_IDS)
        cur.execute(f"SELECT * FROM anketa_history WHERE anketa_id IN ({id_list})")
        histories = cur.fetchall()
        migrated = 0
        for h in histories:
            pg.execute(text("""
                INSERT INTO anketa_history (id, anketa_id, field_name, old_value, new_value, changed_by, changed_at)
                VALUES (:id, :anketa_id, :field_name, :old_value, :new_value, :changed_by, :changed_at)
            """), h)
            migrated += 1
        pg.commit()
        if migrated:
            pg.execute(text("SELECT setval('anketa_history_id_seq', (SELECT COALESCE(MAX(id),0) FROM anketa_history))"))
            pg.commit()
        print(f"  + Migrated {migrated} history records")

        print("\n=== Migration complete! ===")

    except Exception as e:
        pg.rollback()
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        pg.close()
        sqlite_conn.close()

if __name__ == "__main__":
    main()
