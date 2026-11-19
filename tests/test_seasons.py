"""Hafta 6 (YM-1): mevsim profilleri, temsili günler, yıla genişletme, hafta/yıl girdisi.

Takvim testleri veri istemez; diğerleri data/processed/ dosyaları yoksa atlanır.
"""
import copy

import pandas as pd
import pytest

from microgrid.config import load_config
from microgrid.data import loads as load_profiles
from microgrid.data import pvgis, seasons
from microgrid.data.inputs import INPUT_COLUMNS, build_inputs
from microgrid.kpi import annualize, compute
from microgrid.sim.loop import run
from microgrid.sim.mocks import MockStation, SimpleBattery, UncontrolledEMS

TZ = "Europe/Istanbul"


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def data(cfg):
    if not (pvgis.processed_path(cfg).exists() and load_profiles.processed_path(cfg).exists()):
        pytest.skip("data/processed/ dosyaları yok (python -m microgrid.data)")


def test_day_type_holidays_count_as_weekend():
    idx = pd.DatetimeIndex(["2023-10-29", "2023-10-30", "2023-10-28", "2023-04-21"])  # Cumhuriyet B., pzt, cmt, bayram
    assert list(seasons.day_type_of(idx)) == ["hafta_sonu", "hafta_ici", "hafta_sonu", "hafta_sonu"]
    assert list(seasons.season_of([12, 3, 6, 11])) == ["kis", "ilkbahar", "yaz", "sonbahar"]


@pytest.mark.parametrize("n", [1, 2, 3])
def test_calendar_covers_year(cfg, data, n):
    c = {**cfg, "inputs": {**cfg["inputs"], "sky_classes": n}}
    weights = seasons.calendar(c)
    assert weights.sum() == 365
    assert len(weights) == 8 * n
    # Gökyüzü sınıfları dengeli: aynı mevsim ve gün tipinde gün sayıları en fazla 1 farklı
    spread = weights.groupby(level=["mevsim", "gun_tipi"]).agg(lambda s: s.max() - s.min())
    assert spread.max() <= 1


def test_profiles_keep_annual_energy(cfg, data):
    profs = seasons.profiles(cfg)
    weights = seasons.calendar(cfg)
    daily = profs.groupby(level=seasons.KEY_NAMES).sum()          # temsili günün kWh'i
    annual = daily.mul(weights, axis=0).sum()
    pv = pvgis.load(pvgis.processed_path(cfg))["pv_kw_per_kwp"].sum() * cfg["pv"]["installed_kw"]
    load = load_profiles.load(load_profiles.processed_path(cfg))["total_kw"].sum()
    assert annual["pv_kw"] == pytest.approx(pv, rel=1e-6)
    assert annual["base_load_kw"] == pytest.approx(load, rel=1e-6)
    # Güneşli gün bulutlu günden fazla üretir
    assert daily.loc[("yaz", "hafta_ici", "gunesli"), "pv_kw"] > daily.loc[("yaz", "hafta_ici", "bulutlu"), "pv_kw"]


def test_representative_inputs_contract(cfg, data):
    key = ("kis", "hafta_ici", "orta")
    inp = seasons.representative_inputs(cfg, key)
    assert list(inp.columns) == INPUT_COLUMNS and len(inp) == 96
    assert inp.index[0].hour == 12 and inp.index[0].month in seasons.SEASONS["kis"]
    assert not inp.isna().any().any()


def test_annualize_weights_and_ratios(cfg):
    idx = pd.date_range(pd.Timestamp("2023-06-21 12:00", tz=TZ), periods=4, freq="6h")
    day = pd.DataFrame(
        {"pv_kw": [40.0, 0, 0, 0], "base_load_kw": 20.0, "ev_kw": [0, 50.0, 0, 0], "bess_kw": 0.0,
         "price_tl_per_kwh": 4.0, "min_vm_pu": 0.98, "max_line_loading_pct": 30.0, "trafo_loading_pct": 10.0},
        index=idx,
    )
    day["grid_kw"] = day.base_load_kw + day.ev_kw - day.pv_kw
    day["cost_tl"] = day.grid_kw.clip(lower=0) * day.price_tl_per_kwh * 0.25
    a = annualize({"a": day, "b": day}, {"a": 2, "b": 3}, cfg)
    one = compute(day, cfg)
    assert a["maliyet_tl"] == pytest.approx(5 * one["maliyet_tl"])
    assert a["alim_kwh"] == pytest.approx(5 * one["alim_kwh"])
    assert a["yenilenebilir_payi"] == pytest.approx(one["yenilenebilir_payi"])
    assert a["tepe_alim_kw"] == one["tepe_alim_kw"]


def test_week_and_year_inputs_with_actual_data(cfg, data):
    c = copy.deepcopy(cfg)
    c["inputs"]["mode"] = "actual"
    week = pd.date_range(pd.Timestamp("2023-12-18 12:00", tz=TZ), periods=7 * 96, freq="15min")
    inp = build_inputs(c, week)
    assert len(inp) == 7 * 96 and not inp.isna().any().any()
    # Tam yıl, araçsız döngü: girdi enerjisi korunuyor
    year = pd.date_range(pd.Timestamp("2023-01-01", tz=TZ), periods=365 * 96, freq="15min")
    c["vehicles"]["count"] = 0
    steps = run(c, build_inputs(c, year), MockStation(c, year[0]), UncontrolledEMS(), SimpleBattery(c)).steps
    k = compute(steps, c)
    assert k["tuketim_kwh"] == pytest.approx(200_000, rel=0.01)
    assert k["pv_kwh"] == pytest.approx(133_000, rel=0.02)
