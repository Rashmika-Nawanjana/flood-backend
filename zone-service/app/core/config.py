import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Flood Zone Service")
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql://admin:admin@localhost:5432/flooddb"
    )
    influxdb_url: str = os.getenv("INFLUXDB_URL", "http://localhost:8086")
    influxdb_token: str = os.getenv("INFLUXDB_TOKEN", "")
    influxdb_org: str = os.getenv("INFLUXDB_ORG", "flood")
    influxdb_bucket: str = os.getenv("INFLUXDB_BUCKET", "telemetry")


settings = Settings()
