"""Sunum grafikleri (YM-1, Hafta 10). Her grafik tek mesaj, 16:9, büyük yazı.

Önce veri:  python -m microgrid.data
Sonra:      python scripts/ym1_sunum_grafikleri.py      (~1 dk)
Çıktı: docs/sunum/ym1-*.png
"""
import copy

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from microgrid.analysis import run_year, scenario_config, sweep
from microgrid.config import REPO_ROOT, load_config
from microgrid.data import seasons
from microgrid.data.inputs import build_inputs
from microgrid.kpi import annualize, compute
from microgrid.sim.loop import run
from microgrid.sim.scenarios import SCENARIOS, Scenario

plt.rcParams.update({"font.size": 15, "axes.titlesize": 19, "axes.labelsize": 15, "legend.fontsize": 13,
                     "axes.spines.top": False, "axes.spines.right": False})
SIZE = (13.33, 7.5)   # 16:9
OUT = REPO_ROOT / "docs" / "sunum"
OUT.mkdir(parents=True, exist_ok=True)
cfg = load_config()
limit = cfg["grid"]["site_import_limit_kw"]


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=150)
    plt.close(fig)
    print(f"Yazıldı: {OUT / name}")


def day_index(start):
    return pd.date_range(pd.Timestamp(start, tz="Europe/Istanbul"), periods=96, freq="15min")


# 1. Sorun: araçlar PV'nin bittiği ve elektriğin en pahalı olduğu saatte geliyor (Aralık temsili günü)
c = copy.deepcopy(cfg)
idx = day_index("2023-12-20 12:00")
sc2 = SCENARIOS["S2 Kontrolsüz şarj"]   # YM-2 istasyonu, kontrolsüz şarj
s2 = run(c, build_inputs(c, idx), sc2.station(c, idx[0]), sc2.ems(c), sc2.battery(c)).steps
x = np.arange(len(s2)) / 4
fig, ax = plt.subplots(figsize=SIZE)
top = max(s2["grid_kw"].max(), limit) * 1.15
puant = (s2.index.hour >= 17) & (s2.index.hour < 22)
ax.fill_between(x, 0, top, where=puant, color="tab:red", alpha=0.08, step="post", label="Puant tarifesi 6,17 TL/kWh")
ax.fill_between(x, s2["pv_kw"], color="tab:orange", alpha=0.45, label="Güneş (PV) üretimi")
ax.plot(x, s2["base_load_kw"], color="black", lw=2.5, label="Site (daireler + ortak alan)")
ax.plot(x, s2["grid_kw"], color="tab:red", lw=3.5, label="Şebekeden çekilen güç")
ax.axhline(limit, color="tab:red", ls="--", lw=1.5)
ax.text(0.3, limit + 4, f"Site sınırı {limit} kW", color="tab:red", fontsize=14)
peak = s2["grid_kw"].idxmax()
ax.annotate(f"{s2['grid_kw'].max():.0f} kW\n{peak:%H:%M}", xy=(x[s2.index.get_loc(peak)], s2["grid_kw"].max()),
            xytext=(x[s2.index.get_loc(peak)] + 2.5, 0.75 * s2["grid_kw"].max()), arrowprops={"arrowstyle": "->", "lw": 1.5}, fontsize=15)
ticks = np.arange(0, 25, 3)
ax.set_xticks(ticks, [f"{(12 + t) % 24:02d}:00" for t in ticks])
ax.set(ylim=(0, top), ylabel="kW", title="Kontrolsüz şarj: araçlar güneşin bittiği ve elektriğin en pahalı olduğu saatte geliyor")
ax.legend(loc="upper right")
save(fig, "ym1-1-sorun-aralik-gunu.png")

# 2. İstasyonun etkisi: yıllık maliyet ve tepe yük (S1 vs S2)
s1 = Scenario("S1", config={"vehicles.count": 0})
s1_k, _ = run_year(scenario_config(cfg, s1), s1)
s2_k, _ = run_year(cfg, Scenario("S2"))
fig, axes = plt.subplots(1, 2, figsize=SIZE)
names = ["Araç yok", "Kontrolsüz şarj\n(20 araç)"]
for ax, (kpi, title, unit, scale) in zip(axes, [("maliyet_tl", "Yıllık elektrik maliyeti", "bin TL/yıl", 1e3),
                                                ("tepe_alim_kw", "Yılın en yüksek şebeke yükü", "kW", 1)]):
    vals = [float(s1_k[kpi]) / scale, float(s2_k[kpi]) / scale]
    bars = ax.bar(names, vals, color=["tab:gray", "tab:red"], width=0.55)
    ax.bar_label(bars, labels=[f"{v:,.0f}".replace(",", ".") for v in vals], fontsize=17, padding=4)
    ax.set(title=title, ylabel=unit, ylim=(0, max(vals) * 1.2))
    if kpi == "tepe_alim_kw":
        ax.axhline(limit, color="tab:red", ls="--", lw=1.5)
        ax.text(-0.3, limit + 4, f"Site sınırı {limit} kW", color="tab:red", fontsize=13)
puant_payi = float(s2_k["arac_sarj_puant_payi"])
ratio = lambda k: f"{float(s2_k[k]) / float(s1_k[k]):.1f}".replace(".", ",")
fig.suptitle(f"İstasyonun etkisi: maliyet {ratio('maliyet_tl')} katına, tepe yük {ratio('tepe_alim_kw')} katına çıkıyor "
             f"(şarjın %{puant_payi * 100:.0f}'ü puantta)", fontsize=17)
save(fig, "ym1-2-istasyon-etkisi.png")

# 3. Duyarlılık: araç sayısı ve tepe yük
df = sweep(cfg, Scenario("S2"), "vehicles.count", [0, 2, 4, 6, 8, 10, 15, 20, 25, 30])
fig, ax = plt.subplots(figsize=SIZE)
peaks = df["tepe_alim_kw"].astype(float)
ax.plot(df.index, peaks, marker="o", ms=10, lw=3, color="black", label="Yılın en yüksek şebeke yükü")
ax.axhline(limit, color="tab:red", ls="--", lw=2, label=f"Site sınırı {limit} kW")
ax.fill_between(df.index, limit, peaks, where=peaks > limit, color="tab:red", alpha=0.2, interpolate=True)
ax.axvline(cfg["vehicles"]["count"], color="gray", ls=":", lw=2)
ax.text(cfg["vehicles"]["count"] + 0.3, 30, "Mevcut tasarım\n(20 araç)", color="gray", fontsize=14)
over = peaks[peaks > limit]
first = f"{over.index[0]} araçta" if len(over) else "incelenen aralıkta"
ax.set(xlabel="Araç sayısı", ylabel="kW", ylim=(0, peaks.max() * 1.15),
       title=f"Kontrolsüz şarjda site sınırı {first} aşılıyor (mevcut tasarım {cfg['vehicles']['count']} araç)")
ax.legend(loc="upper left")
save(fig, "ym1-3-arac-sayisi.png")

# 4. Yöntem: temsili günler (yıllık maliyet hatası, tam yıla göre)
c1 = scenario_config(cfg, Scenario("S1"), {"vehicles.count": 0})
full_cfg = copy.deepcopy(c1)
full_cfg["inputs"]["mode"] = "actual"
year = cfg["loads"]["year"]
idx = pd.date_range(pd.Timestamp(f"{year}-01-01", tz="Europe/Istanbul"), periods=365 * 96, freq="15min")
s1 = Scenario("S1")
full = compute(run(full_cfg, build_inputs(full_cfg, idx), s1.station(full_cfg, idx[0]), s1.ems(full_cfg),
                   s1.battery(full_cfg)).steps, full_cfg)
errs = {}
for n, label in [(1, "8 gün\nmevsim × gün tipi"), (2, "16 gün\n+ güneşli/bulutlu"), (3, "24 gün\n+ bulutlu/orta/güneşli")]:
    k, _ = run_year(scenario_config(c1, Scenario("S1"), {"inputs.sky_classes": n}), Scenario("S1"))
    errs[label] = 100 * (float(k["maliyet_tl"]) / float(full["maliyet_tl"]) - 1)
fig, ax = plt.subplots(figsize=SIZE)
bars = ax.bar(list(errs), [abs(v) for v in errs.values()], color=["tab:gray", "tab:olive", "tab:green"], width=0.55)
ax.bar_label(bars, labels=[f"%{v:+.1f}".replace(".", ",") for v in errs.values()], fontsize=18, padding=4)
ax.set(ylabel="Yıllık maliyet hatası (%, mutlak)", ylim=(0, max(abs(v) for v in errs.values()) * 1.25),
       title="Yıl, 24 temsili günle %3 hatayla hesaplanıyor (365 günlük simülasyona göre)")
save(fig, "ym1-4-temsili-gun-dogrulama.png")
