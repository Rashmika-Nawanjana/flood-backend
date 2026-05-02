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

    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    allowed_origins: str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")

    keycloak_url: str = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
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