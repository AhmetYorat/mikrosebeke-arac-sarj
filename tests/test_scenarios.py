"""sim/scenarios.py: senaryo listesi, config değişiklikleri, tek gün çalıştırma (YM-4)."""
import pytest

from microgrid.config import load_config
from microgrid.sim.loop import time_index
from microgrid.sim.mocks import mock_inputs
from microgrid.sim.scenarios import SCENARIOS, apply_overrides, set_path, simulate


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def test_set_path_rejects_typos(cfg):
    with pytest.raises(KeyError):
        set_path(apply_overrides(cfg, {}), "vehicle.count", 5)   # doğrusu vehicles.count


def test_overrides_do_not_mutate(cfg):
    before = cfg["vehicles"]["count"]
    c = apply_overrides(cfg, {"vehicles.count": 3})
    assert c["vehicles"]["count"] == 3 and cfg["vehicles"]["count"] == before


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_every_scenario_runs_and_balances(cfg, name):
    index = time_index(cfg)
    s = simulate(cfg, SCENARIOS[name], mock_inputs(cfg, index)).steps
    assert len(s) == len(index)
    assert ((s.base_load_kw + s.ev_kw + s.bess_kw - s.pv_kw) - s.grid_kw).abs().max() < 1e-9


def test_s1_has_no_charging(cfg):
    index = time_index(cfg)
    s = simulate(cfg, SCENARIOS["S1 Temel (araç yok)"], mock_inputs(cfg, index)).steps
    assert s["ev_kw"].abs().max() == 0


def test_s2_charges_in_evening(cfg):
    index = time_index(cfg)
    s = simulate(cfg, SCENARIOS["S2 Kontrolsüz şarj"], mock_inputs(cfg, index)).steps
    assert s.loc[s.index.hour.isin([18, 19, 20]), "ev_kw"].max() > 0
