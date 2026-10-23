"""Sabit yük profilleri: konut ve ticari, saatlik (YM-1).

Şekil BDEW standart yük profillerinden gelir (demandlib paketi):
    H0: konut, G0: genel ticari
Profiller 15 dakikalıktır; hafta içi / cumartesi / pazar-tatil ve kış / yaz / geçiş dönemi
ayrımı vardır. Konut profilinde (h0_dyn) mevsime göre değişen dinamik katsayı uygulanır.
Resmî tatiller Türkiye takviminden verilir; bu günler pazar gibi davranır.

Profil 1000 kWh/yıl'a normalize edilmiştir; config'deki yıllık tüketimle ölçeklenir.

Komut satırından:
    python -m microgrid.data.loads
"""
from pathlib import Path

import holidays
import pandas as pd
from demandlib import bdew

from microgrid.config import REPO_ROOT, load_config

PROCESSED_DIR = REPO_ROOT / "data" / "processed"
LOCAL_TZ = "Europe/Istanbul"


def turkish_holidays(year) -> dict:
    return dict(holidays.Turkey(years=year))


def bdew_profiles(year, residential_kwh, commercial_kwh) -> pd.DataFrame:
    """15 dakikalık BDEW profillerini verilen yıllık tüketimlere ölçekler (kW)."""
    slp = bdew.ElecSlp(year, holidays=turkish_holidays(year))
    df = slp.get_scaled_power_profiles({"h0_dyn": residential_kwh, "g0": commercial_kwh})
    return df.rename(columns={"h0_dyn": "residential_kw", "g0": "commercial_kw"})


def build(cfg=None) -> pd.DataFrame:
    """Config'e göre saatlik konut, ticari ve toplam yük tablosu (kW, Türkiye saati).

    Saatlik değer, o saatin dört 15 dakikalık adımının ortalama gücüdür; yani kW değeri
    aynı zamanda o saatteki kWh'tir.
    """
    cfg = cfg or load_config()
    loads = cfg["loads"]
    res = loads["residential"]
    df = bdew_profiles(
        loads["year"],
        res["households"] * res["kwh_per_household"],
        loads["commercial"]["annual_kwh"],
    )
    hourly = df.resample("h").mean()
    # Türkiye 2016'dan beri yaz saati uygulamıyor; BDEW zaman damgaları doğrudan yerel saat kabul edilir.
    hourly.index = hourly.index.tz_localize(LOCAL_TZ)
    hourly.index.name = "timestamp"
    hourly["total_kw"] = hourly["residential_kw"] + hourly["commercial_kw"]
    return hourly


def processed_path(cfg) -> Path:
    return PROCESSED_DIR / f"yuk_profilleri_{cfg['loads']['year']}.csv"


def save(cfg=None) -> Path:
    cfg = cfg or load_config()
    out = processed_path(cfg)
    out.parent.mkdir(parents=True, exist_ok=True)
    build(cfg).to_csv(out)
    return out


def load(path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col="timestamp")
    df.index = pd.to_datetime(df.index, utc=True).tz_convert(LOCAL_TZ)
    return df


def average_day(df, months=None, weekdays=None) -> pd.DataFrame:
    """Seçilen ay ve günlerin saat bazında ortalaması: 24 satırlık temsili gün.

    months: [6] gibi ay listesi; weekdays: 0=pazartesi ... 6=pazar. Boş bırakılırsa hepsi.
    PV tablosu için de çalışır.
    """
    sel = df
    if months is not None:
        sel = sel[sel.index.month.isin(months)]
    if weekdays is not None:
        sel = sel[sel.index.dayofweek.isin(weekdays)]
    day = sel.groupby(sel.index.hour).mean()
    day.index.name = "hour"
    return day


if __name__ == "__main__":
    path = save()
    df = load(path)
    print(f"Yazıldı: {path}")
    print(f"{len(df)} saat")
    print(f"Yıllık tüketim (MWh): {(df.sum() / 1000).round(1).to_dict()}")
    print(f"Tepe yük (kW): {df.max().round(1).to_dict()}")
