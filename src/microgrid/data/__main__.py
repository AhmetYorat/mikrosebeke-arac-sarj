"""Döngünün ihtiyaç duyduğu bütün veriyi tek komutla hazırlar (YM-1):

    python -m microgrid.data

1. PVGIS'ten Bandırma saatlik verisini indirir ve temizler -> data/processed/pv_*.csv
2. Konut + ticari yük profillerini üretir                  -> data/processed/yuk_profilleri_*.csv

Dosyalar repoya girmez; repoyu yeni klonlayan herkes bir kez çalıştırır.
İnternet yalnızca PVGIS için gerekir; PV dosyası zaten varsa indirme atlanır (--yeniden ile zorlanır).
"""
import sys

from microgrid.config import load_config
from microgrid.data import loads, pvgis

cfg = load_config()
force = "--yeniden" in sys.argv

pv_path = pvgis.processed_path(cfg)
if pv_path.exists() and not force:
    print(f"PV verisi zaten var: {pv_path}")
else:
    raw = pvgis.download(cfg)
    pv_path, report = pvgis.save_clean(cfg, raw_csv=raw)
    print(f"PV verisi yazıldı: {pv_path} (düzeltmeler: {report})")

load_path = loads.save(cfg)
print(f"Yük profilleri yazıldı: {load_path}")
print("Hazır. Döngüyü çalıştır: python -m microgrid.sim")
