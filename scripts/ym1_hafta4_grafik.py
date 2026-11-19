"""Hafta 4 (v0) rapor grafiği: gerçek veriyle 24 saatlik döngü, kontrolsüz şarj.

Önce:   python -m microgrid.data && python -m microgrid.sim --gun ikisi
Sonra:  python scripts/ym1_hafta4_grafik.py
Çıktı:  docs/raporlar/hafta4-v0.png
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from microgrid.config import REPO_ROOT, load_config

cfg = load_config()
limit = cfg["grid"]["site_import_limit_kw"]
step_h = cfg["simulation"]["step_minutes"] / 60

fig, axes = plt.subplots(2, 2, figsize=(14, 7.5), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
for col, (name, title) in enumerate([("haziran", "Haziran"), ("aralik", "Aralık")]):
    path = REPO_ROOT / "results" / f"v0_{name}_steps.csv"
    if not path.exists():
        raise SystemExit(f"{path} yok. Önce: python -m microgrid.sim --gun ikisi")
    s = pd.read_csv(path, index_col=0)
    x = np.arange(len(s)) * step_h

    ax = axes[0, col]
    ax.fill_between(x, s["pv_kw"], color="tab:orange", alpha=0.35, label="PV")
    ax.plot(x, s["base_load_kw"], color="black", lw=1.5, label="Sabit yük")
    ax.plot(x, s["ev_kw"], color="tab:blue", lw=1.5, label="Şarj istasyonu")
    ax.plot(x, s["grid_kw"], color="tab:red", lw=2.2, label="Şebekeden alım")
    ax.axhline(limit, color="tab:red", ls="--", lw=1, label=f"Site sınırı {limit} kW")
    ax.axhline(cfg["station"]["power_limit_kw"], color="tab:blue", ls=":", lw=1, label="İstasyon sınırı 150 kW")
    ax.set(title=f"{title} temsili gün · kontrolsüz şarj · maliyet {s['cost_tl'].sum():.0f} TL", ylabel="kW", ylim=(-80, 200))
    ax.grid(alpha=0.3)
    if col == 0:
        ax.legend(fontsize=8, loc="upper left")

    ax = axes[1, col]
    ax.plot(x, s["min_vm_pu"], color="tab:green", lw=1.5)
    ax.axhline(cfg["grid"]["voltage_min_pu"], color="tab:green", ls="--", lw=1)
    ax.set(ylabel="En düşük gerilim (p.u.)", ylim=(0.94, 1.02))
    ax.grid(alpha=0.3)
    ticks = np.arange(0, 25, 3)
    ax.set_xticks(ticks, [f"{(12 + t) % 24:02d}:00" for t in ticks])

fig.suptitle(f"v0 · {cfg['site']['name']} · gerçek PV/yük/tarife, sahte istasyon ve EMS (Senaryo 2)")
fig.tight_layout()
out = REPO_ROOT / "docs" / "raporlar" / "hafta4-v0.png"
fig.savefig(out, dpi=150)
print(f"Yazıldı: {out}")
