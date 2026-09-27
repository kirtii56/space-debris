"""Database helpers. SQLAlchemy is used only to open connections; all queries are plain SQL."""

from functools import lru_cache

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import DATA_DIR, DATABASE_URL, ROOT_DIR

SCHEMA_FILE = ROOT_DIR / "sql" / "schema.sql"


@lru_cache(maxsize=None)
def get_engine(url: str = DATABASE_URL) -> Engine:
    if url.startswith("sqlite"):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    return create_engine(url, future=True)


def _statements(sql_text: str) -> list[str]:
    """Split a .sql file into single statements (dropping comment-only chunks)."""
    statements = []
    for chunk in sql_text.split(";"):
        code = "\n".join(ln for ln in chunk.splitlines() if not ln.strip().startswith("--")).strip()
        if code:
            statements.append(code)
    return statements


def init_schema(engine: Engine | None = None) -> None:
    engine = engine or get_engine()
    with engine.begin() as conn:
        for statement in _statements(SCHEMA_FILE.read_text()):
            conn.execute(text(statement))


def query_df(sql: str, params: dict | None = None, engine: Engine | None = None) -> pd.DataFrame:
    engine = engine or get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def execute(sql: str, params: dict | None = None, engine: Engine | None = None) -> None:
    engine = engine or get_engine()
    with engine.begin() as conn:
        conn.execute(text(sql), params or {})


def replace_rows(df: pd.DataFrame, table: str, delete_sql: str, params: dict | None = None,
                 engine: Engine | None = None) -> int:
    """Delete old rows and append new ones in a single transaction."""
    engine = engine or get_engine()
    with engine.begin() as conn:
        conn.execute(text(delete_sql), params or {})
        if not df.empty:
            df.to_sql(table, conn, if_exists="append", index=False, chunksize=1000)
    return len(df)
