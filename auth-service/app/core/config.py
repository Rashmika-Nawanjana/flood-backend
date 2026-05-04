import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    keycloak_url: str = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
    keycloak_realm: str = os.getenv("KEYCLOAK_REALM", "flood-management")
    keycloak_client_id: str = os.getenv("KEYCLOAK_CLIENT_ID", "flood-frontend")
    keycloak_client_secret: str = os.getenv("KEYCLOAK_CLIENT_SECRET", "")
    oidc_discovery_url: str = os.getenv(
        "OIDC_DISCOVERY_URL",
        "",
    )


settings = Settings()
