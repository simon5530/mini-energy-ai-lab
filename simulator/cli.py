"""Command-line simulation loop for Phase 0."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from .bess import BatteryConfig, BatterySimulator
from .factory import FactoryConfig, FactoryLoadGenerator
from .pv import PVConfig, PVGenerator


@dataclass(frozen=True)
class SimulationRow:
    timestamp: datetime
    factory_load_kw: float
    pv_power_kw: float
    battery_power_kw: float
    battery_soc_pct: float
    battery_temperature_c: float
    grid_import_kw: float
    limit_reason: str | None


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise ValueError("configuration root must be a mapping")
    return data


def demo_battery_request_kw(timestamp: datetime) -> float:
    """A fixed demonstration schedule, not an EMS decision algorithm."""
    if 6 <= timestamp.hour < 9:
        return 80.0
    if 15 <= timestamp.hour < 20:
        return -100.0
    return 0.0


def run_simulation(config: dict, steps: int, seed: int) -> list[SimulationRow]:
    if steps <= 0:
        raise ValueError("steps must be positive")

    simulation = config["simulation"]
    interval_minutes = float(simulation["interval_minutes"])
    if interval_minutes <= 0:
        raise ValueError("interval_minutes must be positive")
    start = datetime.fromisoformat(simulation["start_time"])

    battery = BatterySimulator(BatteryConfig(**config["battery"]))
    factory = FactoryLoadGenerator(FactoryConfig(**config["factory"]), seed=seed)
    pv = PVGenerator(PVConfig(**config["pv"]))
    duration_hours = interval_minutes / 60

    rows: list[SimulationRow] = []
    for index in range(steps):
        timestamp = start + timedelta(minutes=interval_minutes * index)
        load_kw = factory.power_kw(timestamp)
        pv_kw = pv.power_kw(timestamp)
        battery_step = battery.step(
            demo_battery_request_kw(timestamp), duration_hours
        )
        grid_import_kw = load_kw - pv_kw + battery_step.applied_power_kw
        rows.append(
            SimulationRow(
                timestamp=timestamp,
                factory_load_kw=load_kw,
                pv_power_kw=pv_kw,
                battery_power_kw=battery_step.applied_power_kw,
                battery_soc_pct=battery_step.soc_pct,
                battery_temperature_c=battery_step.temperature_c,
                grid_import_kw=grid_import_kw,
                limit_reason=battery_step.limit_reason,
            )
        )
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Phase 0 energy simulator")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/system.yaml"),
        help="path to YAML configuration",
    )
    parser.add_argument("--steps", type=int, help="number of simulation steps")
    parser.add_argument("--seed", type=int, default=7, help="factory noise seed")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)
    steps = args.steps or int(config["simulation"]["default_steps"])
    rows = run_simulation(config, steps=steps, seed=args.seed)

    print(
        "timestamp                  load_kW   pv_kW   batt_kW   SOC_%   temp_C   grid_kW   limit"
    )
    for row in rows:
        print(
            f"{row.timestamp.isoformat():25} "
            f"{row.factory_load_kw:8.1f} "
            f"{row.pv_power_kw:7.1f} "
            f"{row.battery_power_kw:9.1f} "
            f"{row.battery_soc_pct:7.2f} "
            f"{row.battery_temperature_c:8.1f} "
            f"{row.grid_import_kw:9.1f} "
            f"{row.limit_reason or '-'}"
        )


if __name__ == "__main__":
    main()
