"""Small database boundary supporting SQLite and Neon PostgreSQL.

SQLite remains the default. Set DATABASE_URL to use PostgreSQL; DB_PATH is
used only when DATABASE_URL is absent. The adapter intentionally keeps the
existing parameterized ``?`` SQL contract while translating the small SQLite
syntax subset used by this application.
"""
from __future__ import annotations

import os
import re
import sqlite3
from typing import Any, Iterable

try:
    import psycopg
    from psycopg.rows import tuple_row
except ImportError:  # SQLite-only local/test environments remain supported.
    psycopg = None  # type: ignore[assignment]
    tuple_row = None  # type: ignore[assignment]


class HybridRow:
    def __init__(self, columns: tuple[str, ...], values: tuple[Any, ...]):
        self._columns = columns
        self._values = values
        self._index = {name: index for index, name in enumerate(columns)}

    def __getitem__(self, key: int | str) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return self._values[self._index[key]]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def keys(self):
        return self._columns


def ident(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"unsafe identifier: {value!r}")
    return '"' + value.replace('"', '""') + '"'


class PostgresCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def _row(self, row):
        if row is None:
            return None
        columns = tuple(column.name for column in self._cursor.description or ())
        return HybridRow(columns, tuple(row))

    def fetchone(self):
        return self._row(self._cursor.fetchone())

    def fetchall(self):
        return [self._row(row) for row in self._cursor.fetchall()]

    def execute(self, query: str, params: Iterable[Any] = ()):
        self._cursor.execute(_translate_sql(query), tuple(params))
        return self

    def executemany(self, query: str, params: Iterable[Iterable[Any]]):
        self._cursor.executemany(_translate_sql(query), list(params))
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self._cursor.close()
        return False

    def __iter__(self):
        for row in self._cursor:
            yield self._row(row)

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return None


_PARAM_RE = re.compile(r"(?<!%)\?")


def _replace_parameters(query: str) -> str:
    # Application SQL uses ? placeholders and does not place them in literals.
    return _PARAM_RE.sub("%s", query)


def _translate_sql(query: str) -> str:
    query = query.strip()
    if query.upper().startswith("PRAGMA "):
        return "SELECT 1"
    query = re.sub(r"^BEGIN\s+IMMEDIATE\s*$", "BEGIN", query, flags=re.I)
    query = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", query, flags=re.I)
    query = re.sub(r"\bdatetime\s*\(\s*'now'\s*\)", "CURRENT_TIMESTAMP", query, flags=re.I)
    query = re.sub(r"\bdate\s*\(\s*'now'\s*\)", "CURRENT_DATE", query, flags=re.I)
    if re.match(r"^CREATE\s+TABLE\b", query, flags=re.I):
        query = re.sub(
            r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b",
            "BIGSERIAL PRIMARY KEY",
            query,
            flags=re.I,
        )
        query = re.sub(r"\bINTEGER\b", "BIGINT", query, flags=re.I)
        query = re.sub(r"\bBLOB\b", "BYTEA", query, flags=re.I)
        query = re.sub(r"\bREAL\b", "DOUBLE PRECISION", query, flags=re.I)
        query = re.sub(r"\bDATETIME\b", "TIMESTAMPTZ", query, flags=re.I)
        query = re.sub(r"\bAUTOINCREMENT\b", "", query, flags=re.I)
    query = re.sub(
        r"^(ALTER\s+TABLE\s+\S+\s+ADD\s+COLUMN)(?!\s+IF\s+NOT\s+EXISTS)\b",
        r"\1 IF NOT EXISTS",
        query,
        flags=re.I,
    )
    if query.upper().startswith("INSERT INTO ") and " ON CONFLICT " not in query.upper():
        if query.rstrip().endswith(")"):
            query = query.rstrip() + " ON CONFLICT DO NOTHING"
    # Psycopg treats every percent as placeholder syntax. Preserve the
    # application's literal LIKE patterns while leaving real placeholders
    # and already-escaped percent signs untouched.
    query = re.sub(r"(?<!%)%(?![sbt%])", "%%", query)
    return _replace_parameters(query)


class PostgresConnection:
    def __init__(self, url: str):
        if psycopg is None:
            raise RuntimeError('Postgres support requires psycopg[binary]')
        self._connection = psycopg.connect(url, row_factory=tuple_row)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self._connection.rollback()
        else:
            self._connection.commit()
        self.close()
        return False

    def execute(self, query: str, params: Iterable[Any] = ()) -> PostgresCursor:
        cursor = self._connection.cursor()
        cursor.execute(_translate_sql(query), tuple(params))
        return PostgresCursor(cursor)

    def cursor(self):
        return PostgresCursor(self._connection.cursor())

    def executemany(self, query: str, params: Iterable[Iterable[Any]]):
        cursor = self._connection.cursor()
        cursor.executemany(_translate_sql(query), list(params))
        return PostgresCursor(cursor)

    def executescript(self, script: str):
        for statement in re.split(r";\s*(?:\n|$)", script):
            statement = statement.strip()
            if statement:
                self.execute(statement)

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()

    def __getattr__(self, name):
        return getattr(self._connection, name)


def using_postgres() -> bool:
    return bool(os.getenv("DATABASE_URL", "").strip())


def repair_postgres_sequences(target: PostgresConnection) -> None:
    """Advance serial sequences after imports or interrupted first-start repairs."""
    rows = target.execute(
        """SELECT table_name, column_name
           FROM information_schema.columns
           WHERE table_schema = 'public' AND column_default LIKE 'nextval(%%'"""
    ).fetchall()
    for row in rows:
        table, column = str(row[0]), str(row[1])
        target.execute(
            """SELECT setval(
                pg_get_serial_sequence(%s, %s),
                COALESCE((SELECT MAX({column}) FROM {table}), 1),
                EXISTS (SELECT 1 FROM {table})
            )""".format(column=ident(column), table=ident(table)),
            (table, column),
        )


def connect(path: str | None = None):
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return PostgresConnection(url)
    connection = sqlite3.connect(path or os.getenv("DB_PATH", "telescout.db"), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def driver_name() -> str:
    return "postgres" if using_postgres() else "sqlite"


def bootstrap_postgres_from_sqlite(sqlite_path: str) -> bool:
    """Copy an existing SQLite volume once when DATABASE_URL is first enabled."""
    if not using_postgres() or not os.path.exists(sqlite_path):
        return False
    source = sqlite3.connect(sqlite_path)
    source.row_factory = sqlite3.Row
    target = PostgresConnection(os.environ["DATABASE_URL"])
    try:
        target.execute("CREATE TABLE IF NOT EXISTS _greyai_sqlite_bootstrap (id INTEGER PRIMARY KEY, completed_at TEXT NOT NULL)")
        if target.execute("SELECT id FROM _greyai_sqlite_bootstrap WHERE id = 1").fetchone():
            repair_postgres_sequences(target)
            target.commit()
            return False
        tables = source.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL ORDER BY name").fetchall()
        indexes = source.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        identity_columns: list[tuple[str, str]] = []
        for table, create_sql in tables:
            body = re.sub(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", "BIGSERIAL PRIMARY KEY", create_sql.rstrip(';'), flags=re.I)
            body = re.sub(r"\bINTEGER\b", "BIGINT", body, flags=re.I)
            body = re.sub(r"\bBLOB\b", "BYTEA", body, flags=re.I)
            body = re.sub(r"\bREAL\b", "DOUBLE PRECISION", body, flags=re.I)
            body = re.sub(r"\bDATETIME\b", "TIMESTAMPTZ", body, flags=re.I)
            body = re.sub(r"\bAUTOINCREMENT\b", "", body, flags=re.I)
            body = re.sub(r"^CREATE TABLE(?: IF NOT EXISTS)?\s+[^\s(]+", f"CREATE TABLE IF NOT EXISTS {ident(table)}", body, flags=re.I)
            target.execute(body)
            for column in source.execute(f"PRAGMA table_info({ident(table)})").fetchall():
                if int(column[5] or 0) == 1 and re.search(r"\bAUTOINCREMENT\b", create_sql, flags=re.I):
                    identity_columns.append((table, column[1]))
        for _, index_sql in indexes:
            target.execute(index_sql)
        for table, _ in tables:
            columns = [row[1] for row in source.execute(f"PRAGMA table_info({ident(table)})")]
            if not columns:
                continue
            names = ", ".join(ident(column) for column in columns)
            placeholders = ", ".join("?" for _ in columns)
            rows = source.execute(f"SELECT {names} FROM {ident(table)}")
            target.executemany(f"INSERT INTO {ident(table)} ({names}) VALUES ({placeholders})", [tuple(row) for row in rows])
        for table, column in identity_columns:
            target.execute(
                """SELECT setval(
                    pg_get_serial_sequence(%s, %s),
                    COALESCE((SELECT MAX({column}) FROM {table}), 1),
                    EXISTS (SELECT 1 FROM {table})
                )""".format(column=ident(column), table=ident(table)),
                (table, column),
            )
        target.execute("INSERT INTO _greyai_sqlite_bootstrap (id, completed_at) VALUES (1, CURRENT_TIMESTAMP) ON CONFLICT DO NOTHING")
        repair_postgres_sequences(target)
        target.commit()
        return True
    finally:
        source.close()
        target.close()
