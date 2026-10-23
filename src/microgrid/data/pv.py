"""PV modeli (YM-1): ışınımdan kurulu güce göre üretim.

Ana kaynak PVGIS'in kendi hesapladığı 1 kWp üretimidir (pv_kw_per_kwp); modül sıcaklığı,
açı ve spektrum etkilerini içerir. Kurulu güce ölçeklemek yeterlidir:
    pv_kw = installed_kw * pv_kw_per_kwp

pv_from_irradiance() ise aynı sonucu ışınım ve sıcaklıktan basit fiziksel modelle hesaplar.
İki amaçla var: (1) PVGIS sonucunun mantıklı olduğunu bağımsız olarak kontrol etmek,
(2) PVGIS'te olmayan durumlar için üretim hesaplamak (ör. D3: bulut geçişinde ışınım düşüşü,
Hafta 7: ışınım tahmininden ertesi gün üretimi).
"""
import pandas as pd

from microgrid.config import load_config
from microgrid.data import pvgis

# Tipik kristal silisyum panel değerleri
GAMMA_PER_C = -0.004   # güç sıcaklık katsayısı: 25 °C'nin üstünde her derece için %0,4 kayıp
NOCT_C = 45.0          # nominal çalışma hücre sıcaklığı (800 W/m², 20 °C hava)


def pv_from_irradiance(irradiance_w_m2, temp_c, installed_kw, loss_percent=14.0):
    """Panel düzlemi ışınımı (W/m²) ve hava sıcaklığından (°C) AC üretim (kW).

    pv = kWp × G/1000 × (1 + γ (T_hücre − 25)) × (1 − kayıp)
    T_hücre = T_hava + G/800 × (NOCT − 20)
    """
    g = irradiance_w_m2
    t_cell = temp_c + g / 800.0 * (NOCT_C - 20.0)
    p = installed_kw * g / 1000.0 * (1 + GAMMA_PER_C * (t_cell - 25.0)) * (1 - loss_percent / 100.0)
    return p.clip(lower=0) if hasattr(p, "clip") else max(p, 0.0)


def hourly_pv_kw(cfg=None) -> pd.Series:
    """Temiz PVGIS verisinden kurulu güce ölçeklenmiş saatlik üretim (kW, Türkiye saati)."""
    cfg = cfg or load_config()
    path = pvgis.processed_path(cfg)
    if not path.exists():
        raise FileNotFoundError(f"{path} yok. Önce indir: python -m microgrid.data.pvgis")
    df = pvgis.load(path)
    return (df["pv_kw_per_kwp"] * cfg["pv"]["installed_kw"]).rename("pv_kw")
