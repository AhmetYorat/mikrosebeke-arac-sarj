"""Veri katmanı (YM-1) testleri. İnternete çıkmaz; API cevaplarının küçük örnekleriyle çalışır."""
import pandas as pd

from microgrid.config import load_config
from microgrid.data.acn import sessions_to_frame
from microgrid.data.pvgis import parse_hourly


def test_site_and_tariff_filled():
    cfg = load_config()
    assert cfg["site"]["latitude"] is not None and cfg["site"]["longitude"] is not None
    prices = {p["name"]: p["price_tl_per_kwh"] for p in cfg["tariff"]["periods"]}
    assert all(v is not None and v > 0 for v in prices.values())
    # Akıllı şarjın anlamı buna dayanıyor: gece en ucuz, puant en pahalı.
    assert prices["gece"] < prices["gunduz"] < prices["puant"]


def test_tariff_periods_cover_24_hours():
    hours = set()
    for p in load_config()["tariff"]["periods"]:
        start, end = p["start"], p["end"]
        span = range(start, end) if start < end else [*range(start, 24), *range(0, end)]
        assert hours.isdisjoint(span), "dilimler çakışıyor"
        hours.update(span)
    assert hours == set(range(24))


def test_pvgis_parse_converts_units_and_timezone():
    raw = {
        "outputs": {
            "hourly": [
                {"time": "20230621:0910", "P": 650.0, "G(i)": 800.0, "T2m": 25.0, "WS10m": 2.0, "H_sun": 60, "Int": 0},
                {"time": "20230621:2110", "P": 0.0, "G(i)": 0.0, "T2m": 18.0, "WS10m": 1.0, "H_sun": 0, "Int": 0},
            ]
        }
    }
    df = parse_hourly(raw)
    assert df["pv_kw_per_kwp"].iloc[0] == 0.65            # W -> kW
    assert df.index[0].hour == 12                          # 09 UTC -> 12 Türkiye saati
    assert df.index[1].hour == 0 and df.index[1].day == 22  # gece yarısını geçince gün de değişir


def test_acn_sessions_to_frame():
    sessions = [
        {
            "sessionID": "s1",
            "connectionTime": "Wed, 01 May 2019 15:00:00 GMT",
            "disconnectTime": "Wed, 01 May 2019 23:30:00 GMT",
            "kWhDelivered": 12.5,
            "timezone": "America/Los_Angeles",
            "userInputs": [{"kWhRequested": 15.0}],
        },
        {
            "sessionID": "s2",
            "connectionTime": "Wed, 01 May 2019 16:00:00 GMT",
            "disconnectTime": "Wed, 01 May 2019 18:00:00 GMT",
            "kWhDelivered": 5.0,
            "timezone": "America/Los_Angeles",
            "userInputs": None,
        },
    ]
    df = sessions_to_frame(sessions)
    assert df.loc[0, "arrival_hour"] == 8.0   # 15:00 UTC = 08:00 PDT
    assert df.loc[0, "duration_h"] == 8.5
    assert pd.isna(df.loc[1, "kwh_requested"])
