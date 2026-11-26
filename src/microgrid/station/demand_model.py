"""Araç talep modeli (YM-2): config'teki dağılımlardan bir günlük araç filosu üretir.

Site otoparkı: araçlar akşam gelir, ertesi sabah ayrılır (docs/kapsam.md). Geliş/ayrılış saatleri ve SOC'ler
`vehicles:` altındaki dağılımlardan, araç modeli (batarya, OBC sınırı, V2G) `vehicles.fleet` kataloğundan gelir.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from microgrid.station.vehicle import ElectricVehicle


def _catalog(veh: dict) -> list[dict]:
    """Katalog yoksa tek tip araç: battery_kwh, AC 22 / DC 50 kW, V2G yok."""
    return veh.get("fleet") or [{
        "model": "Standart", "battery_kwh": veh["battery_kwh"], "max_ac_kw": 22, "max_dc_kw": 50,
        "v2g": False, "share": 1.0,
    }]


class DemandModel:
    def __init__(self, cfg: dict, seed: int = 0):
        self.cfg = cfg
        self.rng = np.random.default_rng(seed)

    def generate_fleet(self, start: pd.Timestamp) -> list[ElectricVehicle]:
        """Simülasyon başlangıcına (öğlen) göre araçlar, gelişe göre sıralı.

        Kırpma kuralları: geliş [start, start + 12 sa) içinde; ayrılış en erken gelişten 1 saat sonra,
        en geç simülasyon bitişinde. Böylece hiçbir araç negatif süre kalmaz ya da pencerenin dışına taşmaz.
        """
        veh = self.cfg["vehicles"]
        catalog = _catalog(veh)
        shares = np.array([m["share"] for m in catalog], dtype=float)
        shares /= shares.sum()
        day = start.normalize()
        end = start + pd.Timedelta(hours=self.cfg["simulation"]["horizon_hours"])
        h = lambda x: pd.to_timedelta(x, unit="h")

        fleet = []
        for _ in range(veh["count"]):
            spec = catalog[self.rng.choice(len(catalog), p=shares)]
            arrival = day + h(self.rng.normal(veh["arrival_hour"]["mean"], veh["arrival_hour"]["std"]))
            arrival = min(max(arrival, start), start + h(12) - pd.Timedelta(minutes=1))
            departure = day + h(24 + self.rng.normal(veh["departure_hour"]["mean"], veh["departure_hour"]["std"]))
            departure = min(max(departure, arrival + h(1)), end)
            soc = float(self.rng.uniform(veh["arrival_soc"]["min"], veh["arrival_soc"]["max"]))
            fleet.append(ElectricVehicle(
                vehicle_id="", model_name=spec["model"], battery_kwh=float(spec["battery_kwh"]),
                soc_arrival=soc, target_soc=float(veh["target_soc"]), arrival=arrival, departure=departure,
                max_ac_kw=float(spec["max_ac_kw"]), max_dc_kw=float(spec["max_dc_kw"]), v2g_capable=bool(spec["v2g"]),
            ))
        fleet.sort(key=lambda v: v.arrival)
        for i, v in enumerate(fleet):
            v.vehicle_id = f"EV{i + 1:02d}"
        return fleet
