"""A deliberately small energy-balance model for a battery system."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BatteryConfig:
    capacity_kwh: float
    max_charge_power_kw: float
    max_discharge_power_kw: float
    min_soc_pct: float
    max_soc_pct: float
    initial_soc_pct: float
    charge_efficiency: float
    discharge_efficiency: float
    base_temperature_c: float = 27.0
    temperature_rise_at_full_power_c: float = 8.0

    def __post_init__(self) -> None:
        if self.capacity_kwh <= 0:
            raise ValueError("capacity_kwh must be positive")
        if self.max_charge_power_kw <= 0 or self.max_discharge_power_kw <= 0:
            raise ValueError("charge and discharge power limits must be positive")
        if not 0 <= self.min_soc_pct < self.max_soc_pct <= 100:
            raise ValueError("SOC limits must satisfy 0 <= min < max <= 100")
        if not self.min_soc_pct <= self.initial_soc_pct <= self.max_soc_pct:
            raise ValueError("initial SOC must be within configured limits")
        if not 0 < self.charge_efficiency <= 1:
            raise ValueError("charge_efficiency must be in (0, 1]")
        if not 0 < self.discharge_efficiency <= 1:
            raise ValueError("discharge_efficiency must be in (0, 1]")


@dataclass(frozen=True)
class BatteryStep:
    requested_power_kw: float
    applied_power_kw: float
    soc_pct: float
    temperature_c: float
    limit_reason: str | None


class BatterySimulator:
    """Track SOC using grid-side battery power and directional efficiency.

    Positive power means charging; negative power means discharging.
    """

    _EPSILON = 1e-9

    def __init__(self, config: BatteryConfig) -> None:
        self.config = config
        self.soc_pct = config.initial_soc_pct

    def step(self, requested_power_kw: float, duration_hours: float) -> BatteryStep:
        if duration_hours <= 0:
            raise ValueError("duration_hours must be positive")

        power_limited = max(
            -self.config.max_discharge_power_kw,
            min(requested_power_kw, self.config.max_charge_power_kw),
        )
        limit_reason = None
        if abs(power_limited - requested_power_kw) > self._EPSILON:
            limit_reason = "power_limit"

        applied_power_kw = self._limit_for_available_energy(
            power_limited, duration_hours
        )
        if abs(applied_power_kw - power_limited) > self._EPSILON:
            limit_reason = "soc_limit"

        if applied_power_kw >= 0:
            stored_energy_delta_kwh = (
                applied_power_kw
                * duration_hours
                * self.config.charge_efficiency
            )
        else:
            stored_energy_delta_kwh = (
                applied_power_kw
                * duration_hours
                / self.config.discharge_efficiency
            )

        self.soc_pct += stored_energy_delta_kwh / self.config.capacity_kwh * 100
        self.soc_pct = max(
            self.config.min_soc_pct,
            min(self.soc_pct, self.config.max_soc_pct),
        )

        maximum_power = max(
            self.config.max_charge_power_kw,
            self.config.max_discharge_power_kw,
        )
        utilization = abs(applied_power_kw) / maximum_power
        temperature_c = (
            self.config.base_temperature_c
            + utilization * self.config.temperature_rise_at_full_power_c
        )

        return BatteryStep(
            requested_power_kw=requested_power_kw,
            applied_power_kw=applied_power_kw,
            soc_pct=self.soc_pct,
            temperature_c=temperature_c,
            limit_reason=limit_reason,
        )

    def _limit_for_available_energy(
        self, power_kw: float, duration_hours: float
    ) -> float:
        if power_kw >= 0:
            headroom_kwh = (
                (self.config.max_soc_pct - self.soc_pct)
                / 100
                * self.config.capacity_kwh
            )
            maximum_from_soc_kw = headroom_kwh / (
                duration_hours * self.config.charge_efficiency
            )
            return min(power_kw, max(0.0, maximum_from_soc_kw))

        available_kwh = (
            (self.soc_pct - self.config.min_soc_pct)
            / 100
            * self.config.capacity_kwh
        )
        maximum_discharge_from_soc_kw = (
            available_kwh * self.config.discharge_efficiency / duration_hours
        )
        return max(power_kw, -max(0.0, maximum_discharge_from_soc_kw))
