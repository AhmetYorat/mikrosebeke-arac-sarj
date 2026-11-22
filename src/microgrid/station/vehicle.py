"""
Elektrikli Araç (ElectricVehicle) Modeli
Yazılım Üyesi 2 (YM-2) - Hafta 2 Sınıf Tasarımı
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ElectricVehicle:
    """
    Elektrikli Araç Veri Modeli ve Durum Takibi (Hafta 2 Sınıf Tasarımı).
    
    Özellikler:
    - vehicle_id: Benzersiz araç kimliği (ör. 'EV-001')
    - model_name: Araç modeli (ör. 'Togg T10X', 'Tesla Model 3', 'Renault Zoe')
    - battery_capacity_kwh: Batarya anma kapasitesi (kWh)
    - initial_soc: İstasyona varış anındaki şarj seviyesi (0.0 - 1.0)
    - current_soc: Anlık şarj seviyesi (0.0 - 1.0)
    - target_soc: Araç sahibinin ayrılırken hedeflediği şarj seviyesi (0.85 - 1.00)
    - arrival_time: İstasyona varış saati (günün saati, örn: 17.5 = 17:30)
    - departure_time: Tahmini ayrılış saati (günün saati, örn: 21.5 = 21:30)
    - max_ac_power_kw: Dahili yerleşik şarj cihazı (OBC) AC güç limiti (kW, örn: 11 veya 22)
    - max_dc_power_kw: DC hızlı şarj güç limiti (kW, örn: 50 - 150)
    - v2g_capable: Şebekeye geri enerji verme (V2G) yeteneği var mı?
    """
    vehicle_id: str
    model_name: str
    battery_capacity_kwh: float
    initial_soc: float
    current_soc: float = field(init=False)
    target_soc: float = 0.90
    arrival_time: float = 0.0
    departure_time: float = 0.0
    max_ac_power_kw: float = 22.0
    max_dc_power_kw: float = 100.0
    v2g_capable: bool = False
    
    # Simülasyon durum değişkenleri
    is_connected: bool = False
    connected_unit_id: Optional[str] = None
    total_energy_charged_kwh: float = 0.0
    total_energy_discharged_kwh: float = 0.0

    def __post_init__(self):
        self.initial_soc = max(0.05, min(1.0, float(self.initial_soc)))
        self.current_soc = self.initial_soc
        self.target_soc = max(self.initial_soc, min(1.0, float(self.target_soc)))

    @property
    def remaining_parking_duration_hours(self) -> float:
        """Kalan otoparkta kalış süresi (saat)."""
        return max(0.0, self.departure_time - self.arrival_time)

    @property
    def energy_needed_kwh(self) -> float:
        """Hedef SOC seviyesine ulaşmak için gereken net batarya enerjisi (kWh)."""
        soc_diff = max(0.0, self.target_soc - self.current_soc)
        return soc_diff * self.battery_capacity_kwh

    def is_fully_charged(self) -> bool:
        """Araç kullanıcının hedeflediği şarj seviyesine ulaştı mı?"""
        return self.current_soc >= self.target_soc

    def get_max_charging_power(self, unit_type: str, unit_max_power_kw: float) -> float:
        """
        Donanım kısıtları ve CC-CV (Sabit Akım - Sabit Gerilim) şarj eğrisine göre
        aracın bu üniteden anlık çekebileceği tavan gücü hesaplar.
        
        Darboğaz kontrolü:
        - AC şarjda: min(aracın dahili OBC gücü, soket gücü)
        - DC şarjda: min(aracın DC limiti, soket gücü)
        
        CC-CV Kuralı:
        - SOC < %80  -> Nominal tam güç (Sabit Akım)
        - SOC >= %80 -> Azalan güç (Sabit Gerilim)
        """
        if self.is_fully_charged():
            return 0.0

        # Donanımsal sınır
        if unit_type.upper() == "AC":
            base_power = min(self.max_ac_power_kw, unit_max_power_kw)
        else: # DC
            base_power = min(self.max_dc_power_kw, unit_max_power_kw)

        # CC-CV Karakteristiği
        if self.current_soc < 0.80:
            return base_power
        else:
            # SOC %80 -> %100 aralığında gücü %100'den %15'e doğru düşür
            decay = max(0.15, (1.0 - self.current_soc) / 0.20)
            return base_power * decay

    def charge(self, power_kw: float, dt_hours: float, efficiency: float = 0.95) -> float:
        """Belirtilen güçle aracı dt_hours kadar şarj eder ve SOC'yi günceller."""
        if power_kw <= 0.0 or self.current_soc >= 1.0:
            return 0.0

        energy_added = power_kw * dt_hours * efficiency
        max_possible_energy = (1.0 - self.current_soc) * self.battery_capacity_kwh
        actual_energy = min(energy_added, max_possible_energy)
        
        self.current_soc += actual_energy / self.battery_capacity_kwh
        self.total_energy_charged_kwh += actual_energy
        return actual_energy

    def discharge(self, power_kw: float, dt_hours: float, efficiency: float = 0.95) -> float:
        """V2G Modu: Araçtan şebekeye enerji aktarımı."""
        if not self.v2g_capable or power_kw <= 0.0:
            return 0.0

        min_soc_limit = 0.20  # V2G alt sınırı (kullanıcıyı koruma)
        available_soc = max(0.0, self.current_soc - min_soc_limit)
        max_discharge_energy = available_soc * self.battery_capacity_kwh
        
        needed_from_battery = (power_kw * dt_hours) / efficiency
        actual_battery_energy = min(needed_from_battery, max_discharge_energy)
        
        self.current_soc -= actual_battery_energy / self.battery_capacity_kwh
        net_to_grid = actual_battery_energy * efficiency
        self.total_energy_discharged_kwh += net_to_grid
        return net_to_grid

    def to_dict(self) -> dict:
        """Durum özeti sözlüğü."""
        return {
            "vehicle_id": self.vehicle_id,
            "model_name": self.model_name,
            "battery_capacity_kwh": self.battery_capacity_kwh,
            "initial_soc": round(self.initial_soc, 3),
            "current_soc": round(self.current_soc, 3),
            "target_soc": round(self.target_soc, 3),
            "arrival_time": self.arrival_time,
            "departure_time": self.departure_time,
            "energy_needed_kwh": round(self.energy_needed_kwh, 2),
            "is_connected": self.is_connected,
            "connected_unit_id": self.connected_unit_id,
        }
