"""Synthetic factory load profile for learning and tests."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class FactoryConfig:
    min_load_kw: float
    max_load_kw: float
    noise_kw: float


class FactoryLoadGenerator:
    def __init__(self, config: FactoryConfig, seed: int = 7) -> None:
        if config.min_load_kw < 0 or config.max_load_kw < config.min_load_kw:
            raise ValueError("factory load range is invalid")
        if config.noise_kw < 0:
            raise ValueError("noise_kw must be non-negative")
        self.config = config
        self._random = random.Random(seed)

    def power_kw(self, timestamp: datetime) -> float:
        hour = timestamp.hour + timestamp.minute / 60
        # The cosine reaches its maximum at noon and its minimum at midnight,
        # giving a smooth synthetic daily operating pattern without pretending
        # to be a measured or forecast industrial load profile.
        activity = (1 + math.cos((hour - 12) / 12 * math.pi)) / 2
        base = self.config.min_load_kw + activity * (
            self.config.max_load_kw - self.config.min_load_kw
        )
        # A private seeded generator makes variation reproducible in tests and
        # avoids changing Python's process-wide random state.
        noise = self._random.uniform(-self.config.noise_kw, self.config.noise_kw)
        return max(
            self.config.min_load_kw,
            min(base + noise, self.config.max_load_kw),
        )
