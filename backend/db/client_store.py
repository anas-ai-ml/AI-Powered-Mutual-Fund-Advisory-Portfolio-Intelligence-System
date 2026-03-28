import json
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional
from uuid import uuid4


DEFAULT_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://localhost:5432/mutual_fund_advisory",
)


class ClientStore:
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or DEFAULT_DATABASE_URL
        self._psycopg = None
        self._dict_row = None

    def _load_driver(self):
        if self._psycopg is not None:
            return
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - runtime dependency
            raise RuntimeError(
                "PostgreSQL support requires the 'psycopg' package. "
                "Install dependencies from requirements.txt and set DATABASE_URL."
            ) from exc
        self._psycopg = psycopg
        self._dict_row = dict_row

    @contextmanager
    def _connect(self) -> Iterator[Any]:
        self._load_driver()
        conn = self._psycopg.connect(self.database_url, row_factory=self._dict_row)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def ensure_schema(self) -> None:
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS clients (
            client_id TEXT PRIMARY KEY,
            advisor_id TEXT NOT NULL,
            name TEXT NOT NULL,
            age INTEGER,
            contact TEXT,
            pan_placeholder TEXT,
            source_channel TEXT,
            profile_data JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_clients_advisor_id ON clients (advisor_id);
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(create_table_sql)

    def list_clients(self, advisor_id: str) -> List[Dict[str, Any]]:
        self.ensure_schema()
        query = """
        SELECT client_id, advisor_id, name, age, contact, pan_placeholder,
               source_channel, created_at, updated_at
        FROM clients
        WHERE advisor_id = %s
        ORDER BY created_at DESC, name ASC
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (advisor_id,))
                return list(cur.fetchall())

    def get_client(self, client_id: str) -> Optional[Dict[str, Any]]:
        self.ensure_schema()
        query = """
        SELECT client_id, advisor_id, name, age, contact, pan_placeholder,
               source_channel, profile_data, created_at, updated_at
        FROM clients
        WHERE client_id = %s
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (client_id,))
                row = cur.fetchone()
                return self._normalize_row(row) if row else None

    def create_client(
        self,
        advisor_id: str,
        name: str,
        age: int,
        contact: str,
        pan_placeholder: str,
        source_channel: str,
    ) -> Dict[str, Any]:
        self.ensure_schema()
        client_id = str(uuid4())
        now = datetime.now().isoformat(timespec="seconds")
        insert_sql = """
        INSERT INTO clients (
            client_id, advisor_id, name, age, contact, pan_placeholder,
            source_channel, profile_data, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
        """
        profile_data = {
            "age": int(age),
            "contact": contact,
            "pan_placeholder": pan_placeholder,
            "source_channel": source_channel,
        }
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    insert_sql,
                    (
                        client_id,
                        advisor_id,
                        name,
                        int(age),
                        contact,
                        pan_placeholder,
                        source_channel,
                        json.dumps(profile_data),
                        now,
                        now,
                    ),
                )
        return self.get_client(client_id) or {}

    def save_client_profile(
        self,
        client_id: str,
        advisor_id: str,
        profile_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        self.ensure_schema()
        existing = self.get_client(client_id)
        if not existing:
            return None
        merged_profile = dict(existing.get("profile_data", {}))
        merged_profile.update(profile_data or {})
        update_sql = """
        UPDATE clients
        SET advisor_id = %s,
            age = %s,
            profile_data = %s::jsonb,
            updated_at = %s
        WHERE client_id = %s
        """
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    update_sql,
                    (
                        advisor_id,
                        int(merged_profile.get("age", existing.get("age") or 0)),
                        json.dumps(merged_profile),
                        now,
                        client_id,
                    ),
                )
        return self.get_client(client_id)

    @staticmethod
    def _normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
        if not row:
            return {}
        normalized = dict(row)
        profile_data = normalized.get("profile_data") or {}
        if isinstance(profile_data, str):
            try:
                profile_data = json.loads(profile_data)
            except json.JSONDecodeError:
                profile_data = {}
        normalized["profile_data"] = profile_data
        return normalized


def get_client_store(database_url: Optional[str] = None) -> ClientStore:
    return ClientStore(database_url=database_url)
