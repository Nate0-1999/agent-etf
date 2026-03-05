from __future__ import annotations

import os
from pathlib import Path

import psycopg


def main() -> None:
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL must be set before applying migrations")

    root = Path(__file__).resolve().parents[1]
    migrations_dir = root / "infra" / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))

    with psycopg.connect(dsn, autocommit=True) as connection:
        for migration in migration_files:
            connection.execute(migration.read_text(encoding="utf-8"))
            print(f"applied {migration.name}")


if __name__ == "__main__":
    main()
