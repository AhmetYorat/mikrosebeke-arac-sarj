"""Optimizasyonlu EMS (YM-3, Hafta 7): kayan ufuklu MILP (PuLP), Senaryo 5.

Neden kayan ufuk (her adımda yeniden çözüm), gün başında tek çözüm değil:
sözleşme MILP'in tüm günü `prepare`'de çözmesini öngörüyordu, ama araçların geliş saati, SOC'si ve ayrılışı
gün başında bilinmiyor; istasyon bunları adım adım `requests()` ile veriyor. Bu yüzden:

  - `prepare(forecast)`: günün PV / sabit yük / fiyat tahminini saklar (YM-1, `data.forecast`).
  - `decide(inp)`: şimdi bağlı araçlarla, bu adımdan gün sonuna kadar olan ufku çözer ve yalnızca ilk adımı
    uygular. Şimdiki adım için gerçek değerler (inp), sonrası için tahmin kullanılır. Yeni araç geldikçe,
    SOC beklenenden saptıkça plan kendiliğinden güncellenir.

Model (t = bu adımdan gün sonuna, dt = adım süresi). Tüm güçler kW, işaretler docs/arayuz-sozlesmesi.md'deki gibi.

Karar değişkenleri
  ch[v,t] ≥ 0     araç v'nin şarj gücü, ≤ max_charge_kw; yalnızca ayrılışa kadarki adımlarda
  bch[t], bdis[t] ≥ 0   batarya şarj/deşarj, ≤ power_kw; ikili değişken z[t] aynı adımda ikisini yasaklar
  imp[t], exp[t] ≥ 0    şebekeden alım / şebekeye veriş
  soc[t]          batarya SOC'si

Kısıtlar
  güç dengesi     imp − exp = yük + Σ(ch − dis) + bch − bdis − PV
  istasyon        Σ(ch − dis) ≤ station_limit_kw
  site            imp ≤ site_limit_kw (+ cezalı gevşeme: sınır asla gerçekten çözümsüz kalmasın)
  batarya         soc[t+1] = soc[t] + (η·bch − bdis/η)·dt/kapasite;  soc_min ≤ soc ≤ soc_max;
                  gün sonu SOC ≥ bess.soc_initial (gün başı = gün sonu; aksi hâlde batarya "bedava" boşalırdı)
  araç hedefi     Σ ch·dt·η_ev ≥ ihtiyaç (yetmezse cezalı gevşeme)

Amaç (TL)
  Σ fiyat·imp·dt − satış_fiyatı·exp·dt                  enerji maliyeti
  + peak_weight·tepe                                      tepe alımı küçük bir ağırlıkla bastırır (aynı maliyetli çözümler
                                                           arasında düz olanı seçtirir; projenin ana sorusu tepe yükü)
  + bess_wear·Σ bdis·dt                                   gereksiz çevrimi önleyen aşınma bedeli
  − early_bias·Σ depolanan_enerji[t]                      eşit maliyetli seçeneklerde enerjiyi erken depolatır
  + vehicle_early·Σ t·ch[v,t]·dt                          eşit maliyetli adımlarda aracı erken şarj ettirir
  + ceza·(karşılanamayan araç enerjisi, site aşımı, gün sonu SOC açığı)

Çözüm bulunamazsa (zaman aşımı, çözümsüz) o adım `RuleBasedEMS`'e düşer; `fallbacks` sayacı bunu raporlar.
"""
from __future__ import annotations

import math

import pandas as pd

from microgrid.ems.rule_based import RuleBasedEMS
from microgrid.interfaces import Decision, EmsInputs, VehicleRequest

_EPS = 1e-9
_CLEAN = 1e-6      # çözücü gürültüsü: bundan küçük güçler sıfır sayılır


def _pulp():
    try:
        import pulp
    except ImportError as e:  # pragma: no cover
        raise ImportError("MILP için PuLP gerekli: pip install -r requirements.txt") from e
    return pulp


class MilpEMS:
    def __init__(self, cfg: dict):
        self.pulp = _pulp()
        e = cfg["ems"]
        self.bess = cfg["bess"]
        self.safety_cfg = e
        self.ev_eff = cfg["station"].get("charge_efficiency", 1.0)
        self.export_price = e["export_price_tl_per_kwh"]
        self.peak_weight = e["milp_peak_weight_tl_per_kw"]
        self.unmet_penalty = e["milp_unmet_penalty_tl_per_kwh"]
        self.site_penalty = e["milp_site_penalty_tl_per_kw"]
        self.bess_wear = e["bess_wear_tl_per_kwh"]
        self.early_bias = e["milp_early_bias_tl_per_kwh_step"]
        self.vehicle_early = e["milp_vehicle_early_tl_per_kwh_step"]
        self.time_limit_s = e["milp_time_limit_s"]
        self.gap = e["milp_gap"]
        self._fallback = RuleBasedEMS(cfg, use_bess=True)
        self._forecast: pd.DataFrame | None = None
        self._peak_so_far = 0.0
        self.fallbacks = 0
        self.solves = 0

    # --- sözleşme ---

    def prepare(self, forecast: pd.DataFrame) -> None:
        self._forecast = forecast[["pv_kw", "base_load_kw", "price_tl_per_kwh"]].reset_index(drop=True)
        self._peak_so_far = 0.0
        self._fallback.prepare(forecast)

    def decide(self, inp: EmsInputs) -> Decision:
        if self._forecast is None:
            raise RuntimeError("MilpEMS.prepare() çağrılmadan decide() çağrılamaz")
        try:
            d = self._solve(inp)
        except Exception:      # çözücü hatası EMS'i durdurmasın; ayrıntı için fallbacks sayacına bak
            d = None
        if d is None:
            self.fallbacks += 1
            d = self._fallback.decide(inp)
        self._peak_so_far = max(
            self._peak_so_far, inp.base_load_kw + sum(d.ev_kw.values()) + d.bess_kw - inp.pv_kw)
        return d

    # --- model ---

    def _horizon(self, inp: EmsInputs):
        """Bu adımdan gün sonuna pv, yük, fiyat dizileri. İlk eleman gerçek değer, kalanı tahmin."""
        f = self._forecast.iloc[inp.ctx.step:]
        pv, base, price = (f[c].to_numpy(dtype=float).copy() for c in ("pv_kw", "base_load_kw", "price_tl_per_kwh"))
        if len(pv) == 0:
            return None
        pv[0], base[0], price[0] = inp.pv_kw, inp.base_load_kw, inp.price_tl_per_kwh
        return pv, base, price

    def _vehicle_steps(self, inp: EmsInputs, v: VehicleRequest, H: int) -> int:
        n = math.ceil((v.departure - inp.ctx.timestamp) / pd.Timedelta(hours=inp.ctx.dt_h) - _EPS)
        return max(0, min(H, n))

    def _solve(self, inp: EmsInputs) -> Decision | None:
        pl = self.pulp
        hz = self._horizon(inp)
        if hz is None:
            return None
        pv, base, price = hz
        H, dt = len(pv), inp.ctx.dt_h
        b = self.bess
        P, cap, eta = b["power_kw"], b["capacity_kwh"], b["efficiency"]

        prob = pl.LpProblem("ems", pl.LpMinimize)
        Var = pl.LpVariable
        obj = []

        # --- batarya ---
        bch = [Var(f"bch_{t}", 0, P) for t in range(H)]
        bdis = [Var(f"bdis_{t}", 0, P) for t in range(H)]
        z = [Var(f"z_{t}", cat="Binary") for t in range(H)]
        soc = [Var(f"soc_{t}", b["soc_min"], b["soc_max"]) for t in range(H + 1)]
        prob += soc[0] == min(max(inp.bess_soc, b["soc_min"]), b["soc_max"])
        for t in range(H):
            prob += bch[t] <= P * z[t]
            prob += bdis[t] <= P * (1 - z[t])
            prob += soc[t + 1] == soc[t] + (eta * bch[t] - bdis[t] / eta) * dt / cap
        end_gap = Var("soc_end_gap", 0)
        prob += soc[H] + end_gap >= b["soc_initial"]
        obj.append(self.unmet_penalty * cap * end_gap)                 # gün sonu SOC açığı: hedef neredeyse sert kısıt
        obj.append(self.bess_wear * dt * pl.lpSum(bdis))
        # Eşit maliyetli seçenekler arasında enerjiyi erken depola / geç boşalt: kayan ufukta "sonra yaparım" tuzağını önler
        obj.append(-self.early_bias * cap * pl.lpSum(soc[1:]))

        # --- araçlar ---
        ev_net = [[] for _ in range(H)]                                # t -> araç net güç ifadeleri (şarj − deşarj)
        ch_first: dict[str, object] = {}
        for k, v in enumerate(inp.vehicles):
            n = self._vehicle_steps(inp, v, H)
            if n == 0:
                continue
            ch = [Var(f"ch_{k}_{t}", 0, max(v.max_charge_kw, 0.0)) for t in range(n)]
            unmet = Var(f"unmet_{k}", 0)
            obj.append(self.unmet_penalty * unmet)
            prob += self.ev_eff * dt * pl.lpSum(ch) + unmet >= v.energy_needed_kwh
            for t in range(n):
                ev_net[t].append(ch[t])
            obj.append(self.vehicle_early * dt * pl.lpSum(t * ch[t] for t in range(n)))   # eşitlikte erken şarj
            ch_first[v.charger_id] = ch[0]

        # --- şebeke ---
        imp = [Var(f"imp_{t}", 0) for t in range(H)]
        exp = [Var(f"exp_{t}", 0) for t in range(H)]
        peak = Var("peak", self._peak_so_far)
        for t in range(H):
            prob += imp[t] - exp[t] == base[t] - pv[t] + pl.lpSum(ev_net[t]) + bch[t] - bdis[t]
            prob += pl.lpSum(ev_net[t]) <= inp.station_limit_kw
            over = Var(f"over_{t}", 0)
            prob += imp[t] <= inp.site_limit_kw + over
            prob += peak >= imp[t]
            obj.append(self.site_penalty * over)
            obj.append(float(price[t]) * dt * imp[t] - self.export_price * dt * exp[t])
        obj.append(self.peak_weight * peak)

        prob += pl.lpSum(obj)
        solver = pl.PULP_CBC_CMD(msg=False, timeLimit=self.time_limit_s, gapRel=self.gap)
        prob.solve(solver)
        self.solves += 1
        if pl.LpStatus[prob.status] != "Optimal":
            return None

        def val(x) -> float:
            v_ = x.value() or 0.0
            return 0.0 if abs(v_) < _CLEAN else float(v_)

        ev = {cid: val(x) for cid, x in ch_first.items()}
        bess = val(bch[0]) - val(bdis[0])
        # çözücü gürültüsü yüzünden sınır dışına taşan değerleri kırp
        for v in inp.vehicles:
            if v.charger_id in ev:
                ev[v.charger_id] = min(max(ev[v.charger_id], 0.0), v.max_charge_kw)
        return Decision(ev_kw={v.charger_id: ev.get(v.charger_id, 0.0) for v in inp.vehicles}, bess_kw=bess)
