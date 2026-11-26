"""YM-3 Hafta 9: EMS ve optimizasyon sonuçları (rapor tabloları ve grafik).

    python scripts/ym3_hafta9_sonuclar.py            # tabloları yazdırır, docs/raporlar/hafta9-ym3-*.png üretir

Senaryolar S2-S6, iki temsili günde (Haziran, Aralık), gerçek veriyle. Araç filosu rastgele (MockStation tohumu):
sayılar 5 tohumun ortalamasıdır, grafik tohum 0'dır. Tüm senaryolar aynı istasyonla çalışır (V2GMockStation; V2G
yalnızca S6'da açık), böylece fark yalnızca EMS'ten gelir.
"""
from __future__ import annotations

import copy
import sys
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from microgrid.config import REPO_ROOT, load_config  # noqa: E402
from microgrid.data.forecast import forecast_inputs  # noqa: E402
from microgrid.data.inputs import build_inputs  # noqa: E402
from microgrid.ems.bess import BESS  # noqa: E402
from microgrid.ems.milp import MilpEMS  # noqa: E402
from microgrid.ems.rule_based import RuleBasedEMS  # noqa: E402
from microgrid.kpi import compute  # noqa: E402
from microgrid.sim.loop import run, time_index  # noqa: E402
from microgrid.sim.mocks import UncontrolledEMS, V2GMockStation  # noqa: E402
from microgrid.sim.setup import TEMSILI_GUNLER, load_inputs, with_start  # noqa: E402

OUT = REPO_ROOT / "docs" / "raporlar"
SEEDS = range(5)

ROWS = {   # ad -> (EMS üretici, V2G'ye uygun araç oranı)
    "S2 Kontrolsüz": (lambda c: UncontrolledEMS(), 0.0),
    "S3 Akıllı şarj (kural)": (lambda c: RuleBasedEMS(c), 0.0),
    "S4 + batarya (kural)": (lambda c: RuleBasedEMS(c, use_bess=True), 0.0),
    "S5 MILP": (lambda c: MilpEMS(c), 0.0),
    "S6k V2G (kural)": (lambda c: RuleBasedEMS(c, use_bess=True, v2g=True), 0.4),
    "S6 V2G (MILP)": (lambda c: MilpEMS(c, v2g=True), 0.4),
}


def simulate(c, inputs, make_ems, share, seed, forecast=None):
    idx = inputs.index
    st = V2GMockStation(c, idx[0], seed=seed, v2g_share=share)
    ems = make_ems(c)
    steps = run(c, inputs, st, ems, BESS(c), forecast=forecast).steps
    return steps, st, ems


def kpis(c, steps, st):
    k = compute(steps, c)
    dt = c["simulation"]["step_minutes"] / 60
    return {
        "maliyet_tl": float(k["maliyet_tl"]),
        "tepe_alim_kw": float(k["tepe_alim_kw"]),
        "puant_payi": float(k["arac_sarj_puant_payi"]),
        "oz_tuketim": float(k["oz_tuketim_orani"]),
        "soc_son": float(steps.bess_soc.iloc[-1]),
        "v2g_kwh": float((-steps.ev_kw.clip(upper=0)).sum() * dt),
        "arac_kwh": float(k["arac_sarj_kwh"]),
        "alim_puant_kwh": float(k["alim_puant_kwh"]),
    }


def main() -> None:
    cfg = load_config()
    tables, series = {}, {}
    for day, start in TEMSILI_GUNLER.items():
        c = with_start(cfg, start)
        idx = time_index(c)
        inputs, _ = load_inputs(c, idx, allow_mock=False)
        res = {}
        for name, (mk, share) in ROWS.items():
            t0, runs = time.time(), []
            for seed in SEEDS:
                steps, st, _ = simulate(c, inputs, mk, share, seed)
                runs.append(kpis(c, steps, st))
                if seed == 0:
                    series[(day, name)] = steps
            res[name] = pd.DataFrame(runs)
            print(f"  {day} {name}: {time.time() - t0:.0f} sn", file=sys.stderr)
        tables[day] = res

    # --- Tablo 1: senaryo karşılaştırması ---
    for day, res in tables.items():
        base = res["S2 Kontrolsüz"].mean()
        print(f"\n### {day.replace('aralik', 'Aralık').capitalize()} (5 tohum ortalaması)\n")
        print("| Senaryo | Maliyet (TL) | Δ maliyet | Tepe alım (kW) | Δ tepe | Puant şarj payı | Öz tüketim | Gün sonu SOC | V2G (kWh) |")
        print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
        for name, df in res.items():
            m, s = df.mean(), df.std()
            print(f"| {name} | {m.maliyet_tl:.0f} ± {s.maliyet_tl:.0f} | {100 * (m.maliyet_tl / base.maliyet_tl - 1):+.0f}% | "
                  f"{m.tepe_alim_kw:.0f} | {100 * (m.tepe_alim_kw / base.tepe_alim_kw - 1):+.0f}% | {m.puant_payi:.2f} | "
                  f"{m.oz_tuketim:.2f} | {m.soc_son:.2f} | {m.v2g_kwh:.0f} |")

    # --- Grafik: Aralık tohum 0 ---
    day = "aralik"
    fig, ax = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True, gridspec_kw={"height_ratios": [3, 1.6]})
    colors = {"S2 Kontrolsüz": "#c0392b", "S3 Akıllı şarj (kural)": "#e67e22", "S4 + batarya (kural)": "#2980b9", "S5 MILP": "#27ae60"}
    for name, col in colors.items():
        s = series[(day, name)]
        ax[0].plot(s.index, s.grid_kw, label=name, color=col, lw=1.6)
    ax[0].axhline(cfg["grid"]["site_import_limit_kw"], color="k", ls="--", lw=1, label="site sınırı 180 kW")
    ax[0].set_ylabel("Şebekeden alım (kW)")
    ax[0].set_title("Aralık: şebekeden alım, senaryolara göre (tohum 0)")
    ax[0].set_ylim(0, 235)
    ax[0].legend(loc="upper center", fontsize=8, ncol=3)
    price = series[(day, "S2 Kontrolsüz")].price_tl_per_kwh
    for name in ("S4 + batarya (kural)", "S5 MILP"):
        ax[1].plot(series[(day, name)].index, series[(day, name)].bess_soc, label=f"batarya SOC, {name}", color=colors[name], lw=1.6)
    ax[1].set_ylabel("Batarya SOC")
    ax[1].set_ylim(0, 1.3)
    ax[1].set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    twin = ax[1].twinx()
    twin.fill_between(price.index, 0, price.values, step="post", color="grey", alpha=0.15)
    twin.set_ylabel("Tarife (TL/kWh)")
    twin.set_ylim(0, price.max() * 1.1)
    ax[1].legend(loc="upper left", fontsize=8, ncol=2)
    ax[1].xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%H:%M", tz=price.index.tz))
    fig.tight_layout()
    fig.savefig(OUT / "hafta9-ym3-senaryolar.png", dpi=130)
    print("\nGrafik: docs/raporlar/hafta9-ym3-senaryolar.png")

    # --- Duyarlılık: V2G aşınma bedeli (Aralık, tohum 0) ---
    c = with_start(cfg, TEMSILI_GUNLER["aralik"])
    inputs, _ = load_inputs(c, time_index(c), allow_mock=False)
    print("\n### V2G aşınma bedeli duyarlılığı (Aralık, tohum 0, S6 MILP)\n")
    print("| Aşınma (TL/kWh) | Maliyet (TL) | V2G (kWh) |")
    print("| ---: | ---: | ---: |")
    for wear in [0.0, 0.5, 1.0, 2.0, 4.0]:
        cw = copy.deepcopy(c)
        cw["ems"]["v2g_wear_tl_per_kwh"] = wear
        steps, st, _ = simulate(cw, inputs, lambda x: MilpEMS(x, v2g=True), 0.4, 0)
        k = kpis(cw, steps, st)
        print(f"| {wear:.1f} | {k['maliyet_tl']:.0f} | {k['v2g_kwh']:.0f} |")

    # --- Tahmin hatasının maliyeti: gerçek tarihli gün (Aralık hafta içi) ---
    ca = copy.deepcopy(cfg)
    ca["inputs"]["mode"] = "actual"
    ca["simulation"]["start"] = "2023-12-20 12:00"
    ia = time_index(ca)
    real = build_inputs(ca, ia)
    print("\n### Tahmin hatasının maliyeti (gerçek tarih 20 Aralık 2023, S5 MILP, 5 tohum ortalaması)\n")
    print("| Tahmin | Maliyet (TL) | Tepe alım (kW) |")
    print("| --- | ---: | ---: |")
    rows = {}
    for label, fc in [("kusursuz", None), ("blend (YM-1 yöntemi)", forecast_inputs(ca, ia))]:
        runs = []
        for seed in SEEDS:
            steps, st, _ = simulate(ca, real, lambda x: MilpEMS(x), 0.0, seed, forecast=fc)
            runs.append(kpis(ca, steps, st))
        rows[label] = pd.DataFrame(runs).mean()
        print(f"| {label} | {rows[label].maliyet_tl:.0f} | {rows[label].tepe_alim_kw:.0f} |")
    ref = []
    for seed in SEEDS:
        steps, st, _ = simulate(ca, real, lambda x: RuleBasedEMS(x, use_bess=True), 0.0, seed)
        ref.append(kpis(ca, steps, st))
    ref = pd.DataFrame(ref).mean()
    print(f"| (karşılaştırma: S4 kural tabanlı) | {ref.maliyet_tl:.0f} | {ref.tepe_alim_kw:.0f} |")


if __name__ == "__main__":
    main()
