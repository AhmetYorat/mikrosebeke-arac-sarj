"""Sahte (mock) modüller. Döngüyü gerçek modüller gelmeden uçtan uca çalıştırmak için.

Her biri sözleşmedeki arayüzü en basit hâliyle uygular. Gerçek modüller geldikçe
(YM-1 profiller, YM-2 istasyon, YM-3 EMS/BESS) testler dışında kullanılmayacak.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from microgrid.interfaces import Decision, EmsInputs, StepContext, VehicleRequest


def mock_inputs(cfg: dict, index: pd.DatetimeIndex) -> pd.DataFrame:
    """Çan eğrisi PV, akşam pikli sabit yük ve config'teki tarife."""
    hour = index.hour + index.minute / 60
    pv = cfg["pv"]["installed_kw"] * 0.65 * np.clip(np.sin(np.pi * (hour - 6) / 14), 0, None)
    base = 30 + 25 * np.exp(-0.5 * ((hour - 20) / 2) ** 2)

    def price(h):
        for p in cfg["tariff"]["periods"]:
            s, e = p["start"], p["end"]
            if (s <= h < e) if s < e else (h >= s or h < e):
                return p["price_tl_per_kwh"] or 0.0
        return 0.0

    return pd.DataFrame(
        {"pv_kw": pv, "base_load_kw": base, "price_tl_per_kwh": [price(h) for h in hour]},
        index=index,
    )


class MockStation:
    """Araçlar config'teki dağılımdan gelir, boş üniteye bağlanır. CC-CV ve V2G yok."""

    def __init__(self, cfg: dict, start: pd.Timestamp, seed: int = 0):
        rng = np.random.default_rng(seed)
        veh = cfg["vehicles"]
        day = start.normalize()
        self.chargers = {
            f"{c['kind']}{i + 1}": c["power_kw"]
            for c in cfg["station"]["chargers"] for i in range(c["count"])
        }
        self.vehicles = []
        for i in range(veh["count"]):
            arr_h = rng.normal(veh["arrival_hour"]["mean"], veh["arrival_hour"]["std"])
            dep_h = rng.normal(veh["departure_hour"]["mean"], veh["departure_hour"]["std"])
            arrival = day + pd.to_timedelta(arr_h, unit="h")
            departure = day + pd.to_timedelta(24 + dep_h, unit="h")
            self.vehicles.append({
                "id": f"EV{i + 1:02d}", "arrival": arrival, "departure": departure,
                "soc": rng.uniform(veh["arrival_soc"]["min"], veh["arrival_soc"]["max"]),
                "battery_kwh": veh["battery_kwh"], "target_soc": veh["target_soc"],
                "charger": None,
            })
        self.vehicles.sort(key=lambda v: v["arrival"])

    def _connect(self, ts):
        busy = {v["charger"] for v in self.vehicles if v["charger"]}
        for v in self.vehicles:
            if v["charger"] and ts >= v["departure"]:
                busy.discard(v["charger"])
                v["charger"] = "ayrildi"
            elif v["charger"] is None and v["arrival"] <= ts < v["departure"]:
                free = [c for c in self.chargers if c not in busy]
                if free:
                    v["charger"] = free[0]
                    busy.add(free[0])

    def _connected(self):
        return [v for v in self.vehicles if v["charger"] in self.chargers]

    def requests(self, ctx: StepContext) -> list[VehicleRequest]:
        self._connect(ctx.timestamp)
        return [
            VehicleRequest(
                charger_id=v["charger"], vehicle_id=v["id"], soc=v["soc"],
                battery_kwh=v["battery_kwh"], target_soc=v["target_soc"],
                departure=v["departure"], max_charge_kw=self.chargers[v["charger"]],
            )
            for v in self._connected() if v["soc"] < v["target_soc"]
        ]

    def apply(self, ctx: StepContext, ev_kw: dict[str, float]) -> dict[str, float]:
        applied = {}
        for v in self._connected():
            p = ev_kw.get(v["charger"], 0.0)
            room_kw = (v["target_soc"] - v["soc"]) * v["battery_kwh"] / ctx.dt_h
            p = min(p, room_kw, self.chargers[v["charger"]])
            v["soc"] += p * ctx.dt_h / v["battery_kwh"]
            applied[v["charger"]] = p
        return applied


class V2GMockStation(MockStation):
    """V2G'ye uygun araçları olan sahte istasyon (YM-3, Senaryo 6). GEÇİCİ: YM-2'nin gerçek istasyonu gelince değişecek.

    MockStation'a şunları ekler: araçların bir kısmı (`v2g_share`) V2G'ye uygun; bu araçlar hedef SOC'ye ulaşsa bile
    listede kalır ve `max_discharge_kw` bildirir (üniteyle ve `discharge_kw` ile, ayrıca taban SOC'ye kadar olan
    enerjiyle sınırlı). Negatif `ev_kw` aracı deşarj eder; araç bataryasından çekilen enerji = güç·dt / verim.
    Şarj kayıpsızdır (MockStation gibi), böylece V2G'siz karşılaştırma aynı istasyonla yapılabilir (`v2g_share=0`).
    """

    def __init__(self, cfg: dict, start: pd.Timestamp, seed: int = 0, v2g_share: float = 0.4,
                 discharge_kw: float = 11.0, min_soc: float = 0.3, discharge_eff: float = 0.95):
        super().__init__(cfg, start, seed)
        self.discharge_kw, self.min_soc, self.discharge_eff = discharge_kw, min_soc, discharge_eff
        n_v2g = round(v2g_share * len(self.vehicles))
        ids = sorted(v["id"] for v in self.vehicles)
        # her 5 araçtan ikisi: filo boyunca eşit dağılsın, rastgele tohuma bağlı olmasın
        capable = {vid for i, vid in enumerate(ids) if (i * n_v2g) // len(ids) != ((i + 1) * n_v2g) // len(ids)} if ids else set()
        for v in self.vehicles:
            v["v2g"] = v["id"] in capable

    def _max_discharge(self, v: dict, dt_h: float) -> float:
        if not v["v2g"]:
            return 0.0
        usable_kwh = max(0.0, (v["soc"] - self.min_soc) * v["battery_kwh"])
        return min(self.discharge_kw, self.chargers[v["charger"]], usable_kwh * self.discharge_eff / dt_h)

    def requests(self, ctx: StepContext) -> list[VehicleRequest]:
        self._connect(ctx.timestamp)
        out = []
        for v in self._connected():
            dis = self._max_discharge(v, ctx.dt_h)
            if v["soc"] >= v["target_soc"] and dis <= 0:
                continue
            out.append(VehicleRequest(
                charger_id=v["charger"], vehicle_id=v["id"], soc=v["soc"], battery_kwh=v["battery_kwh"],
                target_soc=v["target_soc"], departure=v["departure"], max_charge_kw=self.chargers[v["charger"]],
                max_discharge_kw=dis,
            ))
        return out

    def apply(self, ctx: StepContext, ev_kw: dict[str, float]) -> dict[str, float]:
        applied = {}
        for v in self._connected():
            p = ev_kw.get(v["charger"], 0.0)
            if p >= 0:
                room_kw = max(0.0, (v["target_soc"] - v["soc"]) * v["battery_kwh"] / ctx.dt_h)
                p = min(p, room_kw, self.chargers[v["charger"]])
                v["soc"] += p * ctx.dt_h / v["battery_kwh"]
            else:
                p = -min(-p, self._max_discharge(v, ctx.dt_h))
                v["soc"] += p * ctx.dt_h / self.discharge_eff / v["battery_kwh"]
            applied[v["charger"]] = p
        return applied


class UncontrolledEMS:
    """Senaryo 2: her araç geldiği an tam güçle şarj olur, batarya kullanılmaz."""

    def prepare(self, forecast: pd.DataFrame) -> None:
        pass

    def decide(self, inp: EmsInputs) -> Decision:
        # Tam güç istenir; istasyon hedefe kalan payla (verim dahil) kendisi kırpar. need/dt istemek verim
        # kaybı yüzünden her adım %5 eksik bırakıyordu ve araç üniteyi ~1 saat fazladan tutuyordu (YM-2).
        return Decision(ev_kw={v.charger_id: v.max_charge_kw for v in inp.vehicles})


class SimpleBattery:
    """Güç ve SOC sınırları, şarjda verim kaybı."""

    def __init__(self, cfg: dict):
        b = cfg["bess"]
        self.capacity_kwh, self.power_kw, self.eff = b["capacity_kwh"], b["power_kw"], b["efficiency"]
        self.soc_min, self.soc_max, self.soc = b["soc_min"], b["soc_max"], b["soc_initial"]

    def apply(self, power_kw: float, dt_h: float) -> float:
        p = max(-self.power_kw, min(self.power_kw, power_kw))
        if p > 0:
            p = min(p, (self.soc_max - self.soc) * self.capacity_kwh / (dt_h * self.eff))
            self.soc += p * dt_h * self.eff / self.capacity_kwh
        else:
            p = max(p, -(self.soc - self.soc_min) * self.capacity_kwh / dt_h)
            self.soc += p * dt_h / self.capacity_kwh
        return p
