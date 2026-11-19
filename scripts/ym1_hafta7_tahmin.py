"""Hafta 7 (YM-1): ertesi gün tahmininin doğruluğu.

Önce veri:  python -m microgrid.data.pvgis && python -m microgrid.data.loads
Sonra:      python scripts/ym1_hafta7_tahmin.py
Çıktı: results/tahmin_dogruluk.csv, docs/raporlar/hafta7-ym1-tahmin.png
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from microgrid.config import REPO_ROOT, load_config
from microgrid.data.forecast import METHODS, evaluate, hourly_forecast

cfg = load_config()
metrics = evaluate(cfg)
out_dir = REPO_ROOT / "results"
out_dir.mkdir(exist_ok=True)
metrics.to_csv(out_dir / "tahmin_dogruluk.csv")
print(metrics.round(2).to_string())

f = {m: hourly_forecast(cfg, m, m) for m in METHODS}
actual = f["perfect"]

fig, axes = plt.subplots(1, 3, figsize=(17, 4.6), gridspec_kw={"width_ratios": [2, 1, 1]})

# 1. Örnek hafta: değişken hava, aralık
week = slice("2023-12-11", "2023-12-17")
ax = axes[0]
x = actual.loc[week].index
ax.fill_between(x, actual.loc[week, "pv_kw"], color="tab:orange", alpha=0.3, label="Gerçek PV")
ax.plot(x, f["persistence"].loc[week, "pv_kw"], color="tab:gray", lw=1, label="Tahmin: dün (persistence)")
ax.plot(x, f["blend"].loc[week, "pv_kw"], color="tab:red", lw=1.6, label="Tahmin: blend (seçilen)")
ax.plot(x, actual.loc[week, "base_load_kw"], color="black", lw=1.2, label="Gerçek sabit yük")
ax.plot(x, f["climatology"].loc[week, "base_load_kw"], color="tab:blue", lw=1.2, ls="--", label="Tahmin: yük (climatology)")
ax.set(title="Örnek hafta (11–17 Aralık): gün öncesi tahmin", ylabel="kW")
ax.legend(fontsize=7, loc="upper right")
ax.grid(alpha=0.3)
ax.tick_params(axis="x", labelsize=8)

# 2. Yöntem karşılaştırması
ax = axes[1]
names = list(METHODS[1:])
w = 0.38
for i, (col, label, c) in enumerate([("pv_kw", "PV (kurulu güce göre)", "tab:orange"), ("base_load_kw", "Yük (ortalamaya göre)", "black")]):
    vals = [metrics.loc[(col, m), "nmae_pct"] for m in names]
    bars = ax.bar(np.arange(len(names)) + (i - 0.5) * w, vals, w, label=label, color=c, alpha=0.8)
    ax.bar_label(bars, fmt="%.1f", fontsize=8)
ax.set_xticks(range(len(names)), names)
ax.set(title="Saatlik hata (nMAE, %)", ylabel="%")
ax.legend(fontsize=8)
ax.grid(alpha=0.3, axis="y")

# 3. PV günlük enerji hatası aylara göre
ax = axes[2]
for m, c in [("persistence", "tab:gray"), ("blend", "tab:red")]:
    err = (f[m]["pv_kw"] - actual["pv_kw"]).groupby(actual.index.normalize()).sum().abs()
    err.groupby(err.index.month).mean().plot(ax=ax, marker="o", color=c, label=m)
daily_pv = actual["pv_kw"].groupby(actual.index.normalize()).sum()
ax.plot(range(1, 13), daily_pv.groupby(daily_pv.index.month).mean().to_numpy(), color="tab:orange", ls=":", label="Ortalama günlük PV")
ax.set(title="PV günlük enerji hatası (aylık ort.)", xlabel="Ay", ylabel="kWh/gün", xticks=range(1, 13))
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

fig.suptitle(f"{cfg['site']['name']} · ertesi gün PV ve yük tahmini (yalnızca geçmiş günlerin verisi)")
fig.tight_layout()
out_png = REPO_ROOT / "docs" / "raporlar" / "hafta7-ym1-tahmin.png"
fig.savefig(out_png, dpi=150)
print(f"\nYazıldı: {out_png}")
