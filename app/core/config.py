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

    api_port: str = os.getenv("API_PORT", "8000")
    postgres_port: str = os.getenv("POSTGRES_PORT", "5432")
    influxdb_port: str = os.getenv("INFLUXDB_PORT", "8086")

    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    allowed_origins: str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")

    backend_url: str = os.getenv(
        "BACKEND_URL", f"http://localhost:{os.getenv('API_PORT', '8000')}"
    )

    database_url: str = os.getenv(
        "DATABASE_URL",
        f"postgresql+psycopg://admin:admin@localhost:{os.getenv('POSTGRES_PORT', '5432')}/flooddb",
    )

    influxdb_url: str = os.getenv(
        "INFLUXDB_URL",
        f"http://localhost:{os.getenv('INFLUXDB_PORT', '8086')}",
    )
    influxdb_token: str = os.getenv("INFLUXDB_TOKEN", "")
    influxdb_org: str = os.getenv("INFLUXDB_ORG", "flood")
    influxdb_bucket: str = os.getenv("INFLUXDB_BUCKET", "telemetry")

    # Clerk auth
    clerk_jwks_url: str = os.getenv("CLERK_JWKS_URL", "")
    clerk_issuer: str = os.getenv("CLERK_ISSUER", "")
    clerk_webhook_secret: str = os.getenv("CLERK_WEBHOOK_SECRET", "")

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]


settings = Settings()
