"""Hafta 6 (YM-1): mevsim profilleri, temsili günlerden yıla genişletme ve doğrulaması.

1. Doğrulama (Senaryo 1, araç yok): 365 günlük tam simülasyon ile 8 / 16 / 24 temsili günden yıllık tahmin.
2. Yıllık tahmin: Senaryo 1 ve 2 (kontrolsüz şarj), 24 temsili gün, pandapower ile.
Senaryo 2 tam yıl çalıştırılamıyor: sahte istasyon araçları yalnızca ilk gün üretiyor (YM-2 modeli gelince).

Önce veri:  python -m microgrid.data.pvgis && python -m microgrid.data.loads
Sonra:      python scripts/ym1_hafta6_yillik.py
Çıktı: results/yillik_kpi.csv, results/yillik_dogrulama.csv, docs/raporlar/hafta6-ym1-mevsim.png
"""
import copy

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from microgrid.config import REPO_ROOT, load_config
from microgrid.data import seasons
from microgrid.data.inputs import build_inputs
from microgrid.grid import PandapowerGrid
from microgrid.kpi import KPI_UNITS, annualize, compute
from microgrid.sim.loop import run
from microgrid.sim.mocks import MockStation, SimpleBattery, UncontrolledEMS

base = load_config()
year = base["loads"]["year"]
out_dir = REPO_ROOT / "results"
out_dir.mkdir(exist_ok=True)


def scenario_cfg(n_vehicles=None, sky_classes=None):
    cfg = copy.deepcopy(base)
    if n_vehicles is not None:
        cfg["vehicles"]["count"] = n_vehicles
    if sky_classes is not None:
        cfg["inputs"]["sky_classes"] = sky_classes
    return cfg


def representative_year(cfg, grid=None):
    days = seasons.day_table(cfg)
    profs = seasons.profiles(cfg)
    weights = seasons.calendar(cfg, days)
    results = {}
    for key in weights.index:
        inp = seasons.representative_inputs(cfg, key, profs, days)
        results[key] = run(cfg, inp, MockStation(cfg, inp.index[0]), UncontrolledEMS(), SimpleBattery(cfg), grid).steps
    return annualize(results, weights.to_dict(), cfg), results, weights


# 1. Doğrulama: Senaryo 1, tam yıl
s1 = scenario_cfg(n_vehicles=0)
full_cfg = copy.deepcopy(s1)
full_cfg["inputs"]["mode"] = "actual"
idx = pd.date_range(pd.Timestamp(f"{year}-01-01", tz="Europe/Istanbul"), periods=365 * 96, freq="15min")
full = run(full_cfg, build_inputs(full_cfg, idx), MockStation(full_cfg, idx[0]), UncontrolledEMS(), SimpleBattery(full_cfg))
full_k = compute(full.steps, full_cfg)

check = ["maliyet_tl", "alim_kwh", "alim_puant_kwh", "veris_kwh", "pv_kwh", "tuketim_kwh", "yenilenebilir_payi",
         "oz_tuketim_orani"]
validation = pd.DataFrame({"tam_yil": full_k[check].astype(float)})
for n in (1, 2, 3):
    est = representative_year(scenario_cfg(n_vehicles=0, sky_classes=n))[0]
    validation[f"{8 * n}_gun"] = est[check].astype(float)
for col in validation.columns[1:]:
    validation[f"{col}_fark_%"] = 100 * (validation[col] / validation["tam_yil"] - 1)
validation.to_csv(out_dir / "yillik_dogrulama.csv")
print("Doğrulama (Senaryo 1, yıllık):")
print(validation.round(3).to_string())

# 2. Yıllık tahmin, 24 temsili gün, pandapower
grid = PandapowerGrid(base)
annual = {}
for name, n in [("S1 araç yok", 0), ("S2 kontrolsüz", None)]:
    annual[name], _, weights = representative_year(scenario_cfg(n_vehicles=n), grid)
table = pd.DataFrame(annual)
table["birim"] = pd.Series(KPI_UNITS)
table.to_csv(out_dir / "yillik_kpi.csv")
print(f"\nYıllık tahmin ({len(weights)} temsili gün):")
print(table.to_string(float_format=lambda v: f"{v:,.2f}"))

# Grafik
profs = seasons.profiles(base)
fig, axes = plt.subplots(1, 3, figsize=(17, 4.6))
colors = {"kis": "tab:blue", "ilkbahar": "tab:green", "yaz": "tab:orange", "sonbahar": "tab:brown"}
labels = {"kis": "Kış", "ilkbahar": "İlkbahar", "yaz": "Yaz", "sonbahar": "Sonbahar"}
hours = np.arange(24)
for s, c in colors.items():
    sub = profs.loc[s].groupby(level="saat").mean()   # mevsimin bütün günleri
    axes[0].plot(hours, sub["pv_kw"], color=c, lw=2, label=f"{labels[s]} PV")
    axes[0].plot(hours, sub["base_load_kw"], color=c, lw=1.2, ls="--")
axes[0].set(title="Mevsim profilleri (düz: PV, kesikli: sabit yük)", xlabel="Saat", ylabel="kW", xticks=range(0, 24, 3))
axes[0].legend(fontsize=8)
axes[0].grid(alpha=0.3)

for sky, c in zip(seasons.SKY_NAMES[3], ["tab:gray", "tab:olive", "gold"]):
    axes[1].plot(hours, profs.loc[("yaz", "hafta_ici", sky), "pv_kw"].to_numpy(), color=c, lw=2, label=f"Yaz, {sky}")
axes[1].plot(hours, profs.loc[("yaz", "hafta_ici", "orta"), "base_load_kw"].to_numpy(), color="black", lw=1.2, ls="--",
             label="Sabit yük")
errs = {f"{8 * n} gün": validation[f"{8 * n}_gun_fark_%"]["maliyet_tl"] for n in (1, 2, 3)}
axes[1].set(title="Gökyüzü sınıfları (yaz, hafta içi PV)", xlabel="Saat", ylabel="kW", xticks=range(0, 24, 3))
axes[1].text(0.02, 0.97, "Yıllık maliyet hatası (tam yıla göre):\n" + "\n".join(f"{k}: %{v:+.1f}" for k, v in errs.items()),
             transform=axes[1].transAxes, va="top", fontsize=8, bbox={"fc": "white", "alpha": 0.8})
axes[1].legend(fontsize=8, loc="upper right")
axes[1].grid(alpha=0.3)

periods = ["alim_gunduz_kwh", "alim_puant_kwh", "alim_gece_kwh"]
bottom = np.zeros(2)
for p, c, lab in zip(periods, ["tab:olive", "tab:red", "tab:blue"], ["Gündüz", "Puant", "Gece"]):
    vals = table.loc[p, list(annual)].astype(float).to_numpy() / 1000
    axes[2].bar(list(annual), vals, bottom=bottom, color=c, label=lab)
    bottom += vals
for i, name in enumerate(annual):
    axes[2].text(i, bottom[i] + 3, f"{table.loc['maliyet_tl', name] / 1e3:,.0f} bin TL/yıl", ha="center", fontsize=9)
axes[2].set(title="Yıllık şebeke alımı (tarife dilimine göre)", ylabel="MWh/yıl", ylim=(0, bottom.max() * 1.15))
axes[2].legend(fontsize=8)
axes[2].grid(alpha=0.3, axis="y")

fig.suptitle(f"{base['site']['name']} · {len(weights)} temsili gün (4 mevsim × 2 gün tipi × 3 gökyüzü) → yıl")
fig.tight_layout()
out_png = REPO_ROOT / "docs" / "raporlar" / "hafta6-ym1-mevsim.png"
fig.savefig(out_png, dpi=150)
print(f"\nYazıldı: {out_png}")
