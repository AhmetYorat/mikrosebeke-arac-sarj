"""Detaylı şarj istasyonu modeli (PRD v2 - EM-1 + YM-2).

Bu modül EM-1 ve YM-2 tarafından geliştirilmektedir.

PRD v2 - İstasyon Tanımı:
İstasyon iki katmanda modellenir:
- Python (YM-2): ChargingStation sınıfı; her ünite için hangi aracın bağlı olduğu, 
  anlık güç, SOC ve ayrılışa kalan süre tutulur. EMS her adımsa ünitelere güç atar; 
  istasyon toplam gücü pandapower'a yük olarak gider.
- Simulink (EM-1): MathWorks örneğindeki iki toplu batarya grubu (G2V/V2G) temel alınır; 
  istasyon AC ve DC şarj grupları olarak ayrı dallar hâlinde, konvertörleriyle modellenir.

Şarj Üniteleri:
- AC üniteler: Yavaş şarj (22 kW) - ev/avm otoparkları için
- DC üniteler: Hızlı şarj (50-150 kW) - otoyol hızlı şarj için

Kontrol Seviyeleri:
1. Ünitelere araç ataması
2. Her ünite için şarj gücü ayarı (SOC + tariff bazlı)
3. Toplam istasyon gücünü sınırlama
"""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class ChargingUnitConfig:
    """Şarj ünitesi yapılandırması."""
    
    unit_id: str
    unit_type: str          # "AC" veya "DC"
    max_power_kw: float     # Maksimum güç (kW)
    
    # AC spesifik
    ac_voltage: float = 220.0   # V
    ac_phases: int = 1          # Tek faz veya üç faz
    
    # DC spesifik
    dc_voltage_min: float = 200.0   # Minimum voltaj (V)
    dc_voltage_max: float = 800.0   # Maximum voltaj (V)
    
    @property
    def is_ac(self) -> bool:
        return self.unit_type.upper() == "AC"
    
    @property
    def is_dc(self) -> bool:
        return self.unit_type.upper() == "DC"


@dataclass
class VehicleOnUnit:
    """Şarj ünitesine bağlı araç durumu."""
    
    vehicle_id: str
    unit_id: str
    arrival_time: float       # Saat (0-24)
    departure_time: float     # Saat (0-24)
    
    # SOC bilgileri
    soc_start: float          # Başlangıç SOC (0-1)
    soc_current: float        # Mevcut SOC (0-1)
    soc_target: float         # Hedef SOC (0-1)
    
    # Enerji gereksinimi
    energy_required_kwh: float  # İstenen enerji (kWh)
    
    # Şarj profili
    max_power_kw: float       # Araç maksimum şarj gücü (kW)
    cc_cv_transition_soc: float = 0.80  # CC-CV geçiş SOC'si
    
    # Mevcut güç ataması
    current_power_kw: float = 0.0


class ChargingStation:
    """Detaylı şarj istasyonu modeli.
    
    Özellikler:
    - AC ve DC şarj üniteleri
    - Her ünite için bağımsız araç takibi
    - SOC bazlı şarj gücünü hesaplama (CC-CV profili)
    - Toplam güç sınırlaması
    - Pandapower entegrasyonu için toplam yük çıktısı
    
    Kullanım:
        # İstasyon oluştur
        config = ChargingUnitConfig(unit_id="AC1", unit_type="AC", max_power_kw=22)
        station = ChargingStation(ac_units=8, dc_units=2, ac_power_kw=22, dc_power_kw=150)
        
        # Araç ekle
        station.add_vehicle(vehicle_id="EV001", unit_id="AC1", arrival_time=18.0, 
                           soc_start=0.2, target_soc=0.95)
        
        # EMS'den güç al
        station.apply_power(unit_id="AC1", power_kw=15.0)
        
        # Toplam gücü al (pandapower'a gönder)
        total_power = station.get_total_load_kw()
    """
    
    def __init__(self, ac_units: int = 8, dc_units: int = 2,
                 ac_power_kw: float = 22.0, dc_power_kw: float = 150.0,
                 max_station_power_kw: Optional[float] = None):
        """Şarj istasyonunu başlat.
        
        Args:
            ac_units: AC şarj üniteleri sayısı
            dc_units: DC şarj üniteleri sayısı  
            ac_power_kw: Her AC ünitesi maksimum gücü (kW)
            dc_power_kw: Her DC ünitesi maksimum gücü (kW)
            max_station_power_kw: İstasyon toplam güç limiti (opsiyonel)
        """
        self.units: dict[str, ChargingUnitConfig] = {}
        self.vehicles_on_units: dict[str, Optional[VehicleOnUnit]] = {}
        self.unit_power_limits: dict[str, float] = {}
        
        # AC üniteleri oluştur
        for i in range(ac_units):
            unit_id = f"AC{i+1}"
            config = ChargingUnitConfig(
                unit_id=unit_id,
                unit_type="AC",
                max_power_kw=ac_power_kw
            )
            self.units[unit_id] = config
            self.vehicles_on_units[unit_id] = None
            self.unit_power_limits[unit_id] = ac_power_kw
        
        # DC üniteleri oluştur
        for i in range(dc_units):
            unit_id = f"DC{i+1}"
            config = ChargingUnitConfig(
                unit_id=unit_id,
                unit_type="DC",
                max_power_kw=dc_power_kw
            )
            self.units[unit_id] = config
            self.vehicles_on_units[unit_id] = None
            self.unit_power_limits[unit_id] = dc_power_kw
        
        # İstasyon toplam güç limiti
        self.max_station_power_kw = max_station_power_kw or (
            ac_units * ac_power_kw + dc_units * dc_power_kw
        )
    
    def add_vehicle(self, vehicle_id: str, unit_id: str, arrival_time: float,
                   soc_start: float = 0.20, target_soc: float = 0.95,
                   max_power_kw: Optional[float] = None) -> bool:
        """Bir aracı üniteye ekle.
        
        Args:
            vehicle_id: Aracın ID'si
            unit_id: Bağlanacak ünitenin ID'si
            arrival_time: Varış saati (0-24 arası)
            soc_start: Başlangıç SOC
            target_soc: Hedef SOC
            max_power_kw: Aracın maksimum şarj gücü (opsiyonel, ünite varsayılanı kullanılır)
            
        Returns:
            Başarılı mı
        """
        if unit_id not in self.units:
            return False
        
        if self.vehicles_on_units.get(unit_id) is not None:
            # Ünite zaten dolu
            return False
        
        unit_max_power = self.unit_power_limits[unit_id]
        
        if max_power_kw is None:
            max_power_kw = unit_max_power
        
        vehicle = VehicleOnUnit(
            vehicle_id=vehicle_id,
            unit_id=unit_id,
            arrival_time=arrival_time,
            departure_time=arrival_time + 4.0,  # Varsayılan 4 saat kalış
            soc_start=soc_start,
            soc_current=soc_start,
            soc_target=target_soc,
            energy_required_kwh=0.0,  # Hesaplanacak
            max_power_kw=min(max_power_kw, unit_max_power),
            cc_cv_transition_soc=0.80
        )
        
        # Enerji gereksinimini hesapla (yaklaşık)
        battery_capacity_kwh = vehicle.energy_required_kwh / max(0.1, target_soc - soc_start)
        vehicle.energy_required_kwh = (target_soc - soc_start) * battery_capacity_kwh
        
        self.vehicles_on_units[unit_id] = vehicle
        return True
    
    def remove_vehicle(self, unit_id: str) -> Optional[VehicleOnUnit]:
        """Üniteden aracı çıkar.
        
        Args:
            unit_id: Çıkarılacak ünitenin ID'si
            
        Returns:
            Çıkarılan araç bilgisi
        """
        vehicle = self.vehicles_on_units.pop(unit_id, None)
        return vehicle
    
    def get_vehicle_on_unit(self, unit_id: str) -> Optional[VehicleOnUnit]:
        """Bir ünitedeki aracı döndür.
        
        Args:
            unit_id: Ünitenin ID'si
            
        Returns:
            Araç bilgisi veya None
        """
        return self.vehicles_on_units.get(unit_id)
    
    def apply_power(self, unit_id: str, power_kw: float) -> bool:
        """Bir üniteye güç atar.
        
        Args:
            unit_id: Ünitenin ID'si
            power_kw: Atanacak güç (kW)
            
        Returns:
            Başarılı mı
        """
        if unit_id not in self.vehicles_on_units:
            return False
        
        vehicle = self.vehicles_on_units[unit_id]
        if vehicle is None:
            return False
        
        # Unit limitini kontrol et
        unit_limit = self.unit_power_limits[unit_id]
        power_kw = min(power_kw, unit_limit)
        
        # vehicle max power ile sınırla
        power_kw = min(power_kw, vehicle.max_power_kw)
        
        # SOC limitlerini kontrol et
        if vehicle.soc_current >= vehicle.soc_target:
            # Hedefe ulaşıldı, şarfı durdur
            power_kw = 0.0
        
        vehicle.current_power_kw = power_kw
        return True
    
    def get_unit_power(self, unit_id: str) -> float:
        """Bir ünitenin mevcut gücünü döndür.
        
        Args:
            unit_id: Ünitenin ID'si
            
        Returns:
            Mevcut güç (kW)
        """
        vehicle = self.vehicles_on_units.get(unit_id)
        if vehicle is None:
            return 0.0
        return vehicle.current_power_kw
    
    def get_total_load_kw(self, current_time: Optional[float] = None) -> float:
        """İstasyonun toplam gücünü döndür.
        
        Args:
            current_time: Mevcut saat (opsiyonel, time-based poweradjustment için)
            
        Returns:
            Toplam yük (kW)
        """
        total = sum(self.get_unit_power(uid) for uid in self.vehicles_on_units)
        
        # İstasyon limitini kontrol et
        return min(total, self.max_station_power_kw)
    
    def get_unit_status(self, current_time: Optional[float] = None) -> dict:
        """Tüm ünitelerin durumunu döndür.
        
        Args:
            current_time: Mevcut saat (opsiyonel, departure time için)
            
        Returns:
            Ünite durumu sözlüğü
        """
        status = {}
        for unit_id, vehicle in self.vehicles_on_units.items():
            if vehicle is not None:
                time_to_dep = 4.0
                if current_time is not None:
                    time_to_dep = max(0, vehicle.departure_time - current_time)
                    
                status[unit_id] = {
                    'occupied': True,
                    'vehicle_id': vehicle.vehicle_id,
                    'soc_current': vehicle.soc_current,
                    'soc_target': vehicle.soc_target,
                    'power_kw': vehicle.current_power_kw,
                    'time_to_departure': time_to_dep
                }
            else:
                status[unit_id] = {
                    'occupied': False,
                    'vehicle_id': None,
                    'soc_current': None,
                    'power_kw': 0.0
                }
        return status
    
    def update_vehicle_soc(self, unit_id: str, time_step_hours: float) -> Optional[float]:
        """Bir ünitenin aracının SOC'sini güncelle.
        
        Args:
            unit_id: Ünitenin ID'si
            time_step_hours: Zaman adımısı (saat)
            
        Returns:
            Güncellenmiş SOC veya None
        """
        vehicle = self.vehicles_on_units.get(unit_id)
        if vehicle is None or vehicle.current_power_kw <= 0:
            return None
        
        # CC-CV şarj profili
        power = vehicle.current_power_kw
        
        if vehicle.soc_current < vehicle.cc_cv_transition_soc:
            # CC (Constant Current) fazı - sabit güç
            pass  # Power zaten ayarlandı
        else:
            # CV (Constant Voltage) fazı - güç azalır
            # Basitleştirilmiş: gücün %50'sine düş
            power = power * 0.5
        
        # SOC güncelle (yaklaşık)
        battery_capacity_kwh = 100.0  # Default battery capacity
        if vehicle.energy_required_kwh > 0:
            soc_diff = max(0.1, vehicle.soc_target - vehicle.soc_start)
            battery_capacity_kwh = vehicle.energy_required_kwh / soc_diff
        
        efficiency = 0.92
        soc_increase = (power * time_step_hours * efficiency) / battery_capacity_kwh
        
        vehicle.soc_current = min(vehicle.soc_target, 
                                  vehicle.soc_current + soc_increase)
        
        # Güç güncelle (CV fazında düşüş varsa)
        if vehicle.soc_current >= vehicle.cc_cv_transition_soc:
            # Yavaş yavaş azalt
            power = power * (1 - 0.1 * (vehicle.soc_current - vehicle.cc_cv_transition_soc) / 0.15)
            vehicle.current_power_kw = max(0, power)
        
        return vehicle.soc_current


def test_charging_station():
    """Şarj istasyonunu test et."""
    print("=" * 60)
    print("DETAYLI ŞARJ İSTASYONU - TEST")
    print("=" * 60)
    
    # İstasyon oluştur (8 AC + 2 DC ünite)
    station = ChargingStation(
        ac_units=4,
        dc_units=2,
        ac_power_kw=22.0,
        dc_power_kw=150.0
    )
    
    print("\nİstasyon Konfigürasyonu:")
    print(f"  AC Üniteleri: {len([u for u in station.units if u.startswith('AC')])} × {22.0} kW")
    print(f"  DC Üniteleri: {len([u for u in station.units if u.startswith('DC')])} × {150.0} kW")
    print(f"  Toplam Güç Limiti: {station.max_station_power_kw:.1f} kW")
    
    # Araç ekle
    print("\nAraç Ekleme:")
    
    test_vehicles = [
        ("EV001", "AC1", 18.0, 0.25, 0.95),
        ("EV002", "AC2", 18.5, 0.40, 0.90),
        ("EV003", "DC1", 19.0, 0.20, 0.80),
    ]
    
    for vid, unit_id, arrival, soc_start, target in test_vehicles:
        success = station.add_vehicle(vid, unit_id, arrival, soc_start, target)
        print(f"  {vid} -> {unit_id}: {'Başarılı' if success else 'Hata'} (SOC: {soc_start}→{target})")
    
    # Güç atama ve toplam hesaplama
    print("\nGüç Atama ve Toplam Yük:")
    
    power_schedule = {
        "AC1": 20.0,
        "AC2": 15.0,
        "DC1": 100.0,
    }
    
    for unit_id, power in power_schedule.items():
        station.apply_power(unit_id, power)
        print(f"  {unit_id}: {power:.1f} kW")
    
    total = station.get_total_load_kw()
    print(f"\n  Toplam Yük: {total:.1f} kW")
    
    # Ünite durumları
    print("\nÜnite Durumları:")
    status = station.get_unit_status()
    for unit_id, info in status.items():
        if info['occupied']:
            print(f"  {unit_id}: {info['vehicle_id']} - SOC={info['soc_current']:.1%}, "
                  f"P={info['power_kw']:.1f} kW")
        else:
            print(f"  {unit_id}: Boş")
    
    # SOC güncelleme
    print("\nSOC Güncelleme (15 dk adım):")
    for unit_id in ["AC1", "AC2", "DC1"]:
        new_soc = station.update_vehicle_soc(unit_id, 0.25)
        if new_soc is not None:
            print(f"  {unit_id}: {new_soc:.1%}")
    
    print("=" * 60)
    print()


if __name__ == "__main__":
    test_charging_station()
