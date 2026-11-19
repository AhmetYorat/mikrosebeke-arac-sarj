"""Hafta 5 (YM-1): Senaryo 1 (araç yok) ve Senaryo 2 (kontrolsüz şarj) KPI karşılaştırması.

İki temsili gün (Haziran, Aralık) için döngüyü gerçek veriyle (build_inputs) ve pandapower ile çalıştırır.
İstasyon ve EMS sahte; Senaryo 1'de araç sayısı 0.

Önce veri:  python -m microgrid.data.pvgis && python -m microgrid.data.loads
Sonra:      python scripts/ym1_hafta5_kpi.py
Çıktı: results/kpi_senaryo1_2.csv, docs/raporlar/hafta5-ym1-kpi.png
"""
import copy

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from microgrid.config import REPO_ROOT, load_config
from microgrid.data.inputs import build_inputs
from microgrid.grid import PandapowerGrid
from microgrid.kpi import compare
from microgrid.sim.loop import run, time_index
from microgrid.sim.mocks import MockStation, SimpleBattery, UncontrolledEMS

DAYS = {"Haziran": "2023-06-21 12:00", "Aralık": "2023-12-20 12:00"}
SCENARIOS = {"S1 araç yok": 0, "S2 kontrolsüz": None}   # None: config'teki araç sayısı

base_cfg = load_config()
grid = PandapowerGrid(base_cfg)
results = {}
for day, start in DAYS.items():
    for scen, n_vehicles in SCENARIOS.items():
        cfg = copy.deepcopy(base_cfg)
        cfg["simulation"]["start"] = start
        if n_vehicles is not None:
            cfg["vehicles"]["count"] = n_vehicles
        index = time_index(cfg)
        results[f"{day} · {scen}"] = run(
            cfg, build_inputs(cfg, index), MockStation(cfg, index[0]), UncontrolledEMS(), SimpleBattery(cfg), grid=grid
        ).steps

table = compare(results, base_cfg)
out_csv = REPO_ROOT / "results" / "kpi_senaryo1_2.csv"
out_csv.parent.mkdir(exist_ok=True)
table.to_csv(out_csv)

rows = ["tepe_alim_kw", "maliyet_tl", "alim_puant_kwh", "yenilenebilir_payi", "oz_tuketim_orani", "min_gerilim_pu",
        "max_kablo_yuklenme_pct"]
print(table.loc[rows].to_string(float_format=lambda v: f"{v:.2f}"))

# Grafik: tepe yük ve maliyet, gün × senaryo
fig, axes = plt.subplots(1, 3, figsize=(15, 4.3))
x = np.arange(len(DAYS))
w = 0.38
colors = {"S1 araç yok": "tab:gray", "S2 kontrolsüz": "tab:red"}
for ax, (kpi, title, unit) in zip(axes, [
    ("tepe_alim_kw", "Şebeke tepe yükü", "kW"),
    ("maliyet_tl", "Günlük elektrik maliyeti", "TL"),
    ("yenilenebilir_payi", "Yenilenebilir payı", "%"),
]):
    for i, scen in enumerate(SCENARIOS):
        vals = [table.loc[kpi, f"{d} · {scen}"] * (100 if unit == "%" else 1) for d in DAYS]
        bars = ax.bar(x + (i - 0.5) * w, vals, w, label=scen, color=colors[scen])
        ax.bar_label(bars, fmt="%.0f", fontsize=8)
    if kpi == "tepe_alim_kw":
        ax.axhline(base_cfg["grid"]["site_import_limit_kw"], color="tab:red", ls="--", lw=1, label="Site sınırı 180 kW")
    ax.set_xticks(x, list(DAYS))
    ax.set(title=title, ylabel=unit)
    ax.grid(alpha=0.3, axis="y")
axes[0].legend(fontsize=8, loc="upper left")
fig.suptitle("İstasyonun etkisi: Senaryo 1 (araç yok) vs Senaryo 2 (kontrolsüz şarj) · temsili günler")
fig.tight_layout()
out_png = REPO_ROOT / "docs" / "raporlar" / "hafta5-ym1-kpi.png"
fig.savefig(out_png, dpi=150)
print(f"\nYazıldı: {out_csv}\nYazıldı: {out_png}")
