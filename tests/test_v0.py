"""v0 (Hafta 4): döngü gerçek veriyle (YM-1 build_inputs) 24 saat uçtan uca çalışıyor.

data/processed/ dosyaları yoksa atlanır (önce: python -m microgrid.data).
"""
import pytest

from microgrid.config import load_config
from microgrid.data import loads as load_profiles
from microgrid.data import pvgis
from microgrid.data.inputs import build_inputs
from microgrid.grid import PandapowerGrid
from microgrid.sim.loop import STEP_COLUMNS, run, time_index
from microgrid.sim.mocks import MockStation, SimpleBattery, UncontrolledEMS


@pytest.fixture(scope="module")
def cfg():
    cfg = load_config()
    if not (pvgis.processed_path(cfg).exists() and load_profiles.processed_path(cfg).exists()):
        pytest.skip("data/processed/ dosyaları yok (python -m microgrid.data)")
    return cfg


@pytest.mark.parametrize("start", ["2023-06-21 12:00", "2023-12-20 12:00"])
def test_v0_runs_24h_with_real_inputs(cfg, start):
    cfg = {**cfg, "simulation": {**cfg["simulation"], "start": start}}
    index = time_index(cfg)
    result = run(
        cfg, build_inputs(cfg, index), MockStation(cfg, index[0]), UncontrolledEMS(), SimpleBattery(cfg),
        grid=PandapowerGrid(cfg),
    )
    s = result.steps
    assert list(s.columns) == STEP_COLUMNS and len(s) == len(index)
    assert s[["pv_kw", "base_load_kw", "ev_kw", "grid_kw", "cost_tl"]].notna().all().all()
    assert s["grid_converged"].all()
    # Güç dengesi her adımda tutuyor
    balance = s.base_load_kw + s.ev_kw + s.bess_kw - s.pv_kw
    assert (balance - s.grid_kw).abs().max() < 1e-9
    # Akşam araçlar şarj oluyor, gece PV yok
    assert s["ev_kw"].max() > 0
    assert s.loc[s.index.hour.isin([1, 2, 3]), "pv_kw"].max() == 0
