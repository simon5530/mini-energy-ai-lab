"""Synthetic clear-sky PV profile for learning and tests."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PVConfig:
    max_power_kw: float
    sunrise_hour: float
    sunset_hour: float


class PVGenerator:
    def __init__(self, config: PVConfig) -> None:
        if config.max_power_kw < 0:
            raise ValueError("max_power_kw must be non-negative")
        if not 0 <= config.sunrise_hour < config.sunset_hour <= 24:
            raise ValueError("sunrise and sunset hours are invalid")
        self.config = config

    def power_kw(self, timestamp: datetime) -> float:
        hour = timestamp.hour + timestamp.minute / 60
        if hour <= self.config.sunrise_hour or hour >= self.config.sunset_hour:
            return 0.0
        daylight_fraction = (hour - self.config.sunrise_hour) / (
            self.config.sunset_hour - self.config.sunrise_hour
        )
        return self.config.max_power_kw * math.sin(math.pi * daylight_fraction)
