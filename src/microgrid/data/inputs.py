"""Döngüye giren girdi tablosu (YM-1): build_inputs(cfg, index).

Arayüz sözleşmesi (docs/arayuz-sozlesmesi.md, YM-1 bölümü):
    indeks: simülasyon zaman adımları (time_index(cfg), 15 dk, Türkiye saati)
    sütunlar: pv_kw (kW), base_load_kw (kW), price_tl_per_kwh (TL/kWh)

Saatlik veriden 15 dakikaya doğrusal ara değerleme burada yapılır. Güç anlık değerdir:
saatlik 40 kW, 15 dakikalık adımda da ~40 kW'tır (4'e bölünmez).

Her saatlik değer, temsil ettiği ana yerleştirilip ara değerlenir:
    PV:  PVGIS değeri saatin 10. dakikasındaki güneş konumuyla hesaplanır -> HH:10
    Yük: saatlik değer o saatin ortalaması -> saatin ortası, HH:30
Böylece PV eğrisi kaymaz ve günlük enerji korunur.

İki çalışma şekli (config: inputs.mode):
    average_day: her adımın ayına göre o ayın ortalama günü (ekip kararı: Haziran ve Aralık,
                 hafta içi). Hangi ay olduğu simulation.start tarihinden gelir.
    actual:      verideki gerçek tarihler (ör. bulutlu bir gün). Tarihler veri yılında olmalı.
"""
import numpy as np
import pandas as pd

from microgrid.config import load_config
from microgrid.data import loads as load_profiles
from microgrid.data.loads import average_day
from microgrid.data.pv import hourly_pv_kw
from microgrid.data.tariff import price_series
from microgrid.interfaces import INPUT_COLUMNS

PV_ANCHOR_MIN = 10
LOAD_ANCHOR_MIN = 30


def hourly_base_load_kw(cfg) -> pd.Series:
    """Saatlik sabit yük: daireler + ortak alan + dükkânlar (EM-1 kararı: total_kw)."""
    path = load_profiles.processed_path(cfg)
    if not path.exists():
        raise FileNotFoundError(f"{path} yok. Önce üret: python -m microgrid.data.loads")
    return load_profiles.load(path)["total_kw"].rename("base_load_kw")


def _interp_day(day: pd.Series, anchor_min, index) -> np.ndarray:
    """24 saatlik ortalama günü adımlara çevirir. Gün döngüsel: 23:30'dan 00:30'a geçiş de doğrusal."""
    x = day.index.to_numpy() + anchor_min / 60
    hours = index.hour + index.minute / 60
    return np.interp(hours, x, day.to_numpy(), period=24)


def _interp_actual(series: pd.Series, anchor_min, index) -> np.ndarray:
    """Saatlik gerçek seriyi adımlara çevirir; adımlar verinin kapsadığı aralıkta olmalı."""
    src = series.index + pd.to_timedelta(anchor_min, unit="min")
    if index[0] < src[0] - pd.to_timedelta(1, unit="h") or index[-1] > src[-1] + pd.to_timedelta(1, unit="h"):
        raise ValueError(
            f"{index[0]} – {index[-1]} veri aralığının ({series.index[0]} – {series.index[-1]}) dışında. "
            "inputs.mode: average_day kullan ya da simulation.start'ı veri yılına çek."
        )
    return np.interp(index.asi8, src.asi8, series.to_numpy())


def build_inputs(cfg=None, index: pd.DatetimeIndex = None) -> pd.DataFrame:
    """Döngünün girdi tablosu: her adım için PV, sabit yük ve fiyat."""
    cfg = cfg or load_config()
    opts = cfg["inputs"]
    pv_h, load_h = hourly_pv_kw(cfg), hourly_base_load_kw(cfg)

    if opts["mode"] == "average_day":
        weekdays = list(range(5)) if opts["weekdays_only"] else None
        pv = np.empty(len(index))
        load = np.empty(len(index))
        for month in index.month.unique():
            mask = index.month == month
            pv[mask] = _interp_day(average_day(pv_h.to_frame(), [month], weekdays)["pv_kw"], PV_ANCHOR_MIN, index[mask])
            load[mask] = _interp_day(
                average_day(load_h.to_frame(), [month], weekdays)["base_load_kw"], LOAD_ANCHOR_MIN, index[mask]
            )
    elif opts["mode"] == "actual":
        pv = _interp_actual(pv_h, PV_ANCHOR_MIN, index)
        load = _interp_actual(load_h, LOAD_ANCHOR_MIN, index)
    else:
        raise ValueError(f"inputs.mode '{opts['mode']}' tanınmıyor: average_day | actual")

    return pd.DataFrame(
        {
            "pv_kw": np.clip(pv, 0, None),
            "base_load_kw": load,
            "price_tl_per_kwh": price_series(cfg, index).to_numpy(),
        },
        index=index,
    )[INPUT_COLUMNS]
