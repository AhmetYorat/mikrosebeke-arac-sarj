import math

import pytest

from microgrid.config import load_config
from microgrid.grid import PandapowerGrid
from microgrid.interfaces import GridInjections
from microgrid.sim.loop import run, time_index
from microgrid.sim.mocks import MockStation, SimpleBattery, UncontrolledEMS, mock_inputs


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def grid(cfg):
    return PandapowerGrid(cfg)


def test_empty_network_sits_at_nominal_voltage(grid):
    r = grid.run(None, GridInjections(0, 0, 0, 0))
    assert r.converged
    assert r.min_vm_pu == pytest.approx(1.0, abs=1e-3)
    assert r.max_line_loading_pct == pytest.approx(0, abs=0.1)


def test_more_station_load_means_lower_voltage(grid):
    v = [grid.run(None, GridInjections(0, 38, p, 0)).min_vm_pu for p in (0, 50, 100, 150)]
    assert v == sorted(v, reverse=True)
    assert v[-1] < v[0] - 0.01


def test_pv_export_raises_voltage_at_site(grid):
    grid.run(None, GridInjections(pv_kw=80, base_load_kw=20, ev_kw=0, bess_kw=0))
    assert grid.bus_voltages()["site"] > 1.0


def test_bess_discharge_relieves_station_feeder(grid):
    without = grid.run(None, GridInjections(0, 38, 150, 0))
    with_bess = grid.run(None, GridInjections(0, 38, 150, -100))
    assert with_bess.max_line_loading_pct < without.max_line_loading_pct
    assert with_bess.min_vm_pu > without.min_vm_pu


def test_trafo_loading_matches_apparent_power(grid, cfg):
    # 200 kW, cos φ = 1: S ≈ 200 kVA, 400 kVA trafoda ~%50 (kayıplarla biraz fazlası).
    r = grid.run(None, GridInjections(0, 0, 200, 0))
    assert 48 < r.trafo_loading_pct < 56


def test_all_chargers_overload_the_station_cable(grid, cfg):
    # İstasyon sınırı (150 kW) olmazsa tüm üniteler (276 kW) otopark kablosunu aşırı yükler.
    installed = sum(c["count"] * c["power_kw"] for c in cfg["station"]["chargers"])
    r = grid.run(None, GridInjections(0, 38, installed, 0))
    assert r.max_line_loading_pct > 100
    limited = grid.run(None, GridInjections(0, 38, cfg["station"]["power_limit_kw"], 0))
    assert limited.max_line_loading_pct < 100


def test_loop_with_pandapower_fills_grid_columns(cfg):
    index = time_index(cfg)
    s = run(cfg, mock_inputs(cfg, index), MockStation(cfg, index[0]), UncontrolledEMS(), SimpleBattery(cfg),
            grid=PandapowerGrid(cfg)).steps
    assert s.grid_converged.all()
    assert not s.min_vm_pu.isna().any()
    assert all(0.9 < v <= 1.1 for v in s.min_vm_pu)
    assert not any(math.isnan(x) for x in s.trafo_loading_pct)
