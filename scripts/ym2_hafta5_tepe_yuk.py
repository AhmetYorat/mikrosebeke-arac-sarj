"""Hafta 5 (YM-2): kontrolsüz şarjda (S2) araç sayısına göre tepe yük ve istasyonun kritik anı.

Haziran ve Aralık temsili günleri için araç sayısını 0'dan 40'a çıkarır. Veri (data/processed/) yoksa sahte
girdilerle çalışır ve grafiğe "SAHTE GİRDİ" yazar; o sayılar raporda gerçek sonuç gibi kullanılmamalı.

    python scripts/ym2_hafta5_tepe_yuk.py
Çıktı: docs/raporlar/hafta5-ym2-tepe-yuk.png, konsola Markdown tablolar (rapora kopyalanır).
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from microgrid.config import REPO_ROOT, load_config
from microgrid.sim.loop import time_index
from microgrid.sim.scenarios import SCENARIOS, simulate
from microgrid.sim.setup import SAHTE, TEMSILI_GUNLER, load_inputs, with_start
from microgrid.station.analysis import S2, critical_station_snapshot, md_table, peak_vs_vehicle_count

COUNTS = [0, 5, 10, 15, 20, 30, 40]
LABEL = {"haziran": "Haziran", "aralik": "Aralık"}
base = load_config()
tables, snaps, sources = {}, {}, set()
for name, start in TEMSILI_GUNLER.items():
    cfg = with_start(base, start)
    inputs, source = load_inputs(cfg, time_index(cfg))
    sources.add(source)
    tables[name] = peak_vs_vehicle_count(cfg, inputs, COUNTS)
    snaps[name] = critical_station_snapshot(simulate(cfg, SCENARIOS[S2], inputs), cfg)

fake = SAHTE in sources
fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
for ax, col, title in zip(axes, ["istasyon_tepe_kw", "sebeke_tepe_kw"], ["İstasyon tepe yükü", "Şebeke tepe alımı"]):
    for name, t in tables.items():
        ax.plot(t.arac_sayisi, t[col], marker="o", label=LABEL[name])
    ax.axhline(base["station"]["power_limit_kw"], ls="--", c="gray", lw=1, label="İstasyon sınırı 150 kW")
    ax.axhline(base["grid"]["site_import_limit_kw"], ls=":", c="red", lw=1, label="Site sınırı 180 kW")
    ax.set(title=title, xlabel="Araç sayısı", ylabel="kW")
    ax.grid(alpha=0.3)
axes[0].legend(fontsize=8)
fig.suptitle("S2 kontrolsüz şarj: araç sayısı – tepe yük" + ("  (SAHTE GİRDİ)" if fake else ""))
fig.tight_layout()
out = REPO_ROOT / "docs" / "raporlar" / "hafta5-ym2-tepe-yuk.png"
fig.savefig(out, dpi=150)

print(f"Girdi kaynağı: {', '.join(sorted(sources))}\n")
for name, t in tables.items():
    print(f"### {LABEL[name]}\n\n{md_table(t)}\n")
print("### İstasyonun kritik anı (S2, config'teki araç sayısı)\n")
print(md_table(pd.DataFrame(snaps).T, index=True))
print(f"\nYazıldı: {out}")
