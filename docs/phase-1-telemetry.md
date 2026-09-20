# Phase 1: Synthetic Telemetry Contract

## Goal

Phase 1 separates **what the simulator knows** from **how another component
could consume it**. A `TelemetryRecord` is the boundary. The simulation creates
records; encoders represent them as table text, JSONL, or CSV.

```text
YAML config
    │
    ▼
factory + PV profiles ──► battery model ──► site power balance
                                                   │
                                                   ▼
                                        validated TelemetryRecord
                                                   │
                                      ┌────────────┼────────────┐
                                      ▼            ▼            ▼
                                    table        JSONL          CSV
```

No transport appears in this diagram. That is deliberate: adding MQTT or an
industrial protocol should not change battery arithmetic or record validation.

## Field groups

- **Identity:** `schema_version`, `source`, `quality`, `step_index`
- **Time:** `timestamp`, `interval_minutes`
- **Power:** `factory_load_kw`, `pv_power_kw`,
  `battery_requested_power_kw`, `battery_power_kw`, `grid_import_kw`
- **Battery state:** `battery_soc_pct`, `battery_temperature_c`
- **Constraint outcome:** `limit_reason`

The sign convention remains:

```text
battery_power_kw > 0  charging
battery_power_kw < 0  discharging
grid_import_kw = factory_load_kw - pv_power_kw + battery_power_kw
```

## Why requested and applied power are separate

A controller may request 250 kW of charging while the model can safely apply
only 40 kW because SOC is near its maximum. Recording only the applied value
would hide that intervention. The pair of fields plus `limit_reason` makes the
constraint visible and auditable.

## Why JSONL and CSV

- **JSONL:** one self-contained object per line; suitable for streaming, logs,
  replay, and incremental parsing.
- **CSV:** easy to inspect in spreadsheets and plotting tools.
- **Table:** optimized for a person reading a terminal.

They are representations of one contract, not three simulation paths.

## Validation boundary

Construction rejects records that contain:

- a timestamp without an explicit UTC offset;
- non-finite numeric values;
- SOC outside 0–100%;
- an unknown limit reason;
- a broken site power balance.

Validation does not prove that synthetic values represent a real site. The
`source=synthetic-simulator` and `quality=simulated` fields prevent that
interpretation from being implicit.

## Exercises

1. Run 48 steps as JSONL and find the first record where requested and applied
   battery power differ.
2. Change the initial SOC to 89% and explain the resulting `soc_limit` record.
3. Load the CSV in a plotting tool and graph load, PV, battery, and grid power.
4. Add a failing test that changes `grid_import_kw` by 1 kW, then trace where
   the record contract rejects it.

## Phase boundary

The next phase may add a local protocol adapter backed by these synthetic
records. It must retain the same versioned contract, remain disconnected from
operational equipment, and have deterministic tests before any networked
experiment is considered.
