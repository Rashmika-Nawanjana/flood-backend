from datetime import datetime, timezone
from typing import Any


def validate_payload(data: dict) -> bool:
    required_fields = [
        "device_id",
        "timestamp",
        "water_level_cm",
        "temperature",
        "pressure",
        "rainfall_intensity_mmh",
        "flow_velocity_ms",
        "device_status",
    ]
    if not all(key in data for key in required_fields):
        return False

    device_status = data.get("device_status")
    if not isinstance(device_status, dict):
        return False

    return all(key in device_status for key in ["battery_voltage", "signal_strength_dbm"])


def parse_timestamp(timestamp_value: Any) -> int:
    if isinstance(timestamp_value, (int, float)):
        return int(timestamp_value)

    if isinstance(timestamp_value, str):
        try:
            parsed = datetime.strptime(timestamp_value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            parsed = datetime.fromisoformat(timestamp_value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp() * 1e9)

    raise ValueError(f"Unsupported timestamp value: {timestamp_value!r}")


def parse_timestamp_to_datetime(timestamp_value: Any) -> datetime:
    ns_value = parse_timestamp(timestamp_value)
    return datetime.fromtimestamp(ns_value / 1e9, tz=timezone.utc)
