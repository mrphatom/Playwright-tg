#!/usr/bin/env python3
"""Copy a GreyAI SQLite backup into PostgreSQL without dropping destination data."""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
from pathlib import Path

try:
    import psycopg
    from psycopg import sql
except ImportError as exc:  # pragma: no cover
    raise SystemExit('Install with: pip install "psycopg[binary]"') from exc


def ident(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"unsafe identifier: {value!r}")
    return '"' + value.replace('"', '""') + '"'


def translate_create(table: str, source_sql: str) -> str:
    body = source_sql.strip().rstrip(';')
    body = re.sub(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", "BIGSERIAL PRIMARY KEY", body, flags=re.I)
    body = re.sub(r"\bINTEGER\b", "BIGINT", body, flags=re.I)
    body = re.sub(r"\bBLOB\b", "BYTEA", body, flags=re.I)
    body = re.sub(r"\bREAL\b", "DOUBLE PRECISION", body, flags=re.I)
    body = re.sub(r"\bDATETIME\b", "TIMESTAMPTZ", body, flags=re.I)
    body = re.sub(r"\bCOLLATE\s+NOCASE\b", "", body, flags=re.I)
    body = re.sub(r"\s+WITHOUT\s+ROWID\b", "", body, flags=re.I)
    body = re.sub(r"^CREATE TABLE(?: IF NOT EXISTS)?\s+[^\s(]+", f"CREATE TABLE IF NOT EXISTS {ident(table)}", body, flags=re.I)
    return body


def objects(source: sqlite3.Connection):
    tables = source.execute("""SELECT name, sql FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL ORDER BY name""").fetchall()
    indexes = source.execute("""SELECT name, sql FROM sqlite_master
        WHERE type='index' AND sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY name""").fetchall()
    return tables, indexes


def migrate(sqlite_path: Path, database_url: str, dry_run: bool) -> None:
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite source does not exist: {sqlite_path}")
    source = sqlite3.connect(str(sqlite_path))
    tables, indexes = objects(source)
    print(f"source={sqlite_path} tables={len(tables)} indexes={len(indexes)}")
    if dry_run:
        for table, _ in tables:
            count = source.execute(f"SELECT COUNT(*) FROM {ident(table)}").fetchone()[0]
            print(f"{table}: {count} rows")
        return
    if not database_url:
        raise SystemExit("DATABASE_URL or --database-url is required")
    with psycopg.connect(database_url) as destination:
        with destination.cursor() as cursor:
            identity_columns = []
            for table, create_sql in tables:
                cursor.execute(translate_create(table, create_sql))
                for column in source.execute(f"PRAGMA table_info({ident(table)})").fetchall():
                    if int(column[5] or 0) == 1 and re.search(r"\bAUTOINCREMENT\b", create_sql, flags=re.I):
                        identity_columns.append((table, column[1]))
            for index, index_sql in indexes:
                try:
                    cursor.execute(index_sql)
                except psycopg.Error as exc:
                    raise RuntimeError(f"index migration failed for {index}: {exc}") from exc
            for table, _ in tables:
                columns = [row[1] for row in source.execute(f"PRAGMA table_info({ident(table)})")]
                if not columns:
                    continue
                cols = sql.SQL(", ").join(sql.Identifier(c) for c in columns)
                placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in columns)
                insert = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING").format(sql.Identifier(table), cols, placeholders)
                rows = source.execute(f"SELECT {', '.join(ident(c) for c in columns)} FROM {ident(table)}")
                cursor.executemany(insert, [tuple(row) for row in rows])
                source_count = source.execute(f"SELECT COUNT(*) FROM {ident(table)}").fetchone()[0]
                cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
                destination_count = cursor.fetchone()[0]
                if destination_count < source_count:
                    raise RuntimeError(f"row-count validation failed for {table}: source={source_count}, destination={destination_count}")
                print(f"copied {table}: source={source_count} destination={destination_count}")
            for table, column in identity_columns:
                cursor.execute(
                    sql.SQL("SELECT setval(pg_get_serial_sequence(%s, %s), COALESCE((SELECT MAX({}) FROM {}), 1), EXISTS (SELECT 1 FROM {}))").format(
                        sql.Identifier(column), sql.Identifier(table), sql.Identifier(table)
                    ),
                    (table, column),
                )
        destination.commit()
    source.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", default=os.getenv("SQLITE_DATABASE_PATH", "telescout.db"))
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    migrate(Path(args.sqlite), args.database_url or "", args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Sources:
# https://neon.com/docs/guides/python
# https://neon.com/docs/get-started/workflow-primer
