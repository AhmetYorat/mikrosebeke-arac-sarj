"""Hafta 1 rapor grafiği (YM-1): Bandırma PVGIS verisi.

Önce veriyi indir:  python -m microgrid.data.pvgis
Sonra:              python scripts/ym1_pvgis_grafik.py
Çıktı: docs/raporlar/hafta1-ym1-pvgis-bandirma.png
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from microgrid.config import REPO_ROOT, load_config
from microgrid.data.pvgis import RAW_DIR, load

cfg = load_config()
site, pv = cfg["site"], cfg["pv"]
df = load(RAW_DIR / f"pvgis_{site['name'].lower()}_{pv['pvgis_year']}.csv")
df = df[df.index.year == pv["pvgis_year"]]  # UTC->yerel kaymasıyla ertesi yıla taşan 3 saati at
kw = df["pv_kw_per_kwp"] * pv["installed_kw"]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))

for month, name in [(6, "Haziran"), (3, "Mart"), (12, "Aralık")]:
    sel = kw[kw.index.month == month]
    sel.groupby(sel.index.hour).mean().plot(ax=ax1, marker="o", ms=3, label=name)
ax1.axvspan(17, 22, color="tab:red", alpha=0.1, label="Puant (17–22)")
ax1.axvline(cfg["vehicles"]["arrival_hour"]["mean"], color="gray", ls="--", label="Ort. araç varışı")
ax1.set(title=f"Ortalama günlük PV üretimi ({pv['installed_kw']} kWp)", xlabel="Saat", ylabel="kW", xticks=range(0, 24, 3))
ax1.legend(fontsize=8)
ax1.grid(alpha=0.3)

monthly = kw.resample("ME").sum() / 1000
ax2.bar(range(1, 13), monthly.values, color="tab:orange")
ax2.set(title=f"Aylık PV üretimi, toplam {monthly.sum():.0f} MWh/yıl", xlabel="Ay", ylabel="MWh", xticks=range(1, 13))
ax2.grid(alpha=0.3, axis="y")

fig.suptitle(f"{site['name']} ({site['latitude']}° K, {site['longitude']}° D) · PVGIS {pv['pvgis_year']}")
fig.tight_layout()
out = REPO_ROOT / "docs" / "raporlar" / "hafta1-ym1-pvgis-bandirma.png"
fig.savefig(out, dpi=150)
print(f"Yazıldı: {out}")
