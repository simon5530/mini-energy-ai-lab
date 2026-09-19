import pytest

from simulator.bess import BatteryConfig, BatterySimulator


@pytest.fixture
def config() -> BatteryConfig:
    return BatteryConfig(
        capacity_kwh=500,
        max_charge_power_kw=250,
        max_discharge_power_kw=250,
        min_soc_pct=20,
        max_soc_pct=90,
        initial_soc_pct=60,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
    )


def test_soc_uses_energy_time_and_directional_efficiency(config: BatteryConfig) -> None:
    battery = BatterySimulator(config)

    charged = battery.step(100, duration_hours=1)
    assert charged.soc_pct == pytest.approx(79.0)

    discharged = battery.step(-100, duration_hours=1)
    assert discharged.soc_pct == pytest.approx(57.9473684)


def test_power_is_clamped_to_configured_limits(config: BatteryConfig) -> None:
    charging = BatterySimulator(config).step(10_000, duration_hours=0.25)
    discharging = BatterySimulator(config).step(-10_000, duration_hours=0.25)

    assert charging.applied_power_kw == 250
    assert charging.limit_reason == "power_limit"
    assert discharging.applied_power_kw == -250
    assert discharging.limit_reason == "power_limit"


def test_soc_boundary_reduces_power_and_never_exceeds_limit() -> None:
    config = BatteryConfig(
        capacity_kwh=500,
        max_charge_power_kw=250,
        max_discharge_power_kw=250,
        min_soc_pct=20,
        max_soc_pct=90,
        initial_soc_pct=89,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
    )

    result = BatterySimulator(config).step(250, duration_hours=1)

    assert result.applied_power_kw == pytest.approx(5 / 0.95)
    assert result.soc_pct == pytest.approx(90)
    assert result.limit_reason == "soc_limit"


def test_minimum_soc_boundary_reduces_discharge_power() -> None:
    config = BatteryConfig(
        capacity_kwh=500,
        max_charge_power_kw=250,
        max_discharge_power_kw=250,
        min_soc_pct=20,
        max_soc_pct=90,
        initial_soc_pct=21,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
    )

    result = BatterySimulator(config).step(-250, duration_hours=1)

    assert result.applied_power_kw == pytest.approx(-5 * 0.95)
    assert result.soc_pct == pytest.approx(20)
    assert result.limit_reason == "soc_limit"


def test_non_positive_duration_is_rejected(config: BatteryConfig) -> None:
    with pytest.raises(ValueError, match="duration_hours"):
        BatterySimulator(config).step(100, duration_hours=0)
