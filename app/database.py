from __future__ import annotations

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "legal_dep_fixed.db"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=MEMORY;")
    connection.execute("PRAGMA synchronous=NORMAL;")
    connection.execute("PRAGMA temp_store=MEMORY;")
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS debtors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Новый',
                parent_debtor_id INTEGER,
                client_name TEXT NOT NULL,
                contract_number TEXT NOT NULL,
                last_missed_payment_date TEXT NOT NULL,
                company TEXT NOT NULL,
                city TEXT NOT NULL,
                court TEXT NOT NULL,
                claim_sent INTEGER NOT NULL DEFAULT 0,
                claim_sent_date TEXT,
                debt_amount REAL NOT NULL DEFAULT 0,
                lawsuit_sent INTEGER NOT NULL DEFAULT 0,
                lawsuit_sent_date TEXT,
                lawsuit_accepted INTEGER NOT NULL DEFAULT 0,
                hearing_date TEXT,
                decision_exists INTEGER NOT NULL DEFAULT 0,
                decision TEXT,
                decision_payout REAL NOT NULL DEFAULT 0,
                received_amount REAL NOT NULL DEFAULT 0,
                comment TEXT,
                case_number TEXT,
                mobile_phone TEXT,
                home_phone TEXT,
                address TEXT,
                birth_date TEXT,
                contract_total_amount REAL,
                contract_advance_amount REAL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS import_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_filename TEXT NOT NULL,
                status TEXT NOT NULL,
                total_rows INTEGER NOT NULL DEFAULT 0,
                ok_rows INTEGER NOT NULL DEFAULT 0,
                needs_review_rows INTEGER NOT NULL DEFAULT 0,
                blocked_rows INTEGER NOT NULL DEFAULT 0,
                imported_rows INTEGER NOT NULL DEFAULT 0,
                notes TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS import_rows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL,
                row_index INTEGER NOT NULL,
                status TEXT NOT NULL,
                source_data_json TEXT NOT NULL,
                normalized_data_json TEXT NOT NULL,
                source_category TEXT,
                suggested_category TEXT,
                errors_json TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                debtor_id INTEGER,
                FOREIGN KEY(batch_id) REFERENCES import_batches(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_courts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                city TEXT NOT NULL,
                region TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                must_change_password INTEGER NOT NULL DEFAULT 1,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        ensure_column(connection, "debtors", "parent_debtor_id", "INTEGER")
        ensure_column(connection, "debtors", "imported_claim_sent_days", "INTEGER")
        ensure_column(connection, "debtors", "imported_debt_days", "INTEGER")
        ensure_column(connection, "debtors", "imported_penalty_amount", "REAL")
        ensure_column(connection, "debtors", "imported_state_duty_amount", "REAL")
        ensure_column(connection, "debtors", "imported_total_amount", "REAL")
        ensure_column(connection, "debtors", "imported_category_override", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(connection, "debtors", "mobile_phone", "TEXT")
        ensure_column(connection, "debtors", "home_phone", "TEXT")
        ensure_column(connection, "debtors", "address", "TEXT")
        ensure_column(connection, "debtors", "birth_date", "TEXT")
        ensure_column(connection, "debtors", "contract_total_amount", "REAL")
        ensure_column(connection, "debtors", "contract_advance_amount", "REAL")
        ensure_column(connection, "debtors", "country", "TEXT NOT NULL DEFAULT 'kz'")
        ensure_column(connection, "debtors", "lawsuit_installment_from", "TEXT")
        ensure_column(connection, "debtors", "lawsuit_installment_to", "TEXT")
        ensure_column(connection, "debtors", "lawsuit_monthly_payment_amount", "REAL")
        ensure_column(connection, "debtors", "lawsuit_first_period_paid_amount", "REAL")
        ensure_column(connection, "import_batches", "notes", "TEXT")
        ensure_column(connection, "import_rows", "debtor_id", "INTEGER")
        ensure_column(connection, "custom_courts", "country", "TEXT NOT NULL DEFAULT 'kz'")
        ensure_column(connection, "custom_courts", "created_at", "TEXT")
        ensure_column(connection, "users", "full_name", "TEXT NOT NULL DEFAULT ''")
        ensure_column(connection, "users", "role", "TEXT NOT NULL DEFAULT 'lawyer'")
        ensure_column(connection, "users", "password_hash", "TEXT NOT NULL DEFAULT ''")
        ensure_column(connection, "users", "password_salt", "TEXT NOT NULL DEFAULT ''")
        ensure_column(connection, "users", "must_change_password", "INTEGER NOT NULL DEFAULT 1")
        ensure_column(connection, "users", "is_active", "INTEGER NOT NULL DEFAULT 1")
        ensure_column(connection, "users", "created_at", "TEXT NOT NULL DEFAULT ''")
        ensure_column(connection, "users", "updated_at", "TEXT NOT NULL DEFAULT ''")
        ensure_column(connection, "user_sessions", "user_id", "INTEGER")
        ensure_column(connection, "user_sessions", "session_token", "TEXT")
        ensure_column(connection, "user_sessions", "created_at", "TEXT")
        ensure_column(connection, "user_sessions", "expires_at", "TEXT")
        ensure_custom_courts_schema(connection)
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_unique ON users(username)"
        )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_sessions_token_unique ON user_sessions(session_token)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id)"
        )


def ensure_column(
    connection: sqlite3.Connection, table_name: str, column_name: str, column_sql: str
) -> None:
    columns = {
        row["name"] for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")


def ensure_custom_courts_schema(connection: sqlite3.Connection) -> None:
    indexes = connection.execute("PRAGMA index_list(custom_courts)").fetchall()
    has_country_unique_index = False
    for index in indexes:
        index_name = index["name"]
        columns = [
            row["name"]
            for row in connection.execute(f"PRAGMA index_info({index_name})").fetchall()
        ]
        if columns == ["name", "country"] or columns == ["country", "name"]:
            has_country_unique_index = True
            break

    if has_country_unique_index:
        return

    connection.execute("ALTER TABLE custom_courts RENAME TO custom_courts_legacy")
    connection.execute(
        """
        CREATE TABLE custom_courts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            region TEXT NOT NULL,
            country TEXT NOT NULL DEFAULT 'kz',
            created_at TEXT NOT NULL,
            UNIQUE(name, country)
        )
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO custom_courts (id, name, city, region, country, created_at)
        SELECT
            id,
            name,
            city,
            region,
            COALESCE(NULLIF(country, ''), 'kz'),
            COALESCE(created_at, '')
        FROM custom_courts_legacy
        """
    )
    connection.execute("DROP TABLE custom_courts_legacy")
