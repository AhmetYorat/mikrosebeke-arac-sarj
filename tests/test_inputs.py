"""Hafta 3 (YM-1): tarife, PV modeli ve döngü girdisi (build_inputs).

Tarife ve PV modeli testleri veri dosyası istemez. build_inputs testleri data/processed/ altındaki
dosyaları kullanır; dosyalar yoksa atlanır (önce: python -m microgrid.data.pvgis && python -m microgrid.data.loads).
"""
import numpy as np
import pandas as pd
import pytest

from microgrid.config import load_config
from microgrid.data import loads as load_profiles
from microgrid.data import pvgis
from microgrid.data.inputs import INPUT_COLUMNS, build_inputs
from microgrid.data.pv import pv_from_irradiance
from microgrid.data.tariff import price_at, price_series

TZ = "Europe/Istanbul"


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def day_index(start, step_minutes=15, hours=24):
    # YM-4'ün time_index(cfg) fonksiyonuyla aynı biçim: öğlen başlayan 24 saat
    return pd.date_range(pd.Timestamp(start, tz=TZ), periods=hours * 60 // step_minutes, freq=f"{step_minutes}min")


# --- Tarife -----------------------------------------------------------------

def test_tariff_period_boundaries(cfg):
    prices = {p["name"]: p["price_tl_per_kwh"] for p in cfg["tariff"]["periods"]}
    assert price_at(cfg, 5.75) == prices["gece"]
    assert price_at(cfg, 6.0) == prices["gunduz"]
    assert price_at(cfg, 16.75) == prices["gunduz"]
    assert price_at(cfg, 17.0) == prices["puant"]
    assert price_at(cfg, 21.75) == prices["puant"]
    assert price_at(cfg, 22.0) == prices["gece"]
    assert price_at(cfg, 0.0) == prices["gece"]


def test_price_series_step_counts(cfg):
    s = price_series(cfg, day_index("2023-06-21 12:00"))
    counts = s.value_counts()
    prices = {p["name"]: p["price_tl_per_kwh"] for p in cfg["tariff"]["periods"]}
    # 15 dk adım: gündüz 11 saat = 44, puant 5 saat = 20, gece 8 saat = 32 adım
    assert counts[prices["gunduz"]] == 44
    assert counts[prices["puant"]] == 20
    assert counts[prices["gece"]] == 32


# --- PV modeli ----------------------------------------------------------------

def test_pv_from_irradiance_stc():
    # Standart koşul (1000 W/m², hücre 25 °C) ve kayıpsız: kurulu güç kadar
    t_air_for_25c_cell = 25 - 1000 / 800 * (45 - 20)
    assert pv_from_irradiance(1000.0, t_air_for_25c_cell, 100, loss_percent=0) == pytest.approx(100)
    # Gece üretim yok, sıcakta verim düşer
    assert pv_from_irradiance(0.0, 20.0, 100) == 0
    assert pv_from_irradiance(800.0, 35.0, 100) < pv_from_irradiance(800.0, 5.0, 100)


# --- build_inputs (veri dosyası gerekir) ---------------------------------------

@pytest.fixture(scope="module")
def processed(cfg):
    if not (pvgis.processed_path(cfg).exists() and load_profiles.processed_path(cfg).exists()):
        pytest.skip("data/processed/ dosyaları yok")


def test_build_inputs_contract(cfg, processed):
    index = day_index("2023-06-21 12:00")
    df = build_inputs(cfg, index)
    assert list(df.columns) == INPUT_COLUMNS
    assert df.index.equals(index)
    assert not df.isna().any().any()
    assert (df["pv_kw"] >= 0).all() and (df["base_load_kw"] > 0).all()
    assert df["pv_kw"].max() <= cfg["pv"]["installed_kw"]
    # Gece PV yok
    assert df.loc[df.index.hour.isin([0, 1, 2, 3]), "pv_kw"].max() == 0


def test_build_inputs_preserves_daily_energy(cfg, processed):
    # 15 dakikalık seriye çevirmek günlük enerjiyi (kWh) değiştirmemeli
    df = build_inputs(cfg, day_index("2023-06-21 12:00"))
    pv_h = pvgis.load(pvgis.processed_path(cfg))["pv_kw_per_kwp"] * cfg["pv"]["installed_kw"]
    load_h = load_profiles.load(load_profiles.processed_path(cfg))["total_kw"]
    june_weekdays = lambda s: load_profiles.average_day(s.to_frame(), [6], list(range(5))).iloc[:, 0].sum()
    assert df["pv_kw"].sum() * 0.25 == pytest.approx(june_weekdays(pv_h), rel=0.02)
    assert df["base_load_kw"].sum() * 0.25 == pytest.approx(june_weekdays(load_h), rel=0.02)


def test_build_inputs_month_follows_start_date(cfg, processed):
    june = build_inputs(cfg, day_index("2023-06-21 12:00"))
    december = build_inputs(cfg, day_index("2023-12-20 12:00"))
    assert june["pv_kw"].sum() > 2 * december["pv_kw"].sum()


def test_build_inputs_actual_mode(cfg, processed):
    cfg_actual = {**cfg, "inputs": {**cfg["inputs"], "mode": "actual"}}
    df = build_inputs(cfg_actual, day_index("2023-06-21 12:00"))
    assert not df.isna().any().any()
    with pytest.raises(ValueError):
        build_inputs(cfg_actual, day_index("2030-06-21 12:00"))


def test_hourly_to_15min_is_linear_not_steps(cfg, processed):
    # Ara değerleme doğrusal: saat içinde art arda adımlar aynı değeri tekrar etmemeli (gündüz PV)
    df = build_inputs(cfg, day_index("2023-06-21 12:00"))
    noon = df.loc[(df.index.hour >= 9) & (df.index.hour < 16), "pv_kw"].to_numpy()
    assert (np.abs(np.diff(noon)) > 1e-6).all()
