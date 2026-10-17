"""PVGIS'ten saatlik güneş ışınımı ve PV üretimi indirir (YM-1).

PVGIS (Avrupa Komisyonu JRC) ücretsizdir, kayıt veya anahtar istemez.
1 kWp'lik sistem için sorgulanır; böylece kurulu güç değişince yeniden indirmeye gerek kalmaz:
    pv_kw = installed_kw * pv_kw_per_kwp

Komut satırından (config'deki konum ve yıl için; indirir ve temizler):
    python -m microgrid.data.pvgis
"""
import json
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

from microgrid.config import REPO_ROOT, load_config

PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
LOCAL_TZ = "Europe/Istanbul"


def fetch_hourly(lat, lon, year, tilt_deg, azimuth_deg, loss_percent, timeout=60) -> dict:
    """PVGIS seriescalc çağrısı; ham JSON'u döndürür."""
    params = {
        "lat": lat,
        "lon": lon,
        "startyear": year,
        "endyear": year,
        "pvcalculation": 1,
        "peakpower": 1,          # 1 kWp: çıktı W/kWp olur
        "loss": loss_percent,
        "angle": tilt_deg,
        "aspect": azimuth_deg,   # PVGIS: 0 = güney, -90 = doğu, 90 = batı
        "outputformat": "json",
    }
    url = f"{PVGIS_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.load(resp)


def parse_hourly(raw: dict) -> pd.DataFrame:
    """Ham PVGIS JSON'unu saatlik tabloya çevirir.

    PVGIS zamanları UTC ve "20230101:0010" biçimindedir; ":10" saatin temsil anıdır.
    Saate yuvarlayıp Türkiye saatine (UTC+3) çeviriyoruz.
    """
    df = pd.DataFrame(raw["outputs"]["hourly"])
    ts = pd.to_datetime(df["time"], format="%Y%m%d:%H%M", utc=True).dt.floor("h")
    out = pd.DataFrame(
        {
            "pv_kw_per_kwp": df["P"] / 1000.0,      # W -> kW (1 kWp için)
            "irradiance_w_m2": df["G(i)"],          # panel düzlemine gelen ışınım
            "temp_c": df["T2m"],
            "wind_m_s": df["WS10m"],
        }
    )
    out.index = pd.DatetimeIndex(ts.dt.tz_convert(LOCAL_TZ), name="timestamp")
    return out


def download(cfg=None, out_dir=RAW_DIR) -> Path:
    """Config'deki konum için veriyi indirir; ham JSON ve temiz CSV'yi data/raw/ altına yazar."""
    cfg = cfg or load_config()
    site, pv = cfg["site"], cfg["pv"]
    raw = fetch_hourly(
        site["latitude"], site["longitude"], pv["pvgis_year"],
        pv["tilt_deg"], pv["azimuth_deg"], pv["loss_percent"],
    )
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"pvgis_{site['name'].lower()}_{pv['pvgis_year']}"
    (out_dir / f"{stem}.json").write_text(json.dumps(raw), encoding="utf-8")
    csv_path = out_dir / f"{stem}.csv"
    parse_hourly(raw).to_csv(csv_path)
    return csv_path


def load(path) -> pd.DataFrame:
    """download() veya save_clean() ile yazılan CSV'yi okur (indeks Türkiye saatinde)."""
    df = pd.read_csv(path, index_col="timestamp")
    df.index = pd.to_datetime(df.index, utc=True).tz_convert(LOCAL_TZ)
    return df


def clean(df, year, max_gap_hours=3) -> tuple[pd.DataFrame, dict]:
    """Ham saatlik tabloyu yerel saatte tam bir takvim yılına (8760 saat) getirir.

    UTC -> Türkiye saati çevrimi yüzünden ham dosya 1 Ocak 03:00'te başlar ve son 3 saat
    ertesi yıla taşar. Taşan saatler yılın başındaki boşluğa kaydırılır: ikisi de 1 Ocak
    gece yarısı civarı, PV zaten sıfır, sıcaklık/rüzgâr farkı ihmal edilebilir.

    Ayrıca: tekrar eden saatler atılır, kısa boşluklar (<= max_gap_hours) doğrusal doldurulur,
    negatif değerler ve ışınım yokken görünen üretim sıfırlanır.
    Dönen rapor sözlüğü hangi düzeltmenin kaç satıra uygulandığını söyler.
    """
    df = df.sort_index()
    report = {"tekrar_eden": int(df.index.duplicated().sum())}
    df = df[~df.index.duplicated()]

    hours = pd.date_range(f"{year}-01-01", f"{year + 1}-01-01", freq="h", inclusive="left", tz=LOCAL_TZ)
    overflow = df[df.index >= hours[-1] + pd.Timedelta(hours=1)]
    df = df[df.index.year == year]
    head_gap = hours[hours < df.index.min()] if len(df) else hours
    n = min(len(overflow), len(head_gap))
    if n:
        moved = overflow.iloc[:n].copy()
        moved.index = head_gap[:n]
        df = pd.concat([moved, df])
    report["yila_kaydirilan"] = int(n)

    df = df.reindex(hours)
    report["eksik"] = int(df.isna().any(axis=1).sum())
    df = df.interpolate(limit=max_gap_hours, limit_area="inside").ffill(limit=max_gap_hours).bfill(limit=max_gap_hours)
    report["doldurulamayan"] = int(df.isna().any(axis=1).sum())
    if report["doldurulamayan"]:
        raise ValueError(f"{report['doldurulamayan']} saat {max_gap_hours} saatten uzun boşlukta, veriyi yeniden indir")

    neg = (df[["pv_kw_per_kwp", "irradiance_w_m2"]] < 0).any(axis=1)
    no_sun = (df["irradiance_w_m2"] <= 0) & (df["pv_kw_per_kwp"] > 0)
    report["negatif"] = int(neg.sum())
    report["isinimsiz_uretim"] = int(no_sun.sum())
    df[["pv_kw_per_kwp", "irradiance_w_m2"]] = df[["pv_kw_per_kwp", "irradiance_w_m2"]].clip(lower=0)
    df.loc[no_sun, "pv_kw_per_kwp"] = 0.0

    df.index.name = "timestamp"
    return df, report


def processed_path(cfg) -> Path:
    return PROCESSED_DIR / f"pv_{cfg['site']['name'].lower()}_{cfg['pv']['pvgis_year']}.csv"


def save_clean(cfg=None, raw_csv=None) -> tuple[Path, dict]:
    """Ham CSV'yi temizleyip data/processed/ altına yazar. Diğer modüller bu dosyayı kullanır."""
    cfg = cfg or load_config()
    year = cfg["pv"]["pvgis_year"]
    raw_csv = raw_csv or RAW_DIR / f"pvgis_{cfg['site']['name'].lower()}_{year}.csv"
    df, report = clean(load(raw_csv), year)
    out = processed_path(cfg)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out)
    return out, report


if __name__ == "__main__":
    raw = download()
    print(f"Ham veri: {raw}")
    path, report = save_clean(raw_csv=raw)
    df = load(path)
    print(f"Temiz veri: {path}")
    print(f"Düzeltmeler: {report}")
    print(f"{len(df)} saat, yıllık üretim {df['pv_kw_per_kwp'].sum():.0f} kWh/kWp")
