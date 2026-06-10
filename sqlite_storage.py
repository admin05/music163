import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class SQLiteStorage:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        if not self.db_path.is_absolute():
            self.db_path = Path(__file__).resolve().parent / self.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    task_key TEXT PRIMARY KEY,
                    phone TEXT NOT NULL,
                    password TEXT NOT NULL,
                    uid TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    uid TEXT PRIMARY KEY,
                    cookie TEXT NOT NULL,
                    user_data TEXT,
                    expires_at INTEGER,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS kv (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def ping(self) -> bool:
        with self._connect() as conn:
            conn.execute("SELECT 1")
        return True

    def bootstrap_accounts_from_env(self) -> int:
        count = 0
        raw_accounts = os.getenv("NETEASE_ACCOUNTS", "").strip()
        if raw_accounts:
            accounts = json.loads(raw_accounts)
            if isinstance(accounts, dict):
                accounts = [
                    {"task_key": key, **value}
                    for key, value in accounts.items()
                    if isinstance(value, dict)
                ]
            if not isinstance(accounts, list):
                raise ValueError("NETEASE_ACCOUNTS 必须是 JSON 数组或对象")

            for index, account in enumerate(accounts, start=1):
                if not isinstance(account, dict):
                    continue
                phone = account.get("phone")
                password = account.get("password")
                if not phone or not password:
                    continue
                task_key = str(account.get("task_key") or account.get("key") or f"task{index}")
                uid = account.get("uid")
                self.upsert_account(task_key, str(phone), str(password), str(uid) if uid else None)
                count += 1

        phone = os.getenv("NETEASE_PHONE", "").strip()
        password = os.getenv("NETEASE_PASSWORD", "").strip()
        if phone and password:
            task_key = os.getenv("NETEASE_TASK_KEY", "task1").strip() or "task1"
            uid = os.getenv("NETEASE_UID", "").strip() or None
            self.upsert_account(task_key, phone, password, uid)
            count += 1

        return count

    def upsert_account(self, task_key: str, phone: str, password: str, uid: str | None = None) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO accounts (task_key, phone, password, uid, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(task_key) DO UPDATE SET
                    phone=excluded.phone,
                    password=excluded.password,
                    uid=COALESCE(excluded.uid, accounts.uid),
                    enabled=1,
                    updated_at=excluded.updated_at
                """,
                (task_key, phone, password, uid, now, now),
            )

    def update_account_uid(self, task_key: str, uid: str | int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE accounts SET uid=?, updated_at=? WHERE task_key=?",
                (str(uid), _now(), task_key),
            )

    def list_accounts(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT task_key, phone, password, uid
                FROM accounts
                WHERE enabled=1
                ORDER BY task_key
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def save_session(self, uid: str | int, cookie: str, user_data: Any = None, ttl_days: int = 30) -> None:
        expires_at = int(time.time()) + ttl_days * 86400 if ttl_days else None
        value = json.dumps(user_data or {}, ensure_ascii=False)
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (uid, cookie, user_data, expires_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(uid) DO UPDATE SET
                    cookie=excluded.cookie,
                    user_data=excluded.user_data,
                    expires_at=excluded.expires_at,
                    updated_at=excluded.updated_at
                """,
                (str(uid), cookie, value, expires_at, now),
            )

    def update_cookie(self, uid: str | int, cookie: str, ttl_days: int = 30) -> None:
        expires_at = int(time.time()) + ttl_days * 86400 if ttl_days else None
        now = _now()
        with self._connect() as conn:
            row = conn.execute("SELECT uid FROM sessions WHERE uid=?", (str(uid),)).fetchone()
            if row:
                conn.execute(
                    "UPDATE sessions SET cookie=?, expires_at=?, updated_at=? WHERE uid=?",
                    (cookie, expires_at, now, str(uid)),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO sessions (uid, cookie, user_data, expires_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (str(uid), cookie, "{}", expires_at, now),
                )

    def get_session_cookie(self, uid: str | int) -> str | None:
        now_ts = int(time.time())
        with self._connect() as conn:
            row = conn.execute(
                "SELECT cookie, expires_at FROM sessions WHERE uid=?",
                (str(uid),),
            ).fetchone()
            if not row:
                return None
            expires_at = row["expires_at"]
            if expires_at and int(expires_at) <= now_ts:
                conn.execute("DELETE FROM sessions WHERE uid=?", (str(uid),))
                return None
            return row["cookie"]

    def delete_session(self, uid: str | int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE uid=?", (str(uid),))

    def get_value(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def set_value(self, key: str, value: str) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO kv (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=excluded.updated_at
                """,
                (key, value, now),
            )

    def get_json(self, key: str, default: Any = None) -> Any:
        value = self.get_value(key)
        if value is None:
            return default
        return json.loads(value)

    def set_json(self, key: str, value: Any) -> None:
        self.set_value(key, json.dumps(value, ensure_ascii=False))
