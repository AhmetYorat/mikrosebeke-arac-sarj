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

Batarya (`use_bess=True`, Senaryo 4), araçlardan sonra, kalan net yüke bakarak şu sırayla karar verir:

  a. Site sınırı: araç şarjı sonrası şebeke alımı `site_limit_kw`'ı aşacaksa batarya aradaki farkı verir
     (SOC tabanına kadar, tarifeden bağımsız). Bu kural diğerlerinden önce gelir.
  b. PV fazlası: PV, sabit yük ve araçları aştıysa fazla bataryaya girer (şebekeye satış ücretsiz olduğu
     için boşa gitmesin).
  c. Puant: en pahalı dilimde net yük varsa batarya bu yükü karşılar. Enerji, kalan puant adımlarına
     eşit paylaştırılır; ilk saatte boşalıp son saatte kalmasın.
  d. Gece: en ucuz dilimde SOC `ems.bess_night_target_soc`'un altındaysa şebekeden şarj olur; eksik enerji
     kalan ucuz adımlara eşit yayılır (yeni tepe oluşmasın) ve site sınırını aşmaz.

Gece hedef SOC'si başlangıç SOC'sine (0.5) eşittir: temsili gün tekrar eden bir gün sayıldığı için
gün sonunda batarya gün başındaki seviyeye döner; aksi hâlde gün sonunda depoda kalan enerji maliyetsiz
görünür ve senaryolar adil karşılaştırılamazdı.

V2G (`v2g=True`, Senaryo 6), batarya kararından sonra kalan net yükü araçlardan karşılar:

  e. Puantta (veya site sınırı aşılacaksa, tarifeden bağımsız) V2G'ye uygun ve o adım şarj olmayan araçlar
     net yükü paylaşarak karşılar. Bir aracın verebileceği enerji iki şeyle sınırlıdır:
       - taban SOC: araç `ems.v2g_soc_floor`'un (0.30) altına indirilmez (minimum SOC garantisi);
       - ayrılışta hedef SOC: deşarjdan sonra kalan ucuz adımlarda (ünite gücünün `safety` kadarıyla) hedefe
         yeniden dolabilmeli (ayrılışta hedef SOC garantisi).
     Enerji kalan puant adımlarına eşit paylaştırılır. Batarya önce, araçlar kalan yük için devreye girer
     (batarya aşınması araç bataryasından ucuz).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from microgrid.interfaces import Decision, EmsInputs, VehicleRequest

_EPS = 1e-9


class RuleBasedEMS:
    def __init__(self, cfg: dict, use_bess: bool = False, v2g: bool = False):
        e = cfg["ems"]
        self.soc_floor: float = e["soc_floor"]
        self.safety: float = e["safety"]
        self.use_bess = use_bess
        self.v2g = v2g
        self.v2g_floor: float = e["v2g_soc_floor"]
        self.v2g_eff: float = e["v2g_efficiency"]          # V2G deşarjında araç bataryasından çekilen = güç·dt / verim
        # energy_needed_kwh batarya tarafıdır; istasyon (YM-2) şebeke gücünü bu verimle bataryaya aktarır. Planlama
        # şebeke tarafında yapılır (MilpEMS ile aynı). Yoksa her adım ihtiyacın %5'i eksik kalır (YM-4 entegrasyonu).
        self.ev_eff: float = cfg["station"].get("charge_efficiency", 1.0)
        self.bess = cfg["bess"]
        self.night_target_soc: float = e["bess_night_target_soc"]
        self._price: np.ndarray | None = None

    # --- sözleşme ---

    def prepare(self, forecast: pd.DataFrame) -> None:
        """Yalnızca fiyat serisini saklar. Tarife önceden bilinen bir tablodur, tahmin gerektirmez."""
        self._price = forecast["price_tl_per_kwh"].to_numpy(dtype=float)

    def decide(self, inp: EmsInputs) -> Decision:
        ev = self._add_pv_surplus(inp, self._charge_plan(inp))
        if not self.use_bess:
            ev, bess = self._limit(inp, ev), 0.0
        else:
            # a. Site sınırı için gereken deşarj, araç sınırlaması için gereken payı da büyütür
            ev = self._limit(inp, ev, site=False)
            site_duty_kw = min(
                self.bess["power_kw"],
                max(0.0, inp.base_load_kw + sum(ev.values()) - inp.pv_kw - inp.site_limit_kw))
            ev = self._limit(inp, ev, bess_kw=-site_duty_kw)
            net = inp.base_load_kw + sum(ev.values()) - inp.pv_kw
            bess = self._bess_power(inp, net)
            if site_duty_kw > 0 and -bess < site_duty_kw:
                bess = -site_duty_kw
        if self.v2g:
            ev = self._v2g(inp, ev, inp.base_load_kw + sum(ev.values()) + bess - inp.pv_kw)
        return Decision(ev_kw=ev, bess_kw=bess)

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
        need = v.energy_needed_kwh / self.ev_eff          # şebeke tarafı
        if need <= 0:
            return 0.0
        cap_kw = min(v.max_charge_kw, need / dt)          # bu adımda verilebilecek en çok güç
        # 4. SOC eşiği: taban altındaki araç tarifeden bağımsız şarj olur
        floor_kw = 0.0
        if v.soc < self.soc_floor:
            floor_kw = min(v.max_charge_kw, (self.soc_floor - v.soc) * v.battery_kwh / (dt * self.ev_eff))

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
            room = min(v.max_charge_kw, v.energy_needed_kwh / (inp.ctx.dt_h * self.ev_eff)) - out[v.charger_id]
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

    def _limit(self, inp: EmsInputs, ev: dict[str, float], bess_kw: float = 0.0, site: bool = True) -> dict[str, float]:
        """7. Toplamı sınıra indirir; sınır yetmezse ayrılışa en yakın araç önce doldurulur.

        site=False yalnızca istasyon sınırını uygular (bataryanın site sınırına katkısı henüz bilinmiyor)."""
        room = self._headroom_kw(inp, bess_kw) if site else inp.station_limit_kw
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

    # --- batarya ---

    def _remaining_steps(self, inp: EmsInputs, price: float, cmp) -> int:
        """Şimdiden gün sonuna kadar fiyatı `cmp(p, price)` koşulunu sağlayan adım sayısı (şu an dahil)."""
        if self._price is None:
            return 0
        tail = self._price[inp.ctx.step:]
        return int(cmp(tail, price).sum())

    def _bess_power(self, inp: EmsInputs, net_kw: float) -> float:
        """b-d kuralları. net_kw = sabit yük + araçlar − PV (> 0 şebekeden çekilecek, < 0 PV fazlası)."""
        b, dt = self.bess, inp.ctx.dt_h
        power, cap, eta = b["power_kw"], b["capacity_kwh"], b["efficiency"]
        stored = (inp.bess_soc - b["soc_min"]) * cap                     # taban üstündeki enerji
        room = (b["soc_max"] - inp.bess_soc) * cap

        # b. PV fazlası
        if net_kw < 0:
            return min(-net_kw, power, room / (dt * eta))
        if self._price is None:
            return 0.0
        lo, hi = float(self._price.min()), float(self._price.max())
        if hi - lo < _EPS:
            return 0.0                                                   # düz tarifede arbitraj yok

        # c. puant: net yükü karşıla, enerjiyi kalan puant adımlarına paylaştır
        if inp.price_tl_per_kwh >= hi - _EPS:
            n = max(1, self._remaining_steps(inp, hi, lambda a, x: a >= x - _EPS))
            share_kw = stored * eta / (n * dt)
            return -min(net_kw, power, share_kw)

        # d. gece: hedef SOC'ye kadar kalan ucuz adımlara eşit yayarak şarj
        if inp.price_tl_per_kwh <= lo + _EPS and inp.bess_soc < self.night_target_soc - _EPS:
            n = max(1, self._remaining_steps(inp, lo, lambda a, x: a <= x + _EPS))
            need_kwh = (self.night_target_soc - inp.bess_soc) * cap
            p = need_kwh / (n * dt * eta)
            return max(0.0, min(p, power, room / (dt * eta), inp.site_limit_kw - net_kw))
        return 0.0

    # --- V2G ---

    def _v2g_usable_kwh(self, inp: EmsInputs, v: VehicleRequest) -> float:
        """Aracın bu adımdan sonra bataryasından çekilebilecek enerji (araç bataryası tarafı, kWh)."""
        above_floor = max(0.0, (v.soc - self.v2g_floor) * v.battery_kwh)
        prices = self._window_prices(inp, v)
        if len(prices) == 0:
            return 0.0
        lo = float(self._price.min()) if self._price is not None else float(prices.min())
        cheap_steps = int((prices <= lo + _EPS).sum())
        refill_kwh = cheap_steps * v.max_charge_kw * self.safety * inp.ctx.dt_h * self.v2g_eff
        return max(0.0, min(above_floor, refill_kwh - v.energy_needed_kwh))

    def _v2g(self, inp: EmsInputs, ev: dict[str, float], net_kw: float) -> dict[str, float]:
        """e. Kalan net yükü V2G'ye uygun araçlardan karşıla (puantta ya da site sınırı için)."""
        if self._price is None:
            return ev
        hi = float(self._price.max())
        in_puant = hi - float(self._price.min()) > _EPS and inp.price_tl_per_kwh >= hi - _EPS
        target_kw = max(net_kw if in_puant else 0.0, net_kw - inp.site_limit_kw)
        if target_kw <= _EPS:
            return ev
        dt = inp.ctx.dt_h
        n_puant = max(1, self._remaining_steps(inp, hi, lambda a, x: a >= x - _EPS)) if in_puant else 1
        caps: dict[str, float] = {}
        for v in inp.vehicles:
            if v.max_discharge_kw <= _EPS or ev.get(v.charger_id, 0.0) > _EPS:
                continue                                   # V2G'siz araç ya da bu adım şarj olan araç
            share_kw = self._v2g_usable_kwh(inp, v) * self.v2g_eff / (n_puant * dt)
            caps[v.charger_id] = min(v.max_discharge_kw, share_kw)
        total = sum(caps.values())
        if total <= _EPS:
            return ev
        scale = min(1.0, target_kw / total)
        out = dict(ev)
        for cid, c in caps.items():
            out[cid] = -c * scale
        return out
