"""Kural tabanlı akıllı şarj (YM-3, Hafta 5): SOC eşikleri + tarife.

Sorun: Kontrolsüz şarjda (Senaryo 2) araçlar akşam eve gelince aynı anda tam güçle şarj olur; bu puant
(17–22, en pahalı dilim) ve sitenin yük tepesiyle çakışır. Araçlar ise sabaha kadar bağlı kalıyor, enerji
ihtiyaçları birkaç saatlik tam güçle karşılanabiliyor. Kural, şarjı ayrılışa kadar olan pencerede en ucuz
adımlara yayar.

Her adımda, bağlı her araç için:

  1. Pencere: şimdiden ayrılışa kadar olan adımların fiyatları (tarife önceden bilinir; `prepare` fiyat
     serisini saklar).
  2. İhtiyaç: `energy_needed_kwh` (hedef SOC'ye kadar). Planlamada ünite gücünün yalnızca `safety` kadarına
     (varsayılan %80) güvenilir; çünkü ünite paylaşımı ve CC-CV bu gücü her zaman vermez.
  3. En ucuz adımlar seçilir: ihtiyacı karşılayana kadar fiyata göre sıralı adımlar alınır; sınırdaki fiyat
     diliminin tamamı kümeye katılır. Şu an bu kümedeyse araç ihtiyacını kümenin adımlarına EŞİT yayarak çeker,
     kümede değilse beklemeye geçer.
       Neden eşit yayma, tam güç değil: 20 araç gece diliminin ilk adımında tam güçle başlarsa 22:00'de yeni
       bir tepe doğar (geri tepme, "rebound peak"). Eşit yayma toplamı düz tutar.
  4. SOC eşiği: SOC `soc_floor`'un (varsayılan 0.30) altındaki araç tarifeye bakmadan hemen tam güçle
     taban SOC'ye kadar şarj edilir (sürücü beklenmedik bir yola çıkabilsin).
  5. Pencereye sığmayan ihtiyaç (geç gelen ya da çok boş araç) tam güçle şarj edilir.
  6. PV fazlası (PV > sabit yük) ücretsizdir: planlı şarjın üstüne, hedefe henüz ulaşmamış araçlara verilir.
  7. Toplam, `station_limit_kw` ve `site_limit_kw − sabit yük + PV` ile sınırlanır. Sınır yetmezse ayrılışa en
     yakın (en az boşluklu) araç önce doldurulur.

Batarya (Senaryo 4) ve V2G (Senaryo 6) kuralları bu sınıfa Hafta 6 ve 8'de eklenir.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from microgrid.interfaces import Decision, EmsInputs, VehicleRequest

_EPS = 1e-9


class RuleBasedEMS:
    def __init__(self, cfg: dict):
        e = cfg["ems"]
        self.soc_floor: float = e["soc_floor"]
        self.safety: float = e["safety"]
        self._price: np.ndarray | None = None

    # --- sözleşme ---

    def prepare(self, forecast: pd.DataFrame) -> None:
        """Yalnızca fiyat serisini saklar. Tarife önceden bilinen bir tablodur, tahmin gerektirmez."""
        self._price = forecast["price_tl_per_kwh"].to_numpy(dtype=float)

    def decide(self, inp: EmsInputs) -> Decision:
        ev = self._charge_plan(inp)
        ev = self._add_pv_surplus(inp, ev)
        ev = self._limit(inp, ev)
        return Decision(ev_kw=ev)

    # --- araç şarjı ---

    def _window_prices(self, inp: EmsInputs, v: VehicleRequest) -> np.ndarray:
        """Şimdiden ayrılışa kadarki adımların fiyatı. Fiyat serisi yoksa şimdiki fiyatın sabit olduğu varsayılır."""
        dt = inp.ctx.dt_h
        n_left = max(1, math.ceil((v.departure - inp.ctx.timestamp) / pd.Timedelta(hours=dt) - _EPS))
        if self._price is None:
            return np.full(n_left, inp.price_tl_per_kwh)
        step = inp.ctx.step
        return self._price[step: min(step + n_left, len(self._price))]

    def _planned_power(self, inp: EmsInputs, v: VehicleRequest) -> float:
        dt = inp.ctx.dt_h
        need = v.energy_needed_kwh
        if need <= 0:
            return 0.0
        cap_kw = min(v.max_charge_kw, need / dt)          # bu adımda verilebilecek en çok güç
        # 4. SOC eşiği: taban altındaki araç tarifeden bağımsız şarj olur
        floor_kw = 0.0
        if v.soc < self.soc_floor:
            floor_kw = min(v.max_charge_kw, (self.soc_floor - v.soc) * v.battery_kwh / dt)

        prices = self._window_prices(inp, v)
        step_kwh = v.max_charge_kw * self.safety * dt
        if len(prices) * step_kwh < need - _EPS or step_kwh <= 0:
            return cap_kw                                   # 5. pencereye sığmıyor: tam güç
        order = np.argsort(prices, kind="stable")
        cum = np.cumsum(np.full(len(order), step_kwh))
        marginal = prices[order[int(np.searchsorted(cum, need - _EPS))]]
        chosen = prices <= marginal + _EPS
        if not chosen[0]:
            return min(floor_kw, cap_kw)
        spread_kw = need / (chosen.sum() * dt)              # 3. kümenin adımlarına eşit yay
        return min(max(spread_kw, floor_kw), cap_kw)

    def _charge_plan(self, inp: EmsInputs) -> dict[str, float]:
        return {v.charger_id: self._planned_power(inp, v) for v in inp.vehicles}

    def _add_pv_surplus(self, inp: EmsInputs, ev: dict[str, float]) -> dict[str, float]:
        """6. PV'nin sabit yükü aşan kısmı henüz tam güçte olmayan araçlara verilir."""
        surplus = max(0.0, inp.pv_kw - inp.base_load_kw - sum(ev.values()))
        out = dict(ev)
        for v in self._by_urgency(inp):
            if surplus <= 0:
                break
            room = min(v.max_charge_kw, v.energy_needed_kwh / inp.ctx.dt_h) - out[v.charger_id]
            extra = max(0.0, min(room, surplus))
            out[v.charger_id] += extra
            surplus -= extra
        return out

    def _by_urgency(self, inp: EmsInputs) -> list[VehicleRequest]:
        """Boşluğu (ayrılışa kalan süre − tam güçle şarj süresi) en az olan araç önce."""
        def slack_h(v: VehicleRequest) -> float:
            left_h = (v.departure - inp.ctx.timestamp) / pd.Timedelta(hours=1)
            return left_h - v.energy_needed_kwh / max(v.max_charge_kw, _EPS)
        return sorted(inp.vehicles, key=slack_h)

    def _headroom_kw(self, inp: EmsInputs, bess_kw: float = 0.0) -> float:
        """EV'ye ayrılabilecek en çok toplam güç: istasyon sınırı ve sitenin şebeke sınırının bıraktığı pay."""
        site_room = inp.site_limit_kw - inp.base_load_kw + inp.pv_kw - bess_kw
        return max(0.0, min(inp.station_limit_kw, site_room))

    def _limit(self, inp: EmsInputs, ev: dict[str, float], bess_kw: float = 0.0) -> dict[str, float]:
        """7. Toplamı sınıra indirir; sınır yetmezse ayrılışa en yakın araç önce doldurulur."""
        room = self._headroom_kw(inp, bess_kw)
        if sum(ev.values()) <= room + _EPS:
            return ev
        out = {k: 0.0 for k in ev}
        for v in self._by_urgency(inp):
            give = min(ev[v.charger_id], room)
            out[v.charger_id] = give
            room -= give
            if room <= 0:
                break
        return out
