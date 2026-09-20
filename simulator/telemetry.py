"""Versioned telemetry records and serializers for the synthetic simulator.

This module is the Phase 1 boundary between simulation logic and downstream
consumers.  It deliberately does not publish to MQTT, a database, or hardware:
the same validated records can be encoded locally before a transport is added.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Iterable, TextIO


SCHEMA_VERSION = "1.0"
SOURCE = "synthetic-simulator"
QUALITY = "simulated"


@dataclass(frozen=True)
class TelemetryRecord:
    """One interval of synthetic site measurements and battery state.

    ``battery_requested_power_kw`` preserves the requested setpoint while
    ``battery_power_kw`` records what the constrained battery model applied.
    Keeping both values makes power- or SOC-limit interventions observable.
    """

    schema_version: str
    source: str
    quality: str
    step_index: int
    timestamp: datetime
    interval_minutes: float
    factory_load_kw: float
    pv_power_kw: float
    battery_requested_power_kw: float
    battery_power_kw: float
    battery_soc_pct: float
    battery_temperature_c: float
    grid_import_kw: float
    limit_reason: str | None

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
        if self.source != SOURCE or self.quality != QUALITY:
            raise ValueError("telemetry must identify its synthetic origin")
        if self.step_index < 0:
            raise ValueError("step_index must be non-negative")
        # An offset-aware timestamp avoids silently mixing local time and UTC
        # when records are later imported by another process.
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must include a UTC offset")
        if self.interval_minutes <= 0:
            raise ValueError("interval_minutes must be positive")

        numeric_values = (
            self.interval_minutes,
            self.factory_load_kw,
            self.pv_power_kw,
            self.battery_requested_power_kw,
            self.battery_power_kw,
            self.battery_soc_pct,
            self.battery_temperature_c,
            self.grid_import_kw,
        )
        if not all(math.isfinite(value) for value in numeric_values):
            raise ValueError("telemetry numeric values must be finite")
        if not 0 <= self.battery_soc_pct <= 100:
            raise ValueError("battery_soc_pct must be in [0, 100]")
        if self.limit_reason not in (None, "power_limit", "soc_limit"):
            raise ValueError("limit_reason is not part of the telemetry contract")

        expected_grid_import_kw = (
            self.factory_load_kw - self.pv_power_kw + self.battery_power_kw
        )
        if not math.isclose(
            self.grid_import_kw,
            expected_grid_import_kw,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            raise ValueError("grid_import_kw violates the site power balance")

    def as_serializable_dict(self) -> dict[str, str | int | float | None]:
        """Return a stable, transport-neutral representation of the record."""

        values = asdict(self)
        # ISO 8601 retains the +08:00 offset from the configured simulation
        # start time and is understood by both JSON and spreadsheet tools.
        values["timestamp"] = self.timestamp.isoformat()
        return values


def write_jsonl(records: Iterable[TelemetryRecord], stream: TextIO) -> None:
    """Write one complete JSON object per line for streaming-friendly replay."""

    for record in records:
        stream.write(
            json.dumps(
                record.as_serializable_dict(),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        stream.write("\n")


def write_csv(records: Iterable[TelemetryRecord], stream: TextIO) -> None:
    """Write records as CSV with a header suitable for spreadsheet inspection."""

    iterator = iter(records)
    try:
        first = next(iterator)
    except StopIteration:
        return

    first_values = first.as_serializable_dict()
    writer = csv.DictWriter(stream, fieldnames=list(first_values))
    writer.writeheader()
    writer.writerow(first_values)
    for record in iterator:
        writer.writerow(record.as_serializable_dict())
