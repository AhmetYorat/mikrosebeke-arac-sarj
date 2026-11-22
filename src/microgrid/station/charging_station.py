"""Şarj istasyonu (YM-2). Sözleşme: docs/arayuz-sozlesmesi.md, "YM-2: Şarj istasyonu".

Döngü her adımda önce requests(ctx), sonra apply(ctx, ev_kw) çağırır:
  requests: ayrılanları çıkarır, gelenleri sıraya ekler, sıra varsa dolu aracı üniteden alır (nöbetleşe), boş ünitelere bağlar (önce AC, AC kalmadıysa DC),
            bağlı araçların sınırlarını VehicleRequest olarak verir. CC-CV eğrisi max_charge_kw içindedir.
  apply:    EMS'in istediği güçleri ünite ve araç sınırlarına göre kırpar, SOC'leri günceller,
            gerçekte uygulanan gücü döndürür.
Güçler şebeke tarafıdır; bataryaya giren enerji güç × süre × station.charge_efficiency.
"""
from __future__ import annotations

import pandas as pd

from microgrid.interfaces import StepContext, VehicleRequest
from microgrid.station.charging_unit import ChargingUnit
from microgrid.station.demand_model import DemandModel
from microgrid.station.vehicle import ElectricVehicle


class ChargingStation:
    def __init__(self, cfg: dict, start: pd.Timestamp, seed: int = 0):
        st = cfg["station"]
        self.eff = st["charge_efficiency"]
        self.cv_threshold = st["cv_threshold_soc"]
        self.cv_min_fraction = st["cv_min_fraction"]
        self.rotate_when_full = st["rotate_when_full"]
        self.units: dict[str, ChargingUnit] = {}
        for c in st["chargers"]:
            for i in range(c["count"]):
                cid = f"{c['kind']}{i + 1}"
                self.units[cid] = ChargingUnit(cid, c["kind"], c["power_kw"])
        self.vehicles: list[ElectricVehicle] = DemandModel(cfg, seed).generate_fleet(start)
        self.queue: list[ElectricVehicle] = []   # ünite bekleyenler, geliş sırasıyla (FIFO)
        self._arrived: set[str] = set()

    # --- iç adımlar -------------------------------------------------------------------------------------------
    def _connected(self) -> list[ChargingUnit]:
        return [u for u in self.units.values() if u.vehicle is not None]

    def _handle_departures(self, ts: pd.Timestamp) -> None:
        for u in self._connected():
            if u.vehicle.departure <= ts:
                u.disconnect()
        self.queue = [v for v in self.queue if v.departure > ts]

    def _rotate(self) -> None:
        """Nöbetleşe şarj: sırada bekleyen varsa hedefe ulaşmış araç üniteyi bırakır (otoparkta kalır, sıraya dönmez)."""
        if not (self.rotate_when_full and self.queue):
            return
        for u in self._connected():
            if u.vehicle.reached_target:
                u.disconnect()

    def _handle_arrivals(self, ts: pd.Timestamp) -> None:
        for v in self.vehicles:
            if v.vehicle_id not in self._arrived and v.arrival <= ts:
                self._arrived.add(v.vehicle_id)
                if v.departure > ts:
                    self.queue.append(v)

    def _assign(self, ts: pd.Timestamp) -> None:
        free = [u for u in self.units.values() if u.is_free]
        free.sort(key=lambda u: u.kind != "AC")   # önce AC; DC yalnızca AC kalmadıysa
        while self.queue and free:
            free.pop(0).connect(self.queue.pop(0), ts)

    # --- sözleşme --------------------------------------------------------------------------------------------
    def requests(self, ctx: StepContext) -> list[VehicleRequest]:
        ts = ctx.timestamp
        self._handle_departures(ts)
        self._handle_arrivals(ts)
        self._rotate()
        self._assign(ts)
        out = []
        for u in self._connected():
            v = u.vehicle
            if v.reached_target:
                continue
            out.append(VehicleRequest(
                charger_id=u.charger_id, vehicle_id=v.vehicle_id, soc=v.soc, battery_kwh=v.battery_kwh,
                target_soc=v.target_soc, departure=v.departure,
                max_charge_kw=u.max_charge_kw(self.cv_threshold, self.cv_min_fraction),
            ))
        return out

    def apply(self, ctx: StepContext, ev_kw: dict[str, float]) -> dict[str, float]:
        """Bağlı her ünite için uygulanan güç. Boş ya da bilinmeyen ünite anahtarları yok sayılır."""
        applied = {}
        for u in self._connected():
            v = u.vehicle
            p = ev_kw.get(u.charger_id, 0.0)
            if p > 0:
                room_kw = v.energy_needed_kwh / (ctx.dt_h * self.eff)
                p = min(p, u.max_charge_kw(self.cv_threshold, self.cv_min_fraction), room_kw)
                v.charge(p, ctx.dt_h, self.eff)
            else:
                p = 0.0
            applied[u.charger_id] = p
        return applied

    # --- çıktılar ---------------------------------------------------------------------------------------------
    def sessions(self) -> pd.DataFrame:
        """Araç başına bir satır: kim geldi, ne kadar bekledi, ne kadar enerji aldı, hedefe ulaştı mı.

        Kullanıcı memnuniyeti KPI'ı (strategies.satisfaction) bu tablodan hesaplanır. energy_kwh şebeke tarafıdır
        (şarj − V2G). Hiç bağlanamayan aracın first_charger'ı None, bekleme süresi tüm kalış süresidir.
        """
        rows = []
        for v in self.vehicles:
            waited_until = v.connected_at if v.ever_connected else v.departure
            rows.append({
                "vehicle_id": v.vehicle_id, "model": v.model_name, "battery_kwh": v.battery_kwh,
                "arrival": v.arrival, "departure": v.departure,
                "first_charger": v.first_charger, "connected_at": v.connected_at,
                "soc_arrival": v.soc_arrival, "soc_final": v.soc, "target_soc": v.target_soc,
                "energy_kwh": v.energy_in_kwh - v.energy_out_kwh, "reached_target": v.reached_target,
                "waited_h": (waited_until - v.arrival).total_seconds() / 3600,
            })
        cols = ["vehicle_id", "model", "battery_kwh", "arrival", "departure", "first_charger", "connected_at",
                "soc_arrival", "soc_final", "target_soc", "energy_kwh", "reached_target", "waited_h"]
        return pd.DataFrame(rows, columns=cols)
