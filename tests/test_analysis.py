"""Hafta 8–9 (YM-1): senaryo tablosu, duyarlılık ve döngüsel batarya. data/processed/ yoksa atlanır."""
import pytest

from microgrid.analysis import Scenario, run_day, scenario_cfg, scenario_table, set_path, sweep
from microgrid.config import load_config
from microgrid.data import loads as load_profiles
from microgrid.data import pvgis, seasons
from microgrid.interfaces import Decision
from microgrid.sim.mocks import SimpleBattery, UncontrolledEMS


@pytest.fixture(scope="module")
def cfg():
    cfg = load_config()
    if not (pvgis.processed_path(cfg).exists() and load_profiles.processed_path(cfg).exists()):
        pytest.skip("data/processed/ dosyaları yok (python -m microgrid.data)")
    cfg["inputs"]["sky_classes"] = 1      # testler hızlı olsun: 8 temsili gün
    return cfg


def test_set_path_and_scenario_cfg_do_not_touch_original(cfg):
    c = scenario_cfg(cfg, Scenario("x", config={"vehicles.count": 0}), {"pv.installed_kw": 50})
    assert c["vehicles"]["count"] == 0 and c["pv"]["installed_kw"] == 50
    assert cfg["vehicles"]["count"] != 0 and cfg["pv"]["installed_kw"] != 50
    with pytest.raises(KeyError):
        set_path(c, "pv.yok_boyle_bir_alan", 1)


def test_scenario_table_shows_station_impact(cfg):
    t = scenario_table([Scenario("S1", config={"vehicles.count": 0}), Scenario("S2")], cfg)
    assert list(t.columns) == ["S1", "S2", "birim"]
    assert t.loc["maliyet_tl", "S2"] > t.loc["maliyet_tl", "S1"]
    assert t.loc["tepe_alim_kw", "S2"] > t.loc["tepe_alim_kw", "S1"]
    assert t.loc["arac_sarj_kwh", "S1"] == 0


def test_sweep_pv_lowers_cost(cfg):
    df = sweep(cfg, Scenario("S2"), "pv.installed_kw", [0, 100, 200])
    cost = df["maliyet_tl"].astype(float)
    assert list(df.index) == [0, 100, 200]
    assert cost[0] > cost[100] > cost[200]
    assert df.loc[0, "pv_kwh"] == 0


class DrainEMS(UncontrolledEMS):
    """Bataryayı her adımda tam güçle boşaltmaya çalışır."""

    def decide(self, inp):
        return Decision(ev_kw=super().decide(inp).ev_kw, bess_kw=-1000.0)


def test_cyclic_battery_gives_no_free_energy(cfg):
    # Batarya hep boşaltılıyorsa ve hiç şarj edilmiyorsa, döngüsel çalıştırmada verdiği enerji ~0 olmalı
    key = ("kis", "hafta_ici", "tum")
    inp = seasons.representative_inputs(cfg, key)
    s = Scenario("drain", ems=lambda c: DrainEMS())
    steps = run_day(cfg, s, inp)
    assert -steps["bess_kw"].sum() * 0.25 < 1.0
    # Isınma olmasa batarya ilk gün başlangıç SOC'sindeki enerjiyi bedava verirdi
    first = run_day(cfg, s, inp, warmup=0)
    b = cfg["bess"]
    assert -first["bess_kw"].sum() * 0.25 == pytest.approx((b["soc_initial"] - b["soc_min"]) * b["capacity_kwh"])


def test_zero_capacity_battery(cfg):
    c = scenario_cfg(cfg, Scenario("x"), {"bess.capacity_kwh": 0})
    assert SimpleBattery(c).apply(-50.0, 0.25) == 0.0
