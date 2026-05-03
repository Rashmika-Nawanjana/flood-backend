from __future__ import annotations

import os
import subprocess
import sys
import time

from sqlalchemy import create_engine, text

from app.core.config import settings

MAX_DATABASE_WAIT_RETRIES = 30
DATABASE_WAIT_SECONDS = 2


def wait_for_database() -> None:
    last_error: Exception | None = None

    for attempt in range(1, MAX_DATABASE_WAIT_RETRIES + 1):
        engine = create_engine(settings.database_url, pool_pre_ping=True)

        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except Exception as exc:  # pragma: no cover - startup guard
            last_error = exc
            if attempt == MAX_DATABASE_WAIT_RETRIES:
                break
            print(
                f"Database is not ready yet, retrying ({attempt}/{MAX_DATABASE_WAIT_RETRIES})...",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(DATABASE_WAIT_SECONDS)
        finally:
            engine.dispose()

    raise RuntimeError("Database did not become ready in time") from last_error


def run_migrations() -> None:
    subprocess.run(["alembic", "upgrade", "head"], check=True)


def start_server() -> None:
    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "app.main:app",
            "--host",
            settings.app_host,
            "--port",
            str(settings.app_port),
        ],
    )


def main() -> None:
    wait_for_database()
    run_migrations()
    start_server()


if __name__ == "__main__":
    main()
