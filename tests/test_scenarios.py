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


def test_s3_moves_charging_out_of_puant_without_new_peak(cfg):
    """Kural tabanlı akıllı şarj (YM-3): puanttaki araç şarjı azalır, aynı enerji verilir, yeni (22:00) tepe oluşmaz."""
    from microgrid.kpi import compute

    index = time_index(cfg)
    inputs = mock_inputs(cfg, index)
    s2 = compute(simulate(cfg, SCENARIOS["S2 Kontrolsüz şarj"], inputs).steps, cfg)
    s3_steps = simulate(cfg, SCENARIOS["S3 Akıllı şarj"], inputs).steps
    s3 = compute(s3_steps, cfg)
    assert s3["arac_sarj_puant_payi"] < 0.1 < s2["arac_sarj_puant_payi"]
    assert abs(s3["arac_sarj_kwh"] - s2["arac_sarj_kwh"]) < 1e-6
    assert s3["maliyet_tl"] < s2["maliyet_tl"]
    assert s3["tepe_alim_kw"] < s2["tepe_alim_kw"]
    # sınırlara uyuyor
    assert (s3_steps["ev_kw"] <= cfg["station"]["power_limit_kw"] + 1e-6).all()
    assert (s3_steps["grid_kw"] <= cfg["grid"]["site_import_limit_kw"] + 1e-6).all()
