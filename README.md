# Mini Energy AI Lab

> **Simulation and personal learning project.** This repository does not
> connect to real energy hardware, is not a production EMS, and must not be
> used to control a real BESS, BMS, PCS, inverter, or electrical facility.

Mini Energy AI Lab is a staged project for learning how industrial energy
software is structured. Phase 0 models a Taiwanese commercial/industrial site
with synthetic factory load, solar PV, grid import, and one battery energy
storage system (BESS). Phase 1 adds a validated, versioned telemetry boundary
without connecting the simulator to a real device, broker, or database.

## Implemented scope

### Phase 0 — system model

This **Model-in-the-Loop / early system-modelling exercise** contains:

- a configurable battery energy-balance model;
- synthetic factory load and clear-sky PV profiles;
- a CLI loop that prints timestamped system state;
- tests for SOC arithmetic, efficiency, power limits, and SOC limits.

The fixed battery schedule in the CLI exists only to make state change visible.
It is **not** EMS logic and does not optimize cost or grid demand.

### Phase 1 — synthetic telemetry

The simulator now turns every interval into a `TelemetryRecord` with:

- schema version, source, quality, step index, and offset-aware timestamp;
- the interval duration and all values with explicit kW, %, or °C units;
- requested versus actually applied battery power;
- an optional reason when a power or SOC constraint changes the request;
- executable validation for finite numbers, SOC range, timestamps, and site
  power balance;
- human-readable table, newline-delimited JSON (JSONL), and CSV encoders.

This phase establishes a local data contract. It does **not** add MQTT, Modbus,
OPC UA, cloud ingestion, persistent storage, or real-time device telemetry.

## Run locally

Python 3.11 or 3.12 is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
mini-energy-sim --steps 24
mini-energy-sim --steps 24 --format jsonl
mini-energy-sim --steps 24 --format csv --output output/telemetry.csv
pytest
```

Configuration lives in [`config/system.yaml`](config/system.yaml). The default
15-minute step is simulated immediately; the CLI does not sleep in real time.
Pass `--seed` to change the reproducible factory-load noise.

JSONL is useful for replay or line-by-line streaming because each line is a
complete JSON object. CSV is convenient for spreadsheet inspection. The
default table remains intended for people, not machine ingestion.

## Read the code as a learning path

The most important execution path is intentionally small:

1. [`simulator/cli.py`](simulator/cli.py) loads configuration and advances
   logical simulation time.
2. [`simulator/factory.py`](simulator/factory.py) and
   [`simulator/pv.py`](simulator/pv.py) generate deterministic synthetic input
   signals.
3. [`simulator/bess.py`](simulator/bess.py) constrains the requested power,
   converts power and elapsed time into stored energy, and updates SOC.
4. `run_simulation` applies the site power-balance equation and creates a
   validated [`TelemetryRecord`](simulator/telemetry.py).
5. [`simulator/telemetry.py`](simulator/telemetry.py) serializes the same record
   as JSONL or CSV without changing the simulation.

Comments in those files explain intent, units, boundaries, and non-obvious
decisions. Tests are the executable contract: start with
[`tests/test_bess.py`](tests/test_bess.py), then
[`tests/test_simulation.py`](tests/test_simulation.py), and finally
[`tests/test_telemetry.py`](tests/test_telemetry.py).

## Model and units

### kW versus kWh

- **kW (kilowatts)** is power: the instantaneous rate at which energy flows.
- **kWh (kilowatt-hours)** is energy: power accumulated over time.
- A constant 100 kW flow lasting 0.25 hours transfers 25 kWh before losses.

The configured battery has 500 kWh of energy capacity and 250 kW charge and
discharge power limits. Those values describe different physical quantities.

### SOC

State of charge (SOC) estimates stored energy as a percentage of usable model
capacity. In this simplified model:

```text
SOC change (%) = stored-energy change (kWh) / capacity (kWh) × 100
```

SOC is constrained to the configured 20–90% operating range. A request that
would cross a boundary is reduced and labelled `soc_limit`; a request exceeding
a power rating is reduced and labelled `power_limit`. The simulator never
silently lets SOC cross its configured limits.

### Charge, discharge, and efficiency

The repository uses one sign convention everywhere in Phase 0:

```text
battery_power_kw > 0  means charging
battery_power_kw < 0  means discharging
```

Charging adds to facility grid demand; discharging subtracts from it:

```text
grid_import_kw = factory_load_kw - pv_power_kw + battery_power_kw
```

Directional efficiency approximates conversion losses. Charging stores less
energy than arrives at the battery-system boundary; discharging must remove
more stored energy than it delivers. This is an intentionally simple model,
not an electrochemical or degradation simulation.

### BMS, PCS, and BESS

- **BMS (Battery Management System):** monitors cells/modules and enforces
  battery protection constraints such as voltage, current, temperature, and
  allowed operating state.
- **PCS (Power Conversion System):** converts electrical power between the
  battery's DC side and the facility/grid AC side and follows valid power
  setpoints.
- **BESS (Battery Energy Storage System):** the complete storage system,
  including battery, BMS, PCS, and supporting equipment.

The Phase 0 Python class is only a system-level energy approximation. It does
not emulate actual BMS or PCS firmware.

## Assumptions and limitations

- Load, PV, and temperature are synthetic signals, not forecasts or measured
  Taiwanese site data.
- Efficiency is constant in each direction; auxiliary consumption, reactive
  power, voltage, current, degradation, cell imbalance, and thermal dynamics
  are out of scope.
- The model uses a fixed time step and treats power as constant within it.
- No MQTT, Modbus, EMS control, MCP, LLM, approval flow, or real hardware is
  included through Phase 1.
- The software makes no production-safety, standards-compliance, or commercial
  performance claim.

## Why a small custom model?

Existing projects such as PyBaMM and Sandia's SNL-QUEST provide much broader
battery or energy-storage modelling. They are valuable references, but would
hide the basic energy arithmetic this learning phase is meant to expose. This
repository therefore begins with a deliberately small model and can adopt
specialized libraries only if a later, explicit learning objective requires
them.

## Roadmap boundary

The planned learning path is simulation → telemetry → industrial protocol →
deterministic EMS → optional agent supervision → human approval → fault tests.
The first two items are implemented. The next bounded phase is a **local-only
industrial-protocol adapter** driven exclusively by synthetic records. It must
not connect to a real PLC, meter, inverter, BMS, PCS, or operational network.
Each later phase requires a separate review and commit.

## License

MIT. See [`LICENSE`](LICENSE).
