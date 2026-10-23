"""Üç zamanlı tarife (YM-1): her zaman adımının elektrik fiyatı.

Dilimler ve fiyatlar config'teki tariff.periods içindedir (EPDK, bkz. docs/veri-kaynaklari.md).
Gece yarısını aşan dilim (gece 22–06) start > end ile yazılır.
"""
import pandas as pd


def _in_period(hour, start, end) -> bool:
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end   # gece yarısını aşan dilim


def period_at(cfg, hour) -> dict:
    """Ondalık saat (18.5 = 18:30) için geçerli tarife dilimi."""
    for p in cfg["tariff"]["periods"]:
        if _in_period(hour % 24, p["start"], p["end"]):
            return p
    raise ValueError(f"{hour} saati hiçbir tarife dilimine girmiyor; config'teki dilimleri kontrol et")


def price_at(cfg, hour) -> float:
    """Ondalık saat için fiyat (TL/kWh)."""
    return period_at(cfg, hour)["price_tl_per_kwh"]


def price_series(cfg, index: pd.DatetimeIndex) -> pd.Series:
    """Zaman indeksinin her adımı için fiyat (TL/kWh).

    Fiyat adımın başlangıç saatine göre alınır. Dilim sınırları tam saat olduğu için
    15 dakikalık bir adım hiçbir zaman iki dilime bölünmez.
    """
    hours = index.hour + index.minute / 60
    return pd.Series([price_at(cfg, h) for h in hours], index=index, name="price_tl_per_kwh")
