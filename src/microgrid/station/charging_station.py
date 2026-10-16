"""
Şarj İstasyonu (ChargingStation) Modeli
Yazılım Üyesi 2 (YM-2) - Hafta 2 Sınıf Tasarımı ve Arayüz Fonksiyonları
"""
from typing import Dict, List, Optional
from .vehicle import ElectricVehicle
from .charging_unit import ChargingUnit


class ChargingStation:
    """
    EV Şarj İstasyonu Yönetim Sınıfı (Hafta 2 Sınıf Tasarımı).
    
    Tüm şarj soketlerini barındırır, EMS (YM-3) ve pandapower (YM-4)
    ile veri arayüzü fonksiyonlarını sağlar.
    """
    def __init__(
        self,
        station_id: str = "Station-01",
        name: str = "Merkezi Mikro-Şebeke EV Şarj Parkı",
        transformer_limit_kw: float = 180.0,
        num_ac_units: int = 8,
        ac_unit_power_kw: float = 22.0,
        num_dc_units: int = 2,
        dc_unit_power_kw: float = 50.0,
    ):
        self.station_id = station_id
        self.name = name
        self.transformer_limit_kw = float(transformer_limit_kw)
        
        # Soket koleksiyonu
        self.units: Dict[str, ChargingUnit] = {}
        
        # 8 adet AC 22 kW Tip-2 Soket
        for i in range(1, num_ac_units + 1):
            uid = f"AC-{i:02d}"
            self.units[uid] = ChargingUnit(
                unit_id=uid,
                unit_type="AC",
                max_power_kw=ac_unit_power_kw,
                min_power_kw=1.4
            )
            
        # 2 adet DC 50 kW CCS2 Soket
        for i in range(1, num_dc_units + 1):
            uid = f"DC-{i:02d}"
            self.units[uid] = ChargingUnit(
                unit_id=uid,
                unit_type="DC",
                max_power_kw=dc_unit_power_kw,
                min_power_kw=5.0
            )

        self.total_energy_delivered_kwh: float = 0.0
        self.completed_sessions_count: int = 0
        self.overload_history: List[dict] = []

    @property
    def total_capacity_kw(self) -> float:
        """Tüm soketlerin teorik toplam kurulu gücü (kW)."""
        return sum(unit.max_power_kw for unit in self.units.values())

    @property
    def active_connected_vehicles_count(self) -> int:
        """Anlık bağlı araç sayısı."""
        return sum(1 for unit in self.units.values() if unit.is_occupied)

    def get_unit(self, unit_id: str) -> Optional[ChargingUnit]:
        """Soket kimliğine göre üniteyi döner."""
        return self.units.get(unit_id)

    def get_available_units(self, unit_type: Optional[str] = None) -> List[ChargingUnit]:
        """Boş soketleri listeler."""
        available = [u for u in self.units.values() if not u.is_occupied]
        if unit_type:
            unit_type = unit_type.upper()
            available = [u for u in available if u.unit_type == unit_type]
        return available

    def plug_in_vehicle(self, vehicle: ElectricVehicle, preferred_unit_type: Optional[str] = None) -> Optional[str]:
        """Yeni gelen aracı boş bir sokete bağlar."""
        free_units = self.get_available_units(preferred_unit_type)
        if not free_units and preferred_unit_type:
            free_units = self.get_available_units(None)

        if not free_units:
            return None  # İstasyon dolu

        chosen_unit = free_units[0]
        success = chosen_unit.connect_vehicle(vehicle)
        return chosen_unit.unit_id if success else None

    def unplug_vehicle(self, unit_id: str) -> Optional[ElectricVehicle]:
        """Soketteki aracı ayırır."""
        unit = self.get_unit(unit_id)
        if not unit:
            return None
        veh = unit.disconnect_vehicle()
        if veh:
            self.completed_sessions_count += 1
        return veh

    def auto_handle_departures(self, current_time_hours: float) -> List[ElectricVehicle]:
        """Ayrılış saati gelen araçları otomatik olarak üniteden çıkarır."""
        departed = []
        for unit in self.units.values():
            if unit.is_occupied and unit.connected_vehicle:
                if current_time_hours >= unit.connected_vehicle.departure_time:
                    veh = unit.disconnect_vehicle()
                    if veh:
                        self.completed_sessions_count += 1
                        departed.append(veh)
        return departed

    # -------------------------------------------------------------------------
    # MODÜL ARAYÜZ FONKSİYONLARI (YM-3, YM-4 ve EM-1 için sözleşme metotları)
    # -------------------------------------------------------------------------

    def bagli_araclar(self, current_time_hours: float) -> List[dict]:
        """
        YM-2 -> YM-3 Arayüzü:
        EMS optimizasyonu için bağlı tüm araçların anlık taleplerini döner.
        """
        demands = []
        for unit in self.units.values():
            if unit.is_occupied and unit.connected_vehicle:
                v = unit.connected_vehicle
                rem_time = max(0.0, v.departure_time - current_time_hours)
                demands.append({
                    "unit_id": unit.unit_id,
                    "unit_type": unit.unit_type,
                    "unit_max_power_kw": unit.max_power_kw,
                    "vehicle_id": v.vehicle_id,
                    "model_name": v.model_name,
                    "battery_capacity_kwh": v.battery_capacity_kwh,
                    "current_soc": v.current_soc,
                    "target_soc": v.target_soc,
                    "energy_needed_kwh": v.energy_needed_kwh,
                    "max_deliverable_power_kw": unit.get_max_deliverable_power(),
                    "arrival_time": v.arrival_time,
                    "departure_time": v.departure_time,
                    "remaining_time_hours": rem_time,
                    "v2g_capable": v.v2g_capable,
                })
        return demands

    def apply_power_allocations(self, allocations: Dict[str, float]) -> None:
        """
        YM-3 -> YM-2 Arayüzü:
        EMS'ten gelen güç atama komutlarını soketlere iletir.
        """
        for uid, p in allocations.items():
            unit = self.get_unit(uid)
            if unit:
                unit.set_power(p)

    def get_total_power_kw(self) -> float:
        """
        YM-2 -> YM-4 Arayüzü:
        İstasyonun mikro-şebekeden çektiği toplam gücü döner (kW).
        pandapower yük akışı bu değeri çeker.
        """
        return sum(unit.current_power_kw for unit in self.units.values())

    def is_transformer_overloaded(self) -> bool:
        """İstasyon gücü 180 kW trafo sınırını aşıyor mu?"""
        return self.get_total_power_kw() > self.transformer_limit_kw

    def step(self, dt_hours: float, current_time_hours: float) -> dict:
        """Simülasyon zaman adımını ilerletir."""
        departed = self.auto_handle_departures(current_time_hours)
        
        step_energy = 0.0
        for unit in self.units.values():
            step_energy += unit.step(dt_hours)
            
        self.total_energy_delivered_kwh += max(0.0, step_energy)
        total_p = self.get_total_power_kw()
        is_overload = total_p > self.transformer_limit_kw

        return {
            "time_hours": current_time_hours,
            "total_power_kw": round(total_p, 2),
            "step_energy_kwh": round(step_energy, 3),
            "is_overloaded": is_overload,
            "active_vehicles": self.active_connected_vehicles_count,
            "departed_count": len(departed)
        }

    def get_dashboard_state(self) -> dict:
        """YM-4 Streamlit Dashboard için anlık görünüm sözlüğü."""
        return {
            "station_id": self.station_id,
            "station_name": self.name,
            "transformer_limit_kw": self.transformer_limit_kw,
            "total_capacity_kw": self.total_capacity_kw,
            "current_total_power_kw": round(self.get_total_power_kw(), 2),
            "is_overloaded": self.is_transformer_overloaded(),
            "occupied_units": self.active_connected_vehicles_count,
            "total_units": len(self.units),
            "units": [u.to_dict() for u in self.units.values()]
        }
