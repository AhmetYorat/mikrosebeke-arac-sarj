"""Şarj stratejileri ve kullanıcı memnuniyeti (YM-2, Hafta 6).

İstasyon her ünite için 0 ile max_charge_kw arasındaki her gücü kabul eder (ünite güç modülasyonu). Buradaki
fonksiyonlar bu modülasyonun kurallarıdır; YM-3'ün EMS'i decide() içinde doğrudan çağırabilir:

    budget = min(inp.station_limit_kw, inp.site_limit_kw - inp.base_load_kw + inp.pv_kw)
    Decision(ev_kw=by_departure(inp.vehicles, budget, inp.ctx.dt_h, eff=cfg["station"]["charge_efficiency"]))

satisfaction: SimResult.sessions'tan kullanıcı memnuniyeti KPI'ları (YM-1'in KPI tablosuna eklenecek).
"""
from __future__ import annotations

import pandas as pd

from microgrid.interfaces import VehicleRequest


def _want_kw(v: VehicleRequest, dt_h: float, eff: float) -> float:
    """Aracın bu adımda isteyebileceği en yüksek güç: ünite/CC-CV sınırı veya hedefe kalan enerji (şebeke tarafı).

    energy_needed_kwh batarya tarafıdır; şebekeden çekilmesi gereken bunun 1/η katıdır. Verimi hesaba katmamak
    her adımda ihtiyacın %5'ini bırakır ve araç hedefe asimptotik yaklaşıp üniteyi gereksiz yere tutar.
    """
    return min(v.max_charge_kw, v.energy_needed_kwh / (dt_h * eff))


def uncontrolled(vehicles: list[VehicleRequest], dt_h: float, *, eff: float) -> dict[str, float]:
    """Kontrolsüz şarj: her araç geldiği an çekebildiği en yüksek güçle. eff: station.charge_efficiency (zorunlu)."""
    return {v.charger_id: _want_kw(v, dt_h, eff) for v in vehicles}


def by_departure(vehicles: list[VehicleRequest], budget_kw: float, dt_h: float, *, eff: float) -> dict[str, float]:
    """Güç bütçesini ayrılışı en yakın araçtan başlayarak dağıtır; eşit ayrılışta daha çok enerji isteyen önce.

    Toplam hiçbir zaman bütçeyi, araç başına güç hiçbir zaman aracın sınırını aşmaz. Bütçe yeterliyse sonuç
    kontrolsüz şarjla aynıdır.
    """
    out = {v.charger_id: 0.0 for v in vehicles}
    left = max(0.0, budget_kw)
    for v in sorted(vehicles, key=lambda v: (v.departure, -v.energy_needed_kwh)):
        p = min(_want_kw(v, dt_h, eff), left)
        out[v.charger_id] = p
        left -= p
    return out


def satisfaction(sessions: pd.DataFrame) -> pd.Series:
    """Kullanıcı memnuniyeti KPI'ları (SimResult.sessions'tan).

    arac_sayisi (adet), hedefe_ulasma_orani (0–1), hizmet_alamayan (adet; hiç üniteye bağlanamayan),
    ortalama_eksik_kwh (kWh; ayrılışta hedefe kalan enerji ortalaması), ortalama_bekleme_saat (saat; ünite beklemesi).
    """
    n = len(sessions)
    if n == 0:
        nan = float("nan")
        return pd.Series({"arac_sayisi": 0, "hedefe_ulasma_orani": nan, "hizmet_alamayan": 0,
                          "ortalama_eksik_kwh": nan, "ortalama_bekleme_saat": nan})
    missing = ((sessions.target_soc - sessions.soc_final).clip(lower=0) * sessions.battery_kwh)
    return pd.Series({
        "arac_sayisi": n,
        "hedefe_ulasma_orani": float(sessions.reached_target.mean()),
        "hizmet_alamayan": int(sessions.first_charger.isna().sum()),
        "ortalama_eksik_kwh": float(missing.mean()),
        "ortalama_bekleme_saat": float(sessions.waited_h.mean()),
    })
