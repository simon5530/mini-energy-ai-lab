"""Command-line simulation loop and Phase 1 telemetry output boundary."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys
from typing import TextIO

import yaml

from .bess import BatteryConfig, BatterySimulator
from .factory import FactoryConfig, FactoryLoadGenerator
from .pv import PVConfig, PVGenerator
from .telemetry import (
    QUALITY,
    SCHEMA_VERSION,
    SOURCE,
    TelemetryRecord,
    write_csv,
    write_jsonl,
)


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


def run_simulation(config: dict, steps: int, seed: int) -> list[TelemetryRecord]:
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

    records: list[TelemetryRecord] = []
    for index in range(steps):
        # The simulator advances logical time immediately; it never sleeps for
        # 15 real minutes.  That keeps experiments deterministic and fast.
        timestamp = start + timedelta(minutes=interval_minutes * index)
        load_kw = factory.power_kw(timestamp)
        pv_kw = pv.power_kw(timestamp)
        requested_battery_kw = demo_battery_request_kw(timestamp)
        battery_step = battery.step(requested_battery_kw, duration_hours)

        # Site power balance uses the repository-wide sign convention:
        # charging is positive (adds grid demand), discharging is negative.
        grid_import_kw = load_kw - pv_kw + battery_step.applied_power_kw
        records.append(
            TelemetryRecord(
                schema_version=SCHEMA_VERSION,
                source=SOURCE,
                quality=QUALITY,
                step_index=index,
                timestamp=timestamp,
                interval_minutes=interval_minutes,
                factory_load_kw=load_kw,
                pv_power_kw=pv_kw,
                battery_requested_power_kw=requested_battery_kw,
                battery_power_kw=battery_step.applied_power_kw,
                battery_soc_pct=battery_step.soc_pct,
                battery_temperature_c=battery_step.temperature_c,
                grid_import_kw=grid_import_kw,
                limit_reason=battery_step.limit_reason,
            )
        )
    return records


def write_table(records: list[TelemetryRecord], stream: TextIO) -> None:
    """Render the original human-readable terminal view."""

    stream.write(
        "timestamp                  load_kW   pv_kW   requested_kW   batt_kW   "
        "SOC_%   temp_C   grid_kW   limit\n"
    )
    for record in records:
        stream.write(
            f"{record.timestamp.isoformat():25} "
            f"{record.factory_load_kw:8.1f} "
            f"{record.pv_power_kw:7.1f} "
            f"{record.battery_requested_power_kw:12.1f} "
            f"{record.battery_power_kw:9.1f} "
            f"{record.battery_soc_pct:7.2f} "
            f"{record.battery_temperature_c:8.1f} "
            f"{record.grid_import_kw:9.1f} "
            f"{record.limit_reason or '-'}\n"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the synthetic energy simulator")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/system.yaml"),
        help="path to YAML configuration",
    )
    parser.add_argument("--steps", type=int, help="number of simulation steps")
    parser.add_argument("--seed", type=int, default=7, help="factory noise seed")
    parser.add_argument(
        "--format",
        choices=("table", "jsonl", "csv"),
        default="table",
        help="output format (default: table)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="write output to this file instead of standard output",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)
    # Check against None rather than truthiness: an explicit ``--steps 0`` must
    # reach run_simulation and fail validation instead of silently using the
    # configured default.
    steps = (
        args.steps
        if args.steps is not None
        else int(config["simulation"]["default_steps"])
    )
    records = run_simulation(config, steps=steps, seed=args.seed)

    # Output is the replaceable edge of the program.  Simulation always creates
    # the same validated records; this branch only chooses their representation.
    stream: TextIO
    should_close = args.output is not None
    if args.output is None:
        stream = sys.stdout
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        stream = args.output.open("w", encoding="utf-8", newline="")

    try:
        if args.format == "jsonl":
            write_jsonl(records, stream)
        elif args.format == "csv":
            write_csv(records, stream)
        else:
            write_table(records, stream)
    finally:
        if should_close:
            stream.close()


if __name__ == "__main__":
    main()
