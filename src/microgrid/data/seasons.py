"""Mevsim profilleri ve temsili günlerden yıla genişletme (YM-1, Hafta 6).

Yıl, temsili günlerle özetlenir: 4 mevsim × 2 gün tipi × gökyüzü sınıfı.
    mevsim:    kış Ara–Oca–Şub, ilkbahar Mar–Nis–May, yaz Haz–Tem–Ağu, sonbahar Eyl–Eki–Kas
    gün tipi:  hafta içi; hafta sonu + resmî tatil (yük profilindeki gibi pazar sayılır)
    gökyüzü:   o mevsim ve gün tipindeki günler günlük PV enerjisine göre eşit gruplara bölünür
               (config inputs.sky_classes; 3 → bulutlu / orta / güneşli)
Her temsili gün, gruptaki günlerin saatlik ortalamasıdır; ağırlığı gruptaki gün sayısıdır.
Yıllık sonuç = Σ ağırlık × temsili günün sonucu (kpi.annualize).

Neden gökyüzü sınıfı: güneşli ve bulutlu günlerin ortalaması alınınca güneşli günlerin PV fazlası ile
bulutlu günlerin şebeke alımı birbirini götürür; yıllık maliyet düşük çıkar. Tam yıl simülasyonuna göre
yıllık maliyet farkı: 8 gün (sınıfsız) %−11, 16 gün (2 sınıf) %−5, 24 gün (3 sınıf) %−3
(scripts/ym1_hafta6_yillik.py).
"""
import numpy as np
import pandas as pd

from microgrid.config import load_config
from microgrid.data.inputs import hourly_base_load_kw, profile_inputs
from microgrid.data.loads import turkish_holidays
from microgrid.data.pv import hourly_pv_kw

SEASONS = {"kis": (12, 1, 2), "ilkbahar": (3, 4, 5), "yaz": (6, 7, 8), "sonbahar": (9, 10, 11)}
DAY_TYPES = ("hafta_ici", "hafta_sonu")
SKY_NAMES = {1: ["tum"], 2: ["bulutlu", "gunesli"], 3: ["bulutlu", "orta", "gunesli"]}
KEY_NAMES = ["mevsim", "gun_tipi", "gokyuzu"]


def season_of(months) -> pd.Index:
    lookup = {m: s for s, ms in SEASONS.items() for m in ms}
    return pd.Index([lookup[m] for m in months])


def day_type_of(index: pd.DatetimeIndex) -> pd.Index:
    """hafta_ici / hafta_sonu; resmî tatiller hafta sonu sayılır."""
    holidays = set()
    for year in index.year.unique():
        holidays |= set(turkish_holidays(int(year)))
    weekend = (index.dayofweek >= 5) | pd.Index(index.date).isin(holidays)
    return pd.Index(np.where(weekend, "hafta_sonu", "hafta_ici"))


def _hourly(cfg) -> pd.DataFrame:
    return pd.concat([hourly_pv_kw(cfg), hourly_base_load_kw(cfg)], axis=1)


def day_table(cfg=None, hourly=None) -> pd.DataFrame:
    """Yılın her günü için mevsim, gün tipi, gökyüzü sınıfı ve günlük PV enerjisi."""
    cfg = cfg or load_config()
    hourly = _hourly(cfg) if hourly is None else hourly
    n = cfg["inputs"]["sky_classes"]
    if n not in SKY_NAMES:
        raise ValueError(f"inputs.sky_classes {n} olamaz: 1, 2 veya 3")

    days = pd.DataFrame({"pv_kwh": hourly["pv_kw"].groupby(hourly.index.normalize()).sum()})
    days["mevsim"] = season_of(days.index.month)
    days["gun_tipi"] = day_type_of(days.index)
    # Grup içindeki sıraya göre n eşit parçaya böl (en düşük PV = bulutlu)
    rank = days.groupby(["mevsim", "gun_tipi"])["pv_kwh"].rank(method="first", pct=True)
    cls = np.minimum(np.ceil(rank * n).astype(int), n) - 1
    days["gokyuzu"] = np.array(SKY_NAMES[n])[cls]
    return days


def calendar(cfg=None, days=None) -> pd.Series:
    """Her temsili günün ağırlığı: yılda kaç gün (toplam 365)."""
    days = day_table(cfg) if days is None else days
    return days.groupby(KEY_NAMES).size().rename("gun_sayisi")


def profiles(cfg=None) -> pd.DataFrame:
    """Temsili günlerin 24 saatlik PV ve sabit yük profilleri (kW).

    Satır indeksi (mevsim, gün tipi, gökyüzü, saat); sütunlar pv_kw, base_load_kw.
    """
    cfg = cfg or load_config()
    hourly = _hourly(cfg)
    days = day_table(cfg, hourly)
    keys = days.loc[hourly.index.normalize(), KEY_NAMES].set_index(hourly.index)
    keys["saat"] = hourly.index.hour
    return hourly.groupby([keys[c] for c in [*KEY_NAMES, "saat"]]).mean()


def representative_index(cfg, key, days=None) -> pd.DatetimeIndex:
    """Temsili günün simülasyon adımları. Tarih etiket içindir: gruptaki, PV'si grup ortalamasına en yakın
    gün seçilir; pencere o gün öğlen başlar ve horizon_hours sürer."""
    days = day_table(cfg) if days is None else days
    group = days[(days[KEY_NAMES] == list(key)).all(axis=1)]
    day = (group["pv_kwh"] - group["pv_kwh"].mean()).abs().idxmin()
    sim = cfg["simulation"]
    start = day.tz_localize(None).tz_localize(sim.get("timezone", "Europe/Istanbul")) + pd.Timedelta(hours=12)
    n = int(sim["horizon_hours"] * 60 / sim["step_minutes"])
    return pd.date_range(start, periods=n, freq=f"{sim['step_minutes']}min", name="timestamp")


def representative_inputs(cfg, key, profs=None, days=None) -> pd.DataFrame:
    """Temsili günün döngü girdisi (build_inputs ile aynı sütunlar)."""
    profs = profiles(cfg) if profs is None else profs
    day = profs.loc[tuple(key)]
    return profile_inputs(cfg, representative_index(cfg, key, days), day["pv_kw"], day["base_load_kw"])
