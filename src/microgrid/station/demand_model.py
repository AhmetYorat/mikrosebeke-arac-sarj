"""
Araç Talep Modeli (DemandModel)
Yazılım Üyesi 2 (YM-2) - Hafta 2 Görevi
"""
import random
from typing import List
from .vehicle import ElectricVehicle


# Türkiye ve Avrupa pazarındaki yaygın elektrikli araç teknik özellikleri
VEHICLE_CATALOG = [
    {
        "model_name": "Renault Zoe E-Tech",
        "battery_capacity_kwh": 52.0,
        "max_ac_power_kw": 22.0,
        "max_dc_power_kw": 50.0,
        "v2g_capable": False,
        "weight": 0.25,
    },
    {
        "model_name": "Tesla Model 3 SR+",
        "battery_capacity_kwh": 60.0,
        "max_ac_power_kw": 11.0,
        "max_dc_power_kw": 170.0,
        "v2g_capable": True,
        "weight": 0.30,
    },
    {
        "model_name": "Togg T10X Uzun Menzil",
        "battery_capacity_kwh": 88.5,
        "max_ac_power_kw": 22.0,
        "max_dc_power_kw": 150.0,
        "v2g_capable": False,
        "weight": 0.25,
    },
    {
        "model_name": "Hyundai Ioniq 5",
        "battery_capacity_kwh": 77.4,
        "max_ac_power_kw": 11.0,
        "max_dc_power_kw": 220.0,
        "v2g_capable": True,
        "weight": 0.10,
    },
    {
        "model_name": "Peugeot e-208",
        "battery_capacity_kwh": 50.0,
        "max_ac_power_kw": 11.0,
        "max_dc_power_kw": 100.0,
        "v2g_capable": False,
        "weight": 0.10,
    },
]


class DemandModel:
    """
    Hafta 2 Araç Talep Modeli (Site Otoparkı - Konut / Rezidans Profili):
    Olasılık dağılımlarına göre 24 saatlik sentetik araç akışı üretir.
    
    Site Sakinleri Davranış Dağılımları:
    - Akşam Eve Dönüş Piki (%65): Normal(18.0, 1.6h) - Gece boyu uzun bağlı kalma
    - Gündüz / Evden Çalışan / Misafir (%35): Normal(11.5, 2.5h)
    - Geliş SOC: Uniform(0.18, 0.45)
    - Hedef SOC: Uniform(0.85, 1.00)
    """
    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed
        self.rng = random.Random(random_seed)

    def _sample_spec(self) -> dict:
        weights = [v["weight"] for v in VEHICLE_CATALOG]
        return self.rng.choices(VEHICLE_CATALOG, weights=weights, k=1)[0]

    def generate_fleet(self, total_vehicles: int = 20) -> List[ElectricVehicle]:
        """24 saatlik simülasyon için araç listesi üretir."""
        fleet = []
        for i in range(1, total_vehicles + 1):
            spec = self._sample_spec()
            vid = f"EV-{i:03d}"
            
            # Varış zamanı dağılımı: %65 akşam piki, %35 gündüz varışı
            if self.rng.random() < 0.65:
                arr = self.rng.gauss(18.0, 1.6)
                stay = self.rng.uniform(2.5, 9.0)
            else:
                arr = self.rng.gauss(11.5, 2.5)
                stay = self.rng.uniform(1.5, 5.0)

            arr = max(0.5, min(23.0, arr))
            dep = min(24.0, arr + stay)

            initial_soc = round(self.rng.uniform(0.18, 0.45), 2)
            target_soc = round(self.rng.uniform(0.85, 1.00), 2)

            ev = ElectricVehicle(
                vehicle_id=vid,
                model_name=spec["model_name"],
                battery_capacity_kwh=spec["battery_capacity_kwh"],
                initial_soc=initial_soc,
                target_soc=target_soc,
                arrival_time=round(arr, 2),
                departure_time=round(dep, 2),
                max_ac_power_kw=spec["max_ac_power_kw"],
                max_dc_power_kw=spec["max_dc_power_kw"],
                v2g_capable=spec["v2g_capable"],
            )
            fleet.append(ev)

        fleet.sort(key=lambda x: x.arrival_time)
        return fleet
