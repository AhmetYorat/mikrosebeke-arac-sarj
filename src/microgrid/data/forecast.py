"""Ertesi gün PV ve yük tahmini (YM-1, Hafta 7). Optimizasyonlu EMS (YM-3, Senaryo 5) günü bununla planlar.

Döngü EMS'e gün başında bir tahmin tablosu verir (ems.prepare); gerçek değerler adım adım gelir.
Tahmin gerçeği bilirse ("perfect") optimizasyonun başarısı olduğundan iyi görünür. Bu modül, yalnızca
geçmiş günlerin verisini kullanan gerçekçi tahminler üretir:

    perfect      gerçek değer (karşılaştırma için üst sınır)
    persistence  dünün aynı saati
    climatology  son window_days günün aynı saatteki ortalaması; yük için yalnızca aynı gün tipinden
                 (hafta içi / cumartesi / pazar + resmî tatil, BDEW profilindeki üç tip)
    blend        persistence ve climatology karışımı (ağırlık: forecast.blend_persistence_weight)

Fiyat tahmin edilmez: üç zamanlı tarife önceden bilinir.
Veri tek yıl (2023) olduğu için yılın ilk günlerinin geçmişi yılın son günlerinden alınır (yıl döngüsel kabul edilir).

Doğruluk:  python -m microgrid.data.forecast   (yıl boyunca her gün için tahmin hatası)
"""
import numpy as np
import pandas as pd

from microgrid.config import load_config
from microgrid.data.inputs import (
    INPUT_COLUMNS, LOAD_ANCHOR_MIN, PV_ANCHOR_MIN, _interp_actual, hourly_base_load_kw,
)
from microgrid.data.loads import turkish_holidays
from microgrid.data.pv import hourly_pv_kw
from microgrid.data.tariff import price_series

METHODS = ("perfect", "persistence", "climatology", "blend")


def day_types(days: pd.DatetimeIndex) -> np.ndarray:
    """0 = hafta içi, 1 = cumartesi, 2 = pazar veya resmî tatil."""
    holidays = set()
    for year in days.year.unique():
        holidays |= set(turkish_holidays(int(year)))
    t = np.where(days.dayofweek == 5, 1, 0)
    t[(days.dayofweek == 6) | pd.Index(days.date).isin(holidays)] = 2
    return t


def _as_days(series: pd.Series) -> np.ndarray:
    """Saatlik yıllık seriyi (gün, saat) matrisine çevirir."""
    if len(series) % 24:
        raise ValueError("saatlik seri tam günlerden oluşmalı")
    return series.to_numpy().reshape(-1, 24)


def _persistence(days: np.ndarray) -> np.ndarray:
    return np.roll(days, 1, axis=0)


def _climatology(days: np.ndarray, window: int, types=None) -> np.ndarray:
    """Her gün için önceki window günün (types verilirse aynı tipteki günlerin) saatlik ortalaması."""
    n = len(days)
    out = np.empty_like(days)
    for d in range(n):
        past = []
        k = 1
        while len(past) < window and k < n:
            p = (d - k) % n
            if types is None or types[p] == types[d]:
                past.append(p)
            k += 1
        out[d] = days[past].mean(axis=0)
    return out


def hourly_forecast(cfg=None, pv_method=None, load_method=None) -> pd.DataFrame:
    """Yılın her günü için gün öncesi tahmin (saatlik, kW): pv_kw, base_load_kw.

    Yöntemler verilmezse config'teki forecast.pv_method / forecast.load_method kullanılır.
    """
    cfg = cfg or load_config()
    opts = cfg["forecast"]
    pv_method = pv_method or opts["pv_method"]
    load_method = load_method or opts["load_method"]
    window = opts["window_days"]

    pv, load = hourly_pv_kw(cfg), hourly_base_load_kw(cfg)
    types = day_types(pv.index.normalize().unique())

    def predict(series, method, by_type):
        days = _as_days(series)
        if method == "perfect":
            f = days
        elif method == "persistence":
            f = _persistence(days)
        elif method == "climatology":
            f = _climatology(days, window, types if by_type else None)
        elif method == "blend":
            w = opts["blend_persistence_weight"]
            f = w * _persistence(days) + (1 - w) * _climatology(days, window, types if by_type else None)
        else:
            raise ValueError(f"tahmin yöntemi '{method}' tanınmıyor: {', '.join(METHODS)}")
        return pd.Series(f.ravel(), index=series.index)

    return pd.DataFrame({
        "pv_kw": predict(pv, pv_method, by_type=False),     # güneş gün tipine bağlı değil
        "base_load_kw": predict(load, load_method, by_type=True),
    })


def forecast_inputs(cfg=None, index: pd.DatetimeIndex = None, hourly=None) -> pd.DataFrame:
    """EMS'in prepare() ile göreceği tahmin tablosu: build_inputs ile aynı indeks ve sütunlar.

    Tarihler veri yılında olmalı (gerçek gün simülasyonu, inputs.mode: actual).
    Temsili gün modunda (average_day) girdinin kendisi ortalama olduğundan ayrıca tahmin gerekmez.
    """
    cfg = cfg or load_config()
    hourly = hourly_forecast(cfg) if hourly is None else hourly
    return pd.DataFrame(
        {
            "pv_kw": np.clip(_interp_actual(hourly["pv_kw"], PV_ANCHOR_MIN, index), 0, None),
            "base_load_kw": _interp_actual(hourly["base_load_kw"], LOAD_ANCHOR_MIN, index),
            "price_tl_per_kwh": price_series(cfg, index).to_numpy(),
        },
        index=index,
    )[INPUT_COLUMNS]


def evaluate(cfg=None) -> pd.DataFrame:
    """Yöntemlerin yıl boyu tahmin hatası (saatlik).

    MAE ve RMSE kW; nMAE PV için kurulu güce, yük için ortalama yüke göre %; bias pozitifse fazla tahmin.
    gunluk_enerji_mae: günlük toplam enerjideki ortalama mutlak hata (kWh/gün).
    """
    cfg = cfg or load_config()
    actual = hourly_forecast(cfg, "perfect", "perfect")
    norm = {"pv_kw": cfg["pv"]["installed_kw"], "base_load_kw": actual["base_load_kw"].mean()}
    rows = []
    for method in METHODS[1:]:
        f = hourly_forecast(cfg, method, method)
        for col in ("pv_kw", "base_load_kw"):
            err = f[col] - actual[col]
            daily = err.groupby(err.index.normalize()).sum()
            rows.append({
                "degisken": col, "yontem": method,
                "mae_kw": err.abs().mean(), "rmse_kw": float(np.sqrt((err ** 2).mean())),
                "nmae_pct": 100 * err.abs().mean() / norm[col], "bias_kw": err.mean(),
                "gunluk_enerji_mae_kwh": daily.abs().mean(),
            })
    return pd.DataFrame(rows).set_index(["degisken", "yontem"])


if __name__ == "__main__":
    with pd.option_context("display.float_format", "{:.2f}".format, "display.width", 120):
        print(evaluate())
