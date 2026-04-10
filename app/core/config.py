import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Flood Backend")
    app_env: str = os.getenv("APP_ENV", "development")
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql://admin:admin@localhost:5432/flooddb"
    )
    influxdb_url: str = os.getenv("INFLUXDB_URL", "http://localhost:8086")


settings = Settings()
