"""İstasyon analizleri (YM-2, Hafta 5).

- peak_vs_vehicle_count: kontrolsüz şarjda (S2) araç sayısı arttıkça istasyon ve şebeke tepe yükü nasıl değişiyor.
- critical_station_snapshot: istasyon yükünün en yüksek olduğu an; EM-1/EM-2 Simulink'te D2'yi (toplu araç
  bağlanması) bu değerlerle kurar. YM-4'ün simulink_io.critical_moment'ı şebeke alımına bakar, bu istasyona bakar.
"""
from __future__ import annotations

import pandas as pd

from microgrid.sim.loop import SimResult
from microgrid.sim.scenarios import SCENARIOS, apply_overrides, simulate

S2 = "S2 Kontrolsüz şarj"


def peak_vs_vehicle_count(cfg: dict, inputs: pd.DataFrame, counts: list[int]) -> pd.DataFrame:
    """Her araç sayısı için S2'yi bir kez çalıştırır; satır başına tepe değerler ve hedefe ulaşma oranı."""
    limit = cfg["grid"]["site_import_limit_kw"]
    rows = []
    for n in counts:
        r = simulate(apply_overrides(cfg, {"vehicles.count": n}), SCENARIOS[S2], inputs)
        s = r.steps
        rows.append({
            "arac_sayisi": n,
            "istasyon_tepe_kw": float(s.ev_kw.max()),
            "istasyon_tepe_saati": f"{s.ev_kw.idxmax():%H:%M}" if s.ev_kw.max() > 0 else "",
            "sebeke_tepe_kw": float(s.grid_kw.max()),
            "site_siniri_asim_adim": int((s.grid_kw > limit + 1e-9).sum()),
            "hedefe_ulasma_orani": float(r.sessions.reached_target.mean()) if len(r.sessions) else float("nan"),
        })
    return pd.DataFrame(rows)


def critical_station_snapshot(result: SimResult, cfg: dict) -> dict:
    """İstasyon gücünün en yüksek olduğu adım: kaç AC/DC ünite şarj ediyor, kaç araç bağlı, ortalama SOC."""
    steps, log = result.steps, result.station
    ts = steps.ev_kw.idxmax()
    now = log[log.timestamp == ts]
    charging = now[now.power_kw > 0]
    return {
        "zaman": f"{ts:%d.%m %H:%M}",
        "istasyon_kw": round(float(steps.ev_kw.max()), 1),
        "sarj_olan_ac": int(charging.charger_id.str.startswith("AC").sum()),
        "sarj_olan_dc": int(charging.charger_id.str.startswith("DC").sum()),
        "bagli_arac": int(len(now)),
        "ortalama_soc": round(float(now.soc.mean()), 3) if len(now) else float("nan"),
    }


def md_table(df: pd.DataFrame, index: bool = False) -> str:
    """Rapora kopyalanacak Markdown tablo (tabulate bağımlılığı eklememek için)."""
    d = df.reset_index() if index else df
    fmt = lambda x: f"{x:.2f}" if isinstance(x, float) else str(x)
    lines = ["| " + " | ".join(map(str, d.columns)) + " |", "|" + " --- |" * len(d.columns)]
    lines += ["| " + " | ".join(fmt(x) for x in row) + " |" for row in d.itertuples(index=False)]
    return "\n".join(lines)
