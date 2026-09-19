from pathlib import Path

import pytest

from simulator.cli import load_config, run_simulation


def test_simulation_values_evolve_and_grid_balance_is_explicit() -> None:
    config = load_config(Path("config/system.yaml"))

    rows = run_simulation(config, steps=8, seed=7)

    assert len(rows) == 8
    assert len({round(row.factory_load_kw, 3) for row in rows}) > 1
    assert len({round(row.pv_power_kw, 3) for row in rows}) > 1
    assert rows[-1].battery_soc_pct > rows[0].battery_soc_pct
    for row in rows:
        assert row.grid_import_kw == pytest.approx(
            row.factory_load_kw - row.pv_power_kw + row.battery_power_kw
        )
        assert 20 <= row.battery_soc_pct <= 90
