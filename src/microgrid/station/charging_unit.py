"""
Şarj Ünitesi / Soketi (ChargingUnit) Modeli
Yazılım Üyesi 2 (YM-2) - Hafta 2 Sınıf Tasarımı
"""
from enum import Enum
from typing import Optional
from .vehicle import ElectricVehicle


class UnitStatus(str, Enum):
    AVAILABLE = "AVAILABLE"              # Boşta, araç yok
    OCCUPIED_CHARGING = "CHARGING"       # Araç bağlı ve şarj oluyor
    OCCUPIED_IDLE = "IDLE"               # Araç bağlı ama şarj olmuyor (tam dolu veya EMS gücü kesti)
    OCCUPIED_DISCHARGING = "DISCHARGING" # V2G modunda araçtan şebekeye deşarj


class ChargingUnit:
    """
    Şarj İstasyonundaki Tek Bir Soketi / Üniteyi Temsil Eder (Hafta 2 Sınıf Tasarımı).
    
    Özellikler:
    - unit_id: Soket kimliği ('AC-01', ..., 'DC-01', ...)
    - unit_type: 'AC' (Tip 2) veya 'DC' (CCS2)
    - max_power_kw: Ünitenin verebileceği nominal tepe güç (22 kW veya 50 kW)
    - min_power_kw: Şarj başlatabilmek için gereken taban güç (AC için 1.4 kW)
    - connected_vehicle: Sokete takılı olan ElectricVehicle nesnesi
    - current_power_kw: Anlık uygulanan güç (kW)
    """
    def __init__(
        self,
        unit_id: str,
        unit_type: str,
        max_power_kw: float,
        min_power_kw: float = 0.0,
    ):
        self.unit_id = unit_id
        self.unit_type = unit_type.upper()
        self.max_power_kw = float(max_power_kw)
        self.min_power_kw = float(min_power_kw)
        
        self.connected_vehicle: Optional[ElectricVehicle] = None
        self.current_power_kw: float = 0.0
        self.total_energy_delivered_kwh: float = 0.0
        self.status: UnitStatus = UnitStatus.AVAILABLE

    @property
    def is_occupied(self) -> bool:
        """Ünitede araç takılı mı?"""
        return self.connected_vehicle is not None

    def connect_vehicle(self, vehicle: ElectricVehicle) -> bool:
        """Aracı bu üniteye bağlar."""
        if self.is_occupied:
            return False
        
        self.connected_vehicle = vehicle
        vehicle.is_connected = True
        vehicle.connected_unit_id = self.unit_id
        self.status = UnitStatus.OCCUPIED_IDLE
        return True

    def disconnect_vehicle(self) -> Optional[ElectricVehicle]:
        """Araç üniteden ayrılır."""
        if not self.is_occupied:
            return None
        
        vehicle = self.connected_vehicle
        vehicle.is_connected = False
        vehicle.connected_unit_id = None
        
        self.connected_vehicle = None
        self.current_power_kw = 0.0
        self.status = UnitStatus.AVAILABLE
        return vehicle

    def get_max_deliverable_power(self) -> float:
        """
        Ünitenin ve bağlı aracın (CC-CV eğrisi dahil) o an güvenle çekebileceği
        maksimum gücü döner (kW).
        """
        if not self.is_occupied or self.connected_vehicle is None:
            return 0.0
        
        if self.connected_vehicle.is_fully_charged():
            return 0.0

        return self.connected_vehicle.get_max_charging_power(
            unit_type=self.unit_type,
            unit_max_power_kw=self.max_power_kw
        )

    def set_power(self, power_kw: float) -> float:
        """
        EMS (Enerji Yönetim Sistemi) tarafından bu üniteye atanan gücü uygular.
        Dönüş: Fiilen uygulanan güç (kW).
        """
        if not self.is_occupied or self.connected_vehicle is None:
            self.current_power_kw = 0.0
            self.status = UnitStatus.AVAILABLE
            return 0.0

        if power_kw > 0.0:
            allowed_max = self.get_max_deliverable_power()
            actual_power = min(power_kw, allowed_max)
            
            if actual_power < self.min_power_kw:
                actual_power = 0.0

            self.current_power_kw = actual_power
            self.status = UnitStatus.OCCUPIED_CHARGING if actual_power > 0.0 else UnitStatus.OCCUPIED_IDLE
            return actual_power

        elif power_kw < 0.0:
            # V2G Deşarjı
            if not self.connected_vehicle.v2g_capable:
                self.current_power_kw = 0.0
                self.status = UnitStatus.OCCUPIED_IDLE
                return 0.0
            
            actual_discharge = max(power_kw, -self.max_power_kw)
            self.current_power_kw = actual_discharge
            self.status = UnitStatus.OCCUPIED_DISCHARGING
            return actual_discharge

        else:
            self.current_power_kw = 0.0
            self.status = UnitStatus.OCCUPIED_IDLE
            return 0.0

    def step(self, dt_hours: float) -> float:
        """Simülasyon zaman adımını ilerletir ve araç bataryasını günceller."""
        if not self.is_occupied or self.connected_vehicle is None or self.current_power_kw == 0.0:
            return 0.0

        if self.current_power_kw > 0.0:
            net_energy = self.connected_vehicle.charge(self.current_power_kw, dt_hours)
            self.total_energy_delivered_kwh += (self.current_power_kw * dt_hours)
            if self.connected_vehicle.is_fully_charged():
                self.current_power_kw = 0.0
                self.status = UnitStatus.OCCUPIED_IDLE
            return net_energy
        else:
            discharged = self.connected_vehicle.discharge(abs(self.current_power_kw), dt_hours)
            return -discharged

    def to_dict(self) -> dict:
        """Soket durumu sözlüğü."""
        return {
            "unit_id": self.unit_id,
            "unit_type": self.unit_type,
            "max_power_kw": self.max_power_kw,
            "current_power_kw": round(self.current_power_kw, 2),
            "status": self.status.value,
            "vehicle": self.connected_vehicle.to_dict() if self.connected_vehicle else None,
        }
