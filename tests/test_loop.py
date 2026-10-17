import pandas as pd
import pytest

from microgrid.config import load_config
from microgrid.interfaces import GridResult
from microgrid.sim.loop import STATION_COLUMNS, STEP_COLUMNS, run, time_index
from microgrid.sim.mocks import MockStation, SimpleBattery, UncontrolledEMS, mock_inputs


@pytest.fixture
def cfg():
    return load_config()


def run_mock(cfg, grid=None):
    index = time_index(cfg)
    station = MockStation(cfg, index[0])
    return run(cfg, mock_inputs(cfg, index), station, UncontrolledEMS(), SimpleBattery(cfg), grid), station


def test_time_index_starts_at_noon_and_covers_horizon(cfg):
    index = time_index(cfg)
    assert len(index) == 24 * 60 // cfg["simulation"]["step_minutes"]
    assert index[0].hour == 12 and str(index.tz) == "Europe/Istanbul"


def test_power_balance_holds_every_step(cfg):
    s = run_mock(cfg)[0].steps
    assert list(s.columns) == STEP_COLUMNS
    balance = s.base_load_kw + s.ev_kw + s.bess_kw - s.pv_kw
    assert (balance - s.grid_kw).abs().max() < 1e-9


def test_station_energy_matches_soc_gain(cfg):
    result, station = run_mock(cfg)
    dt = cfg["simulation"]["step_minutes"] / 60
    delivered = result.steps.ev_kw.sum() * dt
    log = result.station
    assert list(log.columns) == STATION_COLUMNS
    first_soc = log.groupby("vehicle_id").soc.first()
    final_soc = {v["id"]: v["soc"] for v in station.vehicles}
    gained = sum((final_soc[vid] - soc) * cfg["vehicles"]["battery_kwh"] for vid, soc in first_soc.items())
    assert delivered == pytest.approx(gained)
    assert delivered > 0


def test_uncontrolled_charging_respects_charger_power(cfg):
    log = run_mock(cfg)[0].station
    max_kw = max(c["power_kw"] for c in cfg["station"]["chargers"])
    assert log.power_kw.max() <= max_kw + 1e-9


def test_missing_input_column_is_reported(cfg):
    index = time_index(cfg)
    inputs = mock_inputs(cfg, index).drop(columns="pv_kw")
    with pytest.raises(ValueError, match="pv_kw"):
        run(cfg, inputs, MockStation(cfg, index[0]), UncontrolledEMS(), SimpleBattery(cfg))


def test_grid_model_is_called_with_step_injections(cfg):
    seen = []

    class FakeGrid:
        def run(self, ctx, inj):
            seen.append(inj)
            return GridResult(True, 0.97, 1.01, 40.0, 55.0)

    s = run_mock(cfg, FakeGrid())[0].steps
    assert len(seen) == len(s)
    assert s.min_vm_pu.eq(0.97).all() and s.grid_converged.all()


def test_battery_respects_power_and_soc_limits(cfg):
    b = SimpleBattery(cfg)
    assert b.apply(10_000, 0.25) == cfg["bess"]["power_kw"]
    for _ in range(100):
        b.apply(-10_000, 0.25)
    assert b.soc == pytest.approx(cfg["bess"]["soc_min"])
    assert b.apply(-10, 0.25) == pytest.approx(0)
