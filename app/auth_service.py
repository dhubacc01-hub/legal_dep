from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

SESSION_COOKIE_NAME = "legal_dep_session"
SESSION_LIFETIME_DAYS = 14
PASSWORD_MIN_LENGTH = 8

ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_LAWYER = "lawyer"
USER_ROLES = (ROLE_OWNER, ROLE_ADMIN, ROLE_LAWYER)

DEFAULT_BOOTSTRAP_USERS = (
    {
        "username": "owner",
        "full_name": "Owner",
        "role": ROLE_OWNER,
        "temporary_password": "OwnerTemp2026!",
    },
    {
        "username": "admin",
        "full_name": "Admin",
        "role": ROLE_ADMIN,
        "temporary_password": "AdminTemp2026!",
    },
)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    effective_salt = salt or secrets.token_hex(16)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        effective_salt.encode("utf-8"),
        200_000,
    )
    return derived_key.hex(), effective_salt


def verify_password(password: str, password_hash: str, password_salt: str) -> bool:
    candidate_hash, _ = hash_password(password, password_salt)
    return hmac.compare_digest(candidate_hash, password_hash)


def create_session_token() -> str:
    return secrets.token_urlsafe(48)


def build_session_expiry() -> str:
    return (utc_now() + timedelta(days=SESSION_LIFETIME_DAYS)).isoformat()


def ensure_bootstrap_users(connection) -> None:
    timestamp = utc_now().isoformat()
    for item in DEFAULT_BOOTSTRAP_USERS:
        existing = connection.execute(
            "SELECT id FROM users WHERE lower(username) = lower(?)",
            (item["username"],),
        ).fetchone()
        if existing is not None:
            continue
        password_hash, password_salt = hash_password(item["temporary_password"])
        connection.execute(
            """
            INSERT INTO users (
                username,
                full_name,
                role,
                password_hash,
                password_salt,
                must_change_password,
                is_active,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, 1, 1, ?, ?)
            """,
            (
                item["username"],
                item["full_name"],
                item["role"],
                password_hash,
                password_salt,
                timestamp,
                timestamp,
            ),
        )


def serialize_user(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "username": str(row["username"]),
        "full_name": str(row["full_name"]),
        "role": str(row["role"]),
        "must_change_password": bool(row["must_change_password"]),
        "is_active": bool(row["is_active"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }

