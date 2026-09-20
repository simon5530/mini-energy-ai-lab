import csv
import io
import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from simulator.cli import load_config, run_simulation
from simulator.telemetry import SCHEMA_VERSION, write_csv, write_jsonl


def sample_records():
    config = load_config(Path("config/system.yaml"))
    return run_simulation(config, steps=2, seed=7)


def test_jsonl_is_versioned_and_preserves_requested_and_applied_power() -> None:
    records = sample_records()
    stream = io.StringIO()

    write_jsonl(records, stream)

    payloads = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert len(payloads) == 2
    assert payloads[0]["schema_version"] == SCHEMA_VERSION
    assert payloads[0]["source"] == "synthetic-simulator"
    assert payloads[0]["quality"] == "simulated"
    assert payloads[0]["timestamp"].endswith("+08:00")
    assert payloads[0]["battery_requested_power_kw"] == 80.0
    assert payloads[0]["battery_power_kw"] == 80.0


def test_csv_has_one_header_and_one_row_per_record() -> None:
    stream = io.StringIO(newline="")

    write_csv(sample_records(), stream)

    rows = list(csv.DictReader(io.StringIO(stream.getvalue())))
    assert len(rows) == 2
    assert rows[0]["schema_version"] == SCHEMA_VERSION
    assert rows[1]["step_index"] == "1"
    assert rows[0]["timestamp"].endswith("+08:00")


def test_telemetry_rejects_ambiguous_time_and_broken_power_balance() -> None:
    record = sample_records()[0]

    with pytest.raises(ValueError, match="UTC offset"):
        replace(record, timestamp=datetime(2026, 1, 15, 6, 0))

    with pytest.raises(ValueError, match="power balance"):
        replace(record, grid_import_kw=record.grid_import_kw + 1)
