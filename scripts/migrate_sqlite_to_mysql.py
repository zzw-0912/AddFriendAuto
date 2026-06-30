import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, create_engine, func, select, text


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_URL = f"sqlite:///{(ROOT / 'server' / 'friendauto.db').as_posix()}"
APP_TABLES = [
    "admin_audit_logs",
    "admin_users",
    "contacts",
    "devices",
    "email_codes",
    "feedbacks",
    "memberships",
    "orders",
    "plans",
    "task_results",
    "tasks",
    "trial_quotas",
    "users",
]


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _normalize_value(value) for key, value in row.items()}


def _dedupe_task_results(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: set[tuple[Any, Any]] = set()
    deduped: list[dict[str, Any]] = []
    skipped = 0
    for row in rows:
        contact_id = row.get("contact_id")
        if contact_id is None:
            deduped.append(row)
            continue

        key = (row.get("task_id"), contact_id)
        if key in seen:
            skipped += 1
            continue

        seen.add(key)
        deduped.append(row)
    return deduped, skipped


def _require_tables(metadata: MetaData, tables: list[str], label: str) -> None:
    missing = [table for table in tables if table not in metadata.tables]
    if missing:
        names = ", ".join(missing)
        raise SystemExit(f"{label} is missing required tables: {names}")


def _table_count(connection, table) -> int:
    return int(connection.execute(select(func.count()).select_from(table)).scalar_one())


def _ensure_empty_target(connection, target_metadata: MetaData, truncate_target: bool) -> None:
    non_empty = [
        name
        for name in APP_TABLES
        if _table_count(connection, target_metadata.tables[name]) > 0
    ]
    if not non_empty:
        return

    if not truncate_target:
        names = ", ".join(non_empty)
        raise SystemExit(
            "Target MySQL database already has data. "
            f"Non-empty tables: {names}. Use --truncate-target only after taking a backup."
        )

    for name in reversed(APP_TABLES):
        connection.execute(target_metadata.tables[name].delete())


def _reset_mysql_auto_increment(connection, table_name: str, rows: list[dict[str, Any]]) -> None:
    ids = [row.get("id") for row in rows if isinstance(row.get("id"), int)]
    if not ids:
        return
    next_id = max(ids) + 1
    connection.execute(text(f"ALTER TABLE `{table_name}` AUTO_INCREMENT = {next_id}"))


def migrate(sqlite_url: str, mysql_url: str, truncate_target: bool, dry_run: bool) -> None:
    source_engine = create_engine(sqlite_url)
    target_engine = create_engine(mysql_url, pool_pre_ping=True, pool_recycle=3600)

    source_metadata = MetaData()
    target_metadata = MetaData()
    source_metadata.reflect(bind=source_engine)
    target_metadata.reflect(bind=target_engine)
    _require_tables(source_metadata, APP_TABLES, "SQLite source")
    _require_tables(target_metadata, APP_TABLES, "MySQL target")

    with source_engine.connect() as source_conn, target_engine.begin() as target_conn:
        if not dry_run:
            _ensure_empty_target(target_conn, target_metadata, truncate_target)

        for table_name in APP_TABLES:
            source_table = source_metadata.tables[table_name]
            target_table = target_metadata.tables[table_name]
            statement = select(source_table)
            if "id" in source_table.c:
                statement = statement.order_by(source_table.c.id)
            rows = [
                _normalize_row(dict(row))
                for row in source_conn.execute(statement).mappings()
            ]
            skipped = 0
            if table_name == "task_results":
                rows, skipped = _dedupe_task_results(rows)

            note = f", skipped {skipped} duplicate rows" if skipped else ""
            print(f"{table_name}: {len(rows)} rows{note}")
            if dry_run or not rows:
                continue

            target_conn.execute(target_table.insert(), rows)
            if target_engine.dialect.name == "mysql":
                _reset_mysql_auto_increment(target_conn, table_name, rows)

    if dry_run:
        print("Dry run completed. No data was inserted.")
    else:
        print("Migration completed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate FriendAuto data from SQLite to MySQL.")
    parser.add_argument("--sqlite-url", default=os.getenv("SQLITE_DATABASE_URL", DEFAULT_SQLITE_URL))
    parser.add_argument("--mysql-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--truncate-target", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.mysql_url:
        raise SystemExit("Set DATABASE_URL or pass --mysql-url.")
    if not args.mysql_url.startswith("mysql"):
        raise SystemExit("--mysql-url must be a MySQL SQLAlchemy URL.")

    migrate(args.sqlite_url, args.mysql_url, args.truncate_target, args.dry_run)


if __name__ == "__main__":
    main()
