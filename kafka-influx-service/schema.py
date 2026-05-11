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
        v = int(timestamp_value)
        # Detect unit by magnitude and normalise to nanoseconds:
        #   < 1e10  → seconds       (Unix epoch seconds, e.g. 1_778_510_369)
        #   < 1e13  → milliseconds  (normalize_payload fallback, e.g. 1_778_510_369_104)
        #   < 1e16  → microseconds
        #   >= 1e16 → nanoseconds   (already correct)
        if v < 10_000_000_000:          # seconds
            return v * 1_000_000_000
        elif v < 10_000_000_000_000:    # milliseconds
            return v * 1_000_000
        elif v < 10_000_000_000_000_000:  # microseconds
            return v * 1_000
        return v                         # nanoseconds

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
