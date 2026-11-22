"""Hafta 9 (YM-2): şarj istasyonu rapor bölümünün grafik ve tabloları.

    python scripts/ym2_rapor_grafikleri.py
Çıktı (docs/rapor/): ym2-cc-cv.png, ym2-unite-dolulugu.png, ym2-memnuniyet.md
Veri (data/processed/) yoksa sahte girdiyle çalışır ve başlıklara "SAHTE GİRDİ" yazar.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from microgrid.config import REPO_ROOT, load_config
from microgrid.sim.loop import time_index
from microgrid.sim.scenarios import SCENARIOS, apply_overrides, simulate
from microgrid.sim.setup import SAHTE, TEMSILI_GUNLER, load_inputs, with_start
from microgrid.station import cc_cv_limit, satisfaction
from microgrid.station.analysis import md_table

OUT = REPO_ROOT / "docs" / "rapor"
OUT.mkdir(exist_ok=True)
base = load_config()
st = base["station"]

# 1) CC-CV eğrisi
soc = np.linspace(0, 1, 201)
fig, ax = plt.subplots(figsize=(6, 3.2))
for p, lbl in [(22, "AC 22 kW"), (11, "AC, 11 kW OBC"), (50, "DC 50 kW")]:
    ax.plot(soc, [cc_cv_limit(s, p, st["cv_threshold_soc"], st["cv_min_fraction"]) for s in soc], label=lbl)
ax.axvline(st["cv_threshold_soc"], ls="--", c="gray", lw=1)
ax.set(xlabel="SOC", ylabel="En yüksek şarj gücü (kW)", title="CC-CV şarj eğrisi")
ax.legend(fontsize=8); ax.grid(alpha=0.3); fig.tight_layout()
fig.savefig(OUT / "ym2-cc-cv.png", dpi=150)

# 2) Ünite doluluğu (S2, Haziran) ve 3) memnuniyet tablosu
cfg = with_start(base, TEMSILI_GUNLER["haziran"])
inputs, source = load_inputs(cfg, time_index(cfg))
tag = "  (SAHTE GİRDİ)" if source == SAHTE else ""
r = simulate(cfg, SCENARIOS["S2 Kontrolsüz şarj"], inputs)
log = r.station
pivot = log.pivot_table(index="charger_id", columns="timestamp", values="power_kw", aggfunc="sum")
pivot = pivot.reindex(sorted(pivot.index, key=lambda c: (c[:2] != "AC", int(c[2:]))))
fig, ax = plt.subplots(figsize=(10, 3.4))
im = ax.imshow(pivot.fillna(-1).values, aspect="auto", cmap="viridis", vmin=0, interpolation="nearest")
im.cmap.set_under("#eeeeee")
ticks = range(0, pivot.shape[1], 8)
ax.set_xticks(list(ticks), [f"{pivot.columns[i]:%H:%M}" for i in ticks])
ax.set_yticks(range(len(pivot.index)), pivot.index)
fig.colorbar(im, ax=ax, label="kW")
ax.set_title("S2 kontrolsüz şarj, Haziran: ünite başına güç (gri: ünite boş ya da araç dolu)" + tag)
fig.tight_layout()
fig.savefig(OUT / "ym2-unite-dolulugu.png", dpi=150)

variants = {name: (sc, {}) for name, sc in SCENARIOS.items() if name != "S1 Temel (araç yok)"}
variants["S2, nöbetleşe kapalı"] = (SCENARIOS["S2 Kontrolsüz şarj"], {"station.rotate_when_full": False})
rows = {}
for name, (sc, over) in variants.items():
    res = simulate(apply_overrides(cfg, over), sc, inputs)
    k = satisfaction(res.sessions)
    k["arac_sarj_kwh"] = res.steps.ev_kw.clip(lower=0).sum() * cfg["simulation"]["step_minutes"] / 60
    k["istasyon_tepe_kw"] = res.steps.ev_kw.max()
    rows[name] = k
table = md_table(pd.DataFrame(rows), index=True)
(OUT / "ym2-memnuniyet.md").write_text(f"Girdi: {source}, Haziran temsili günü\n\n{table}\n", encoding="utf-8")
print(f"Girdi: {source}\n\n{table}\n\nYazıldı: {OUT}")
