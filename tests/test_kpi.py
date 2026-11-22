"""KPI modülü (YM-1, Hafta 5). Elle hesaplanabilen küçük bir tabloyla ve sahte döngüyle test edilir."""
import math

import pandas as pd
import pytest

from microgrid.config import load_config
from microgrid.kpi import KPI_UNITS, compare, compute
from microgrid.sim.loop import run, time_index
from microgrid.sim.mocks import MockStation, SimpleBattery, UncontrolledEMS, mock_inputs


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture
def steps(cfg):
    # 4 adım (15 dk): öğlen PV fazlası, akşam puantta kontrolsüz şarj, gece şarj, öğlen yine fazla
    idx = pd.DatetimeIndex(
        ["2023-06-21 12:00", "2023-06-21 18:00", "2023-06-21 23:00", "2023-06-22 13:00"], tz="Europe/Istanbul"
    )
    pv = [80.0, 0.0, 0.0, 40.0]
    base = [30.0, 40.0, 20.0, 30.0]
    ev = [0.0, 150.0, 22.0, 0.0]
    grid = [b + e - p for b, e, p in zip(base, ev, pv)]   # [-50, 190, 42, -10]
    prices = {p["name"]: p["price_tl_per_kwh"] for p in cfg["tariff"]["periods"]}
    price = [prices["gunduz"], prices["puant"], prices["gece"], prices["gunduz"]]
    return pd.DataFrame(
        {
            "pv_kw": pv, "base_load_kw": base, "ev_kw": ev, "bess_kw": 0.0, "grid_kw": grid,
            "price_tl_per_kwh": price,
            "cost_tl": [max(g, 0) * pr * 0.25 for g, pr in zip(grid, price)],
            "min_vm_pu": [1.0, 0.94, 0.99, 1.0],
            "max_line_loading_pct": [20.0, 85.0, 30.0, 15.0],
            "trafo_loading_pct": [10.0, 48.0, 12.0, 5.0],
        },
        index=idx,
    )


def test_energy_and_ratios(steps, cfg):
    k = compute(steps, cfg)
    assert k["pv_kwh"] == pytest.approx(30.0)              # 120 kW · 0.25 h
    assert k["veris_kwh"] == pytest.approx(15.0)           # 60 kW fazla · 0.25 h
    assert k["alim_kwh"] == pytest.approx(58.0)            # (190 + 42) · 0.25
    assert k["tuketim_kwh"] == pytest.approx(73.0)         # (30+190+42+30) · 0.25
    assert k["oz_tuketim_orani"] == pytest.approx(0.5)     # 15 / 30
    assert k["yenilenebilir_payi"] == pytest.approx(15 / 73)
    assert k["arac_sarj_kwh"] == pytest.approx(43.0)
    assert k["arac_sarj_puant_payi"] == pytest.approx(150 / 172)


def test_peak_cost_and_tariff_split(steps, cfg):
    k = compute(steps, cfg)
    assert k["tepe_alim_kw"] == 190 and k["tepe_alim_saati"] == "18:00"
    assert k["puant_tepe_alim_kw"] == 190
    assert k["maliyet_tl"] == pytest.approx(steps["cost_tl"].sum())
    assert k["alim_puant_kwh"] == pytest.approx(47.5)
    assert k["alim_gece_kwh"] == pytest.approx(10.5)
    assert k["alim_gunduz_kwh"] == 0
    assert k["alim_gunduz_kwh"] + k["alim_puant_kwh"] + k["alim_gece_kwh"] == pytest.approx(k["alim_kwh"])
    assert k["yuk_faktoru"] == pytest.approx(58 / 190)


def test_limits_and_grid(steps, cfg):
    k = compute(steps, cfg)
    assert k["site_siniri_asim_adim"] == 1                 # 190 > 180
    assert k["site_siniri_asim_kwh"] == pytest.approx(10 * 0.25)
    assert k["istasyon_siniri_asim_adim"] == 0             # 150 sınırı aşılmadı
    assert k["min_gerilim_pu"] == 0.94 and k["gerilim_ihlal_adim"] == 1
    assert k["max_kablo_yuklenme_pct"] == 85 and k["max_trafo_yuklenme_pct"] == 48


def test_compare_on_mock_loop_without_grid(cfg):
    index = time_index(cfg)
    s = run(cfg, mock_inputs(cfg, index), MockStation(cfg, index[0]), UncontrolledEMS(), SimpleBattery(cfg)).steps
    table = compare({"mock": s, "mock2": s}, cfg)
    assert list(table.index) == list(KPI_UNITS) and list(table.columns) == ["mock", "mock2", "birim"]
    k = table["mock"]
    assert 0 <= k["oz_tuketim_orani"] <= 1 and 0 <= k["yenilenebilir_payi"] <= 1
    assert k["maliyet_tl"] > 0
    assert math.isnan(k["min_gerilim_pu"])                 # yük akışı çalışmadıysa boş
