"""Hafta 3 rapor grafiği (YM-1): döngüye giden 15 dakikalık girdiler ve PV modelinin doğrulaması.

Önce veri:  python -m microgrid.data.pvgis && python -m microgrid.data.loads
Sonra:      python scripts/ym1_hafta3_grafik.py
Çıktı: docs/raporlar/hafta3-ym1-girdiler.png
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from microgrid.config import REPO_ROOT, load_config
from microgrid.data import pvgis
from microgrid.data.inputs import build_inputs
from microgrid.data.pv import pv_from_irradiance

cfg = load_config()
step = cfg["simulation"]["step_minutes"]


def day_index(start):
    # Döngüdeki temsili gün gibi: öğlen başlar, ertesi gün öğlen biter
    return pd.date_range(pd.Timestamp(start, tz="Europe/Istanbul"), periods=24 * 60 // step, freq=f"{step}min")


fig, axes = plt.subplots(1, 3, figsize=(17, 4.8))

for ax, (start, title) in zip(axes[:2], [("2023-06-21 12:00", "Haziran"), ("2023-12-20 12:00", "Aralık")]):
    df = build_inputs(cfg, day_index(start))
    x = np.arange(len(df)) * step / 60          # öğlenden itibaren geçen saat
    ax.fill_between(x, df["pv_kw"], color="tab:orange", alpha=0.35, label="PV")
    ax.plot(x, df["base_load_kw"], color="black", lw=2, label="Sabit yük")
    ax.set(title=f"{title} temsili gün ({step} dk adım, hafta içi ort.)", ylabel="kW", ylim=(0, cfg["pv"]["installed_kw"]))
    ticks = np.arange(0, 25, 3)
    ax.set_xticks(ticks, [f"{(12 + t) % 24:02d}:00" for t in ticks], fontsize=8)
    ax.grid(alpha=0.3)
    ax2 = ax.twinx()
    ax2.step(x, df["price_tl_per_kwh"], where="post", color="tab:red", lw=1.5, label="Fiyat")
    ax2.set(ylabel="TL/kWh", ylim=(0, 8))
    lines = ax.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
    ax.legend(lines, [l.get_label() for l in lines], fontsize=8, loc="upper right")

kwp = cfg["pv"]["installed_kw"]
raw = pvgis.load(pvgis.processed_path(cfg))
a = raw["pv_kw_per_kwp"] * kwp
b = pv_from_irradiance(raw["irradiance_w_m2"], raw["temp_c"], kwp, cfg["pv"]["loss_percent"])
ax = axes[2]
ax.scatter(a, b, s=2, alpha=0.2)
ax.plot([0, kwp], [0, kwp], color="gray", ls="--")
day = a > 1
r2 = np.corrcoef(a[day], b[day])[0, 1] ** 2
ax.set(
    title=f"PV modeli doğrulama: R²={r2:.3f}, yıllık fark %{100 * (b.sum() / a.sum() - 1):+.1f}",
    xlabel="PVGIS üretimi (kW)", ylabel="Işınım + sıcaklık modeli (kW)",
)
ax.grid(alpha=0.3)

fig.suptitle(f"{cfg['site']['name']} · döngüye giden girdiler (build_inputs) · PV {kwp} kWp")
fig.tight_layout()
out = REPO_ROOT / "docs" / "raporlar" / "hafta3-ym1-girdiler.png"
fig.savefig(out, dpi=150)
print(f"Yazıldı: {out}")
