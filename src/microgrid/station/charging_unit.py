"""Şarj ünitesi (YM-2): tek bir soket ve ona bağlı araç."""
from __future__ import annotations

from microgrid.station.vehicle import ElectricVehicle


class ChargingUnit:
    """Bir AC veya DC ünite. charger_id sözleşmedeki biçimde: AC1…AC8, DC1, DC2."""

    def __init__(self, charger_id: str, kind: str, power_kw: float):
        self.charger_id = charger_id
        self.kind = kind.upper()
        self.power_kw = float(power_kw)
        self.vehicle: ElectricVehicle | None = None

    @property
    def is_free(self) -> bool:
        return self.vehicle is None

    def connect(self, vehicle: ElectricVehicle, ts) -> None:
        self.vehicle = vehicle
        vehicle.charger_id = self.charger_id
        if not vehicle.ever_connected:
            vehicle.ever_connected = True
            vehicle.connected_at = ts
            vehicle.first_charger = self.charger_id

    def disconnect(self) -> ElectricVehicle:
        v, self.vehicle = self.vehicle, None
        v.charger_id = None
        return v

    def max_charge_kw(self, threshold: float, min_fraction: float) -> float:
        """Bağlı aracın bu üniteden şu an çekebileceği en yüksek güç (boşsa 0)."""
        if self.vehicle is None:
            return 0.0
        return self.vehicle.max_charge_kw(self.kind, self.power_kw, threshold, min_fraction)
