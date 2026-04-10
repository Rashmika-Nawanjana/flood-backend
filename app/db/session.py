from app.core.config import settings


def get_database_url() -> str:
    """Placeholder function to keep DB wiring centralized."""
    return settings.database_url


def get_influxdb_url() -> str:
    """Placeholder function to keep InfluxDB wiring centralized."""
    return settings.influxdb_url
