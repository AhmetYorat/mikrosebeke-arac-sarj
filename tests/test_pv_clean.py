"""PVGIS temizleme adımı (YM-1, Hafta 2). İnternete çıkmaz."""
import pandas as pd
import pytest

from microgrid.data.pvgis import LOCAL_TZ, clean

YEAR = 2023


def raw_like_pvgis():
    """Ham dosyanın biçimi: UTC kayması yüzünden 1 Ocak 03:00'te başlayıp ertesi yıla 3 saat taşar."""
    idx = pd.date_range(f"{YEAR}-01-01 03:00", periods=8760, freq="h", tz=LOCAL_TZ)
    df = pd.DataFrame(
        {"pv_kw_per_kwp": 0.5, "irradiance_w_m2": 500.0, "temp_c": 10.0, "wind_m_s": 2.0},
        index=idx,
    )
    df.index.name = "timestamp"
    return df


def test_clean_gives_full_local_year():
    df, report = clean(raw_like_pvgis(), YEAR)
    assert len(df) == 8760
    assert df.index[0] == pd.Timestamp(f"{YEAR}-01-01 00:00", tz=LOCAL_TZ)
    assert df.index[-1] == pd.Timestamp(f"{YEAR}-12-31 23:00", tz=LOCAL_TZ)
    assert report["yila_kaydirilan"] == 3
    assert not df.isna().any().any()


def test_clean_fills_short_gaps_and_fixes_bad_values():
    raw = raw_like_pvgis()
    raw = raw.drop(raw.index[100:102])                       # 2 saatlik boşluk
    raw = pd.concat([raw, raw.iloc[[200]]])                  # tekrar eden saat
    raw.iloc[300, raw.columns.get_loc("pv_kw_per_kwp")] = -0.01
    raw.iloc[400, raw.columns.get_loc("irradiance_w_m2")] = 0.0  # ışınım yok ama üretim var

    df, report = clean(raw, YEAR)
    assert len(df) == 8760
    assert report == {
        "tekrar_eden": 1, "yila_kaydirilan": 3, "eksik": 2,
        "doldurulamayan": 0, "negatif": 1, "isinimsiz_uretim": 1,
    }
    assert (df["pv_kw_per_kwp"] >= 0).all()
    assert df["pv_kw_per_kwp"].iloc[103] == pytest.approx(0.5)   # boşluk komşu değerlerle doldu


def test_clean_rejects_long_gap():
    raw = raw_like_pvgis()
    raw = raw.drop(raw.index[1000:1010])
    with pytest.raises(ValueError):
        clean(raw, YEAR)
