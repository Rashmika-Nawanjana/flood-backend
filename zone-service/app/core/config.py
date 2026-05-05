import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Flood Zone Service")
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql://admin:admin@localhost:5432/flooddb"
    )
    influxdb_url: str = _required_env("INFLUXDB_URL")
    influxdb_token: str = _required_env("INFLUXDB_TOKEN")
    influxdb_org: str = _required_env("INFLUXDB_ORG")
    influxdb_bucket: str = _required_env("INFLUXDB_BUCKET")


settings = Settings()
