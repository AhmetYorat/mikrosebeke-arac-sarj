"""Sabit yük profilleri (YM-1, Hafta 2). İnternete çıkmaz; BDEW profili demandlib içinde gelir."""
import pandas as pd
import pytest

from microgrid.config import load_config
from microgrid.data.loads import average_day, build


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def loads(cfg):
    return build(cfg)


def test_hourly_full_year(loads, cfg):
    year = cfg["loads"]["year"]
    assert len(loads) == 8760
    assert loads.index[0] == pd.Timestamp(f"{year}-01-01 00:00", tz="Europe/Istanbul")
    assert not loads.isna().any().any()
    assert (loads > 0).all().all()


def test_annual_energy_matches_config(loads, cfg):
    # Saatlik ortalama güç (kW) x 1 saat = kWh; yıllık toplam config'deki tüketime eşit olmalı.
    res = cfg["loads"]["residential"]
    assert loads["residential_kw"].sum() == pytest.approx(res["households"] * res["kwh_per_household"], rel=1e-3)
    assert loads["commercial_kw"].sum() == pytest.approx(cfg["loads"]["commercial"]["annual_kwh"], rel=1e-3)


def test_profile_shapes(loads):
    day = average_day(loads, weekdays=[0, 1, 2, 3, 4])
    # Konut tepe yükü akşam, ticari tepe yükü mesai saatlerinde.
    assert 17 <= day["residential_kw"].idxmax() <= 22
    assert 8 <= day["commercial_kw"].idxmax() <= 17
    # Ticari yük hafta sonu düşer.
    weekend = average_day(loads, weekdays=[6])
    assert weekend["commercial_kw"].sum() < day["commercial_kw"].sum()


def test_turkish_holiday_behaves_like_sunday(loads):
    # 19 Mayıs 2023 cuma: resmî tatil. Bir önceki cumaya göre ticari tüketim belirgin düşük olmalı.
    holiday = loads.loc["2023-05-19", "commercial_kw"].sum()
    normal_friday = loads.loc["2023-05-12", "commercial_kw"].sum()
    assert holiday < 0.8 * normal_friday
