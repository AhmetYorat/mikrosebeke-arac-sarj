"""Hafta 9 (YM-1): duyarlılık analizi. Araç sayısı, PV gücü ve batarya boyutu yıllık KPI'ları nasıl değiştiriyor?

Her nokta 24 temsili günden yıllık tahmin (data/seasons.py, kpi.annualize). Hız için yük akışı yok.
- Araç sayısı ve PV gücü: Senaryo 2 (kontrolsüz şarj, sahte istasyon).
- Batarya boyutu: senaryo listesinde (sim/scenarios.py) YM-3'ün "S4 Akıllı şarj + batarya" senaryosu varsa onunla;
  yoksa GEÇİCİ basit batarya kuralıyla (aşağıda). YM-3'ün EMS'i ana koda girince betik kendiliğinden onu kullanır.

Önce veri:  python -m microgrid.data
Sonra:      python scripts/ym1_hafta9_duyarlilik.py
Çıktı: results/duyarlilik_*.csv, docs/raporlar/hafta9-ym1-duyarlilik.png
"""
import dataclasses

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from microgrid.analysis import run_year, scenario_config, sweep
from microgrid.config import REPO_ROOT, load_config
from microgrid.data.tariff import period_at
from microgrid.interfaces import Decision
from microgrid.sim.mocks import SimpleBattery, UncontrolledEMS
from microgrid.sim.scenarios import SCENARIOS, Scenario


class BatteryRuleEMS(UncontrolledEMS):
    """GEÇİCİ (YM-3 EMS'i gelene kadar): araçlar kontrolsüz; batarya PV fazlasını saklar, puantta alımı karşılar.

    Gece şebekeden şarj etmez; bu yüzden kışın PV az olduğunda bataryanın etkisi sınırlı kalır.
    """

    def __init__(self, cfg):
        self.cfg = cfg

    def decide(self, inp):
        ev = super().decide(inp).ev_kw
        net = inp.base_load_kw + sum(ev.values()) - inp.pv_kw       # bataryasız şebeke alımı
        if net < 0:
            bess = -net                                             # fazla PV -> bataryaya
        elif period_at(self.cfg, inp.ctx.hour)["name"] == "puant":
            bess = -net                                             # puantta alımı bataryadan karşıla
        else:
            bess = 0.0
        return Decision(ev_kw=ev, bess_kw=bess)


cfg = load_config()
s2 = Scenario("S2 kontrolsüz")
s4 = next((sc for name, sc in SCENARIOS.items() if name.startswith("S4")), None)
s_bess = s4 or Scenario("S2 + batarya kuralı (geçici)", ems=lambda c: BatteryRuleEMS(c),
                        battery=lambda c: SimpleBattery(c))


def battery_sweep(scenario, path, values):
    """Batarya kapasitesi 0 noktası, 0 kWh'i kaldırabilen SimpleBattery ile ("batarya yok") hesaplanır."""
    rows = []
    if 0 in values:
        no_bess = dataclasses.replace(scenario, battery=lambda c: SimpleBattery(c))
        zero = run_year(scenario_config(cfg, no_bess, {path: 0}), no_bess)[0]
        rows.append(pd.DataFrame([zero], index=pd.Index([0], name=path)))
    rows.append(sweep(cfg, scenario, path, [v for v in values if v != 0]))
    return pd.concat(rows)


out_dir = REPO_ROOT / "results"
out_dir.mkdir(exist_ok=True)

SWEEPS = [
    ("vehicles.count", [0, 5, 10, 15, 20, 25, 30, 40], s2, "Araç sayısı", "araç"),
    ("pv.installed_kw", [0, 50, 100, 150, 200, 300], s2, "PV kurulu gücü", "kWp"),
    ("bess.capacity_kwh", [0, 100, 200, 300, 400, 600], s_bess, "Batarya kapasitesi", "kWh"),
]
results = {}
for path, values, scen, title, unit in SWEEPS:
    df = battery_sweep(scen, path, values) if path.startswith("bess.") else sweep(cfg, scen, path, values)
    results[path] = df
    df.to_csv(out_dir / f"duyarlilik_{path.split('.')[0]}.csv")
    cols = ["tepe_alim_kw", "maliyet_tl", "yenilenebilir_payi", "oz_tuketim_orani", "site_siniri_asim_kwh"]
    print(f"\n{title} ({scen.name}):")
    print(df[cols].astype(float).to_string(float_format=lambda v: f"{v:,.2f}"))

fig, axes = plt.subplots(2, 3, figsize=(16, 8))
limit = cfg["grid"]["site_import_limit_kw"]
default = {"vehicles.count": cfg["vehicles"]["count"], "pv.installed_kw": cfg["pv"]["installed_kw"],
           "bess.capacity_kwh": cfg["bess"]["capacity_kwh"]}
for col, (path, values, scen, title, unit) in enumerate(SWEEPS):
    df = results[path].astype(float, errors="ignore")
    x = list(df.index)
    ax = axes[0, col]
    ax.plot(x, df["maliyet_tl"].astype(float) / 1e3, marker="o", color="tab:red", label="Yıllık maliyet")
    ax.set(title=f"{title} ({scen.name})", ylabel="bin TL/yıl")
    ax2 = ax.twinx()
    ax2.plot(x, 100 * df["yenilenebilir_payi"].astype(float), marker="s", color="tab:green", label="Yenilenebilir payı")
    ax2.set(ylabel="Yenilenebilir payı (%)", ylim=(0, 100))
    ax.axvline(default[path], color="gray", ls=":", lw=1)
    ax.grid(alpha=0.3)
    lines = ax.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
    ax.legend(lines, [l.get_label() for l in lines], fontsize=8, loc="upper left")

    ax = axes[1, col]
    ax.plot(x, df["tepe_alim_kw"].astype(float), marker="o", color="black", label="Yılın tepe alımı")
    ax.axhline(limit, color="tab:red", ls="--", lw=1, label=f"Site sınırı {limit} kW")
    ax.axvline(default[path], color="gray", ls=":", lw=1, label="Mevcut tasarım")
    ax.set(xlabel=unit, ylabel="kW", ylim=(0, 280))   # üç grafikte aynı ölçek
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="best")

fig.suptitle(f"{cfg['site']['name']} · duyarlılık analizi · yıllık tahmin (24 temsili gün)")
fig.tight_layout()
out_png = REPO_ROOT / "docs" / "raporlar" / "hafta9-ym1-duyarlilik.png"
fig.savefig(out_png, dpi=150)
print(f"\nYazıldı: {out_png}")
