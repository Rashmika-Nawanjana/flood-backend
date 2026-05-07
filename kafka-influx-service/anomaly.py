import logging
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Statistical anomaly detector using Z-score method."""

    def __init__(self, history_size: int = 10, z_threshold: float = 3.0):
        self.history_size = history_size
        self.z_threshold = z_threshold
        self.recent_readings: Dict[str, List[float]] = {}

    def is_anomaly(self, sensor_id: str, new_value: float) -> tuple[bool, float | None]:
        if sensor_id not in self.recent_readings:
            self.recent_readings[sensor_id] = []

        history = self.recent_readings[sensor_id]

        if len(history) < 5:
            history.append(new_value)
            return False, None

        mean = np.mean(history)
        std_dev = np.std(history)
        z_score = abs(new_value - mean) / (std_dev + 1e-5)

        logger.debug(
            f"Sensor {sensor_id}: value={new_value:.1f}cm, mean={mean:.1f}, "
            f"std={std_dev:.2f}, z-score={z_score:.2f}"
        )

        if z_score > self.z_threshold:
            logger.warning(
                f"🚨 ANOMALY: Sensor {sensor_id} reading {new_value}cm "
                f"(z-score: {z_score:.2f})"
            )
            return True, z_score

        history.append(new_value)
        if len(history) > self.history_size:
            history.pop(0)

        return False, z_score
