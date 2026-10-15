"""PVGIS'ten saatlik güneş ışınımı ve PV üretimi indirir (YM-1).

PVGIS (Avrupa Komisyonu JRC) ücretsizdir, kayıt veya anahtar istemez.
1 kWp'lik sistem için sorgulanır; böylece kurulu güç değişince yeniden indirmeye gerek kalmaz:
    pv_kw = installed_kw * pv_kw_per_kwp

Komut satırından (config'deki konum ve yıl için):
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
    """download() ile yazılan CSV'yi okur (indeks Türkiye saatinde)."""
    df = pd.read_csv(path, index_col="timestamp")
    df.index = pd.to_datetime(df.index, utc=True).tz_convert(LOCAL_TZ)
    return df


if __name__ == "__main__":
    path = download()
    df = load(path)
    print(f"Yazıldı: {path}")
    print(f"{len(df)} saat, yıllık üretim {df['pv_kw_per_kwp'].sum():.0f} kWh/kWp")
