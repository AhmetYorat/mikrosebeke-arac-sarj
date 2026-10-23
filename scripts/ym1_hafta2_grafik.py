"""Hafta 2 rapor grafiği (YM-1): temiz PV verisi ve sabit yük profilleri.

Önce veriyi hazırla:
    python -m microgrid.data.pvgis
    python -m microgrid.data.loads
Sonra:
    python scripts/ym1_hafta2_grafik.py
Çıktı: docs/raporlar/hafta2-ym1-pv-yuk.png
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from microgrid.config import REPO_ROOT, load_config
from microgrid.data import loads as loads_mod
from microgrid.data import pvgis
from microgrid.data.loads import average_day

cfg = load_config()
pv_kw = pvgis.load(pvgis.processed_path(cfg))["pv_kw_per_kwp"] * cfg["pv"]["installed_kw"]
loads = loads_mod.load(loads_mod.processed_path(cfg))
loads["pv_kw"] = pv_kw

fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))

for ax, (month, name) in zip(axes[:2], [(6, "Haziran"), (12, "Aralık")]):
    day = average_day(loads, months=[month], weekdays=[0, 1, 2, 3, 4])
    ax.fill_between(day.index, day["pv_kw"], color="tab:orange", alpha=0.35, label="PV üretimi")
    ax.plot(day.index, day["residential_kw"], marker="o", ms=3, color="tab:blue", label="Konut")
    ax.plot(day.index, day["commercial_kw"], marker="o", ms=3, color="tab:green", label="Ticari")
    ax.plot(day.index, day["total_kw"], color="black", lw=2, label="Toplam sabit yük")
    ax.axvspan(17, 22, color="tab:red", alpha=0.1, label="Puant (17–22)")
    ax.set(title=f"{name}, hafta içi ortalama gün", xlabel="Saat", ylabel="kW", xticks=range(0, 24, 3))
    ax.grid(alpha=0.3)
axes[0].legend(fontsize=8)
ymax = max(ax.get_ylim()[1] for ax in axes[:2])
for ax in axes[:2]:
    ax.set_ylim(0, ymax)

monthly = loads[["pv_kw", "total_kw"]].resample("ME").sum() / 1000
x = range(1, 13)
axes[2].bar([i - 0.2 for i in x], monthly["pv_kw"], width=0.4, color="tab:orange", label="PV üretimi")
axes[2].bar([i + 0.2 for i in x], monthly["total_kw"], width=0.4, color="tab:gray", label="Sabit yük")
axes[2].set(title="Aylık enerji", xlabel="Ay", ylabel="MWh", xticks=list(x))
axes[2].legend(fontsize=8)
axes[2].grid(alpha=0.3, axis="y")

res = cfg["loads"]["residential"]
fig.suptitle(
    f"{cfg['site']['name']} · PV {cfg['pv']['installed_kw']} kWp · "
    f"{res['households']} daire + ticari {cfg['loads']['commercial']['annual_kwh'] / 1000:.0f} MWh/yıl · {cfg['loads']['year']}"
)
fig.tight_layout()
out = REPO_ROOT / "docs" / "raporlar" / "hafta2-ym1-pv-yuk.png"
fig.savefig(out, dpi=150)
print(f"Yazıldı: {out}")
