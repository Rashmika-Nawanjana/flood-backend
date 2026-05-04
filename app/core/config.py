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

    # NEW: Port values with safe fallbacks
    api_port: str = os.getenv("API_PORT", "8000")
    keycloak_port: str = os.getenv("KEYCLOAK_PORT", "8080")
    postgres_port: str = os.getenv("POSTGRES_PORT", "5432")
    influxdb_port: str = os.getenv("INFLUXDB_PORT", "8086")

    # CHANGED: Frontend is fixed by team convention for Keycloak redirect
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:14000")
    allowed_origins: str = os.getenv("ALLOWED_ORIGINS", frontend_url)

    # NEW: Backend URL is derived from API_PORT if BACKEND_URL is missing
    backend_url: str = os.getenv("BACKEND_URL", f"http://localhost:{api_port}")

    # CHANGED: Keycloak URL is derived from KEYCLOAK_PORT if KEYCLOAK_URL is missing
    keycloak_url: str = os.getenv("KEYCLOAK_URL", f"http://localhost:{keycloak_port}")

    # CHANGED: Database URL is derived from POSTGRES_PORT if DATABASE_URL is missing
    database_url: str = os.getenv(
        "DATABASE_URL",
        f"postgresql+psycopg://admin:admin@localhost:{postgres_port}/flooddb",
    )

    # CHANGED: InfluxDB URL is derived from INFLUXDB_PORT if INFLUXDB_URL is missing
    influxdb_url: str = os.getenv(
        "INFLUXDB_URL",
        f"http://localhost:{influxdb_port}",
    )

    keycloak_realm: str = os.getenv("KEYCLOAK_REALM", "flood-management")
    keycloak_client_id: str = os.getenv("KEYCLOAK_CLIENT_ID", "flood-frontend")

    @property
    def keycloak_issuer(self) -> str:
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}"

    @property
    def keycloak_jwks_url(self) -> str:
        return f"{self.keycloak_issuer}/protocol/openid-connect/certs"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]


settings = Settings()
