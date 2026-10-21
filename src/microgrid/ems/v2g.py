"""Vehicle-to-Grid (V2G) stratejileri ve optimizasyonu (PRD v2 - Senaryo 6).

Bu modül EM-3 tarafından geliştirilmektedir.
V2G: Araçların yüksek SOC değerlerinde şebekeye enerji vermesi (pik saatlerde)

PRD v2 Senaryo 6 - V2G:
- Akşam saatlerinde (17:00-20:00) yüksek SOC'li araçlar şebekeye enerji verir
- Frekans desteğini sağlar
- Tepe yükü azaltır ve maliyeti düşürür

Stratejiler:
1. Threshold-based: SOC > %X olduğunda deşarj yap
2. Price-based: Pahalı saatlerde maksimum deşarj
3. Hybrid: SOC + fiyat kombinasyonu
"""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass 
class V2GOption:
    """V2G operasyon seçeneği."""
    
    # SOC eşikleri
    v2g_soc_threshold: float = 0.85   # Bu eşikten yüksek SOC'da deşarj başlar
    v2g_min_soc: float = 0.40         # Minimum SOC (araç ayrılırken bu seviye)
    
    # Güç sınırları
    max_discharge_power_kw: float = 50.0  # Maksimum deşarj gücü (kW)
    max_charge_power_kw: float = 50.0     # Maksimum şarj gücü (kW)
    
    # Verimlilik
    v2g_charge_efficiency: float = 0.95   # Şarj verimi
    v2g_discharge_efficiency: float = 0.92  # Deşarj verimi
    
    # Zaman sınırları
    min_stay_hours: float = 2.0         # Minimum kalış süresi (saat)
    departure_buffer_hours: float = 0.5  # Ayrılış öncesi beklememe süresi


@dataclass
class VehicleState:
    """Tek bir araç için durum bilgisi."""
    
    vehicle_id: str
    arrival_time: float      # Saat (0-24, ondalıklı)
    departure_time: float    # Saat (0-24, ondalıklı)
    soc_start: float         # Varıştaki SOC (0-1 arası)
    energy_required_kwh: float  # İstenen şarj enerjisi (kWh)
    soc_target: float        # Hedef SOC
    max_power_kw: float      # Araç maksimum şarj/deşarj gücü


class V2GStrategy:
    """Vehicle-to-Grid stratejisi.
    
    V2G mantığı:
    1. Araçların SOC ve ayrılış saatlerini takip et
    2. Pahalı saatlerde (puant) veya grid yüksekteyken deşarj öner
    3. Araçların ayrılmadan önce istenen SOC seviyesine ulaşmasını sağla
    4. Grid desteği için hızlı reaksiyon
    """
    
    def __init__(self, option: Optional[V2GOption] = None):
        """V2G stratejisini başlat."""
        self.option = option or V2GOption()
        self.connected_vehicles: dict[str, VehicleState] = {}
    
    def add_vehicle(self, vehicle: VehicleState) -> None:
        """Araç ekle - V2G izlemeye başla."""
        self.connected_vehicles[vehicle.vehicle_id] = vehicle
    
    def remove_vehicle(self, vehicle_id: str) -> Optional[VehicleState]:
        """Araç çıkar - V2G izleme durdur."""
        return self.connected_vehicles.pop(vehicle_id, None)
    
    def get_vehicle_discharge_power(self, vehicle_id: str, current_time: float,
                                     grid_price: float, grid_demand_high: bool) -> float:
        """Belirli bir araç için deşarj gücünü belirle.
        
        Args:
            vehicle_id: Aracın ID'si
            current_time: Mevcut saat (0-24 arası)
            grid_price: Grid energy price (TL/kWh)
            grid_demand_high: Grid talebi yüksek mi
            
        Returns:
            Deşarj gücü (kW, 0 = deşarj yok)
        """
        if vehicle_id not in self.connected_vehicles:
            return 0.0
        
        vehicle = self.connected_vehicles[vehicle_id]
        
        # Ayrılma zamanını kontrol et
        hours_until_departure = vehicle.departure_time - current_time
        
        # Ayrılma yaklaşıyorsa (bir saat içinde), hedef SOC'ye ulaşmak için şarj yap
        if hours_until_departure <= 1.0:
            return 0.0  # Deşarj yapma, şarza odaklan
        
        # SOC kontrolü - alt eşikteyse deşarj yapma
        if vehicle.soc_start < self.option.v2g_min_soc:
            return 0.0
        
        # Yüksek SOC ve pahalı fiyat veya yüksek grid talebi -> deşarj
        if (vehicle.soc_start >= self.option.v2g_soc_threshold and 
            (grid_price > 5.0 or grid_demand_high)):
            
            # Kalan süreye göre deşarj gücünü ayarla
            # Daha kısa kalış = daha yüksek güç, daha az energy tüketimi
            power_factor = min(1.0, hours_until_departure / 2.0)
            
            # Vehicle max power ile sınırla
            return min(
                vehicle.max_power_kw,
                self.option.max_discharge_power_kw * power_factor
            )
        
        return 0.0
    
    def get_total_discharge_power(self, current_time: float,
                                   grid_price: float,
                                   grid_demand_high: bool) -> float:
        """Tüm bağlı araçların toplam deşarj gücünü hesapla.
        
        Args:
            current_time: Mevcut saat
            grid_price: Grid energy price
            grid_demand_high: Grid talebi yüksek mi
            
        Returns:
            Toplam deşarj gücü (kW)
        """
        total_power = 0.0
        for vehicle_id in self.connected_vehicles:
            power = self.get_vehicle_discharge_power(
                vehicle_id, current_time, grid_price, grid_demand_high
            )
            total_power += power
        
        return total_power
    
    def update_vehicle_soc(self, vehicle_id: str, charge_power_kw: float,
                          discharge_power_kw: float, time_step_hours: float) -> None:
        """Araç SOC'sini güncelle (simülasyon için)."""
        if vehicle_id not in self.connected_vehicles:
            return
        
        vehicle = self.connected_vehicles[vehicle_id]
        
        # Net güç (şarj pozitif, deşarj negatif)
        net_power = charge_power_kw - discharge_power_kw
        
        # SOC güncelle
        energy_change = net_power * time_step_hours
        
        # Verimlilik uygula
        if energy_change > 0:
            # Şarj
            vehicle.soc_start += (energy_change / 
                                  (vehicle.max_power_kw * 0.8)) * \
                                 self.option.v2g_charge_efficiency * 0.8
        elif energy_change < 0:
            # Deşarj
            vehicle.soc_start += (energy_change / 
                                  (vehicle.max_power_kw * 0.8)) * \
                                 self.option.v2g_discharge_efficiency * 0.8
        
        # SOC sınırlarına sıkıştır
        vehicle.soc_start = max(0.0, min(1.0, vehicle.soc_start))
    
    def get_priority_schedule(self, current_time: float,
                              departure_window_hours: float = 2.0) -> list:
        """Ayrılma yaklaşan araçları sıraya koy.
        
        Returns:
            (vehicle_id, hours_until_departure) tuple'ların sıralı listesi
        """
        vehicles_near_departure = []
        
        for vehicle_id, vehicle in self.connected_vehicles.items():
            hours_until = vehicle.departure_time - current_time
            
            if 0 < hours_until <= departure_window_hours:
                vehicles_near_departure.append(
                    (vehicle_id, hours_until, vehicle.soc_start)
                )
        
        # Ayrılma zamanına göre sırala (en yakından başla)
        vehicles_near_departure.sort(key=lambda x: x[1])
        
        return vehicles_near_departure


class V2GOptimizer:
    """V2G için optimizasyon modülü.
    
    Amaç: Grid maliyetini minimize et veya grid desteğini optimize et
    Kısıtlar:
    - Vehicle SOC sınırları
    - Ayrılış zamanları
    - Power limits
    
    Model:
        min: Σ(t) price[t] * (grid_power[t] - v2g_discharge[t])
        
        subject to:
            SOC[t+1] = SOC[t] + (charge[t]*η_c - discharge[t]/η_d) * Δt
            SOC_min ≤ SOC[t] ≤ SOC_max
            discharge[t] ≤ max_power (V2G için)
    """
    
    def __init__(self, option: Optional[V2GOption] = None):
        self.option = option or V2GOption()
        self.strategy = V2GStrategy(option)
    
    def optimize_v2g_schedule(self, vehicles: list[VehicleState],
                               hours: np.ndarray,
               prices: np.ndarray) -> dict:
        """V2G şarj/deşarj planını optimize et.
        
        Args:
            vehicles: VehicleState listesi
            hours: Saat dizisi (0-24 arası)
            prices: Fiyat dizisi
            
        Returns:
            Plan sonuçları
        """
        n_periods = len(hours)
        
        # Her periyot için araçların toplam V2G gücü
        v2g_discharge = np.zeros(n_periods)
        
        for t, (hour, price) in enumerate(zip(hours, prices)):
            # Grid talebi yüksek mi? (basit: ortalamanın %120'i üstü)
            avg_price = np.mean(prices)
            high_demand = price > avg_price * 1.2
            
            for vehicle in vehicles:
                # Ayrılma yaklaşmıyor mu?
                hours_until_dep = vehicle.departure_time - hour
                if hours_until_dep > 1.0 and vehicle.soc_start >= self.option.v2g_soc_threshold:
                    # Pahalı saatte veya yüksek talepte deşarj
                    if price > 5.0 or high_demand:
                        v2g_discharge[t] += min(
                            vehicle.max_power_kw,
                            self.option.max_discharge_power_kw
                        )
        
        # Maliyet hesapla
        v2g_benefit = np.sum(v2g_discharge * prices * 0.25)  # 15 dk adım
        
        return {
            'v2g_discharge': v2g_discharge,
            'total_energy_discharged': np.sum(v2g_discharge) * 0.25,
            'v2g_benefit_tl': v2g_benefit,
        }


def test_v2g_strategy():
    """V2G stratejisini test et."""
    print("=" * 60)
    print("V2G (Vehicle-to-Grid) STRATEJİSİ - TEST")
    print("=" * 60)
    
    # V2G opsiyonu
    option = V2GOption(
        v2g_soc_threshold=0.85,
        max_discharge_power_kw=50.0
    )
    
    strategy = V2GStrategy(option)
    
    # Test araçları
    vehicles = [
        VehicleState(
            vehicle_id="EV001",
            arrival_time=14.0,
            departure_time=22.0,
            soc_start=0.90,
            energy_required_kwh=10.0,
            soc_target=0.85,
            max_power_kw=50.0
        ),
        VehicleState(
            vehicle_id="EV002",
            arrival_time=18.0,
            departure_time=23.0,
            soc_start=0.75,  # Düşük SOC - deşarj yapmayacak
            energy_required_kwh=25.0,
            soc_target=0.95,
            max_power_kw=50.0
        ),
    ]
    
    # Araçları ekle
    for v in vehicles:
        strategy.add_vehicle(v)
    
    # Saatlik test
    print("\nSaatlik V2G Deşarj Gücü:")
    print("-" * 40)
    
    prices = np.array([2.94, 2.94, 2.94, 2.94, 2.94, 2.94,  # 0-5 gece
                       4.38, 4.38, 4.38, 4.38, 4.38, 4.38,    # 6-11 gündüz
                       4.38, 4.38, 4.38, 4.38,                # 12-15 gündüz
                       6.17, 6.17, 6.17,                      # 16-18 puant
                       6.17, 6.17, 4.38])                     # 19-20 puant/gündüz
    
    for hour in range(24):
        price = prices[hour] if hour < len(prices) else 4.38
        high_demand = price > 5.0
        
        total_power = strategy.get_total_discharge_power(hour, price, high_demand)
        
        # Araç ayrıntılarını yaz
        for v in vehicles:
            power = strategy.get_vehicle_discharge_power(
                v.vehicle_id, hour, price, high_demand
            )
            if power > 0:
                print(f"  {hour:2d}:00 - {v.vehicle_id} (SOC={v.soc_start:.1%}): "
                      f"{power:.1f} kW deşarj")
        
        if total_power > 0:
            print(f"    >> Toplam V2G: {total_power:.1f} kW (Fiyat: {price:.2f} TL)")
    
    # V2G optimizasyonu
    print("\n" + "-" * 40)
    print("V2G Optimizasyonu:")
    
    optimizer = V2GOptimizer(option)
    
    hours = np.arange(96) / 4.0  # 15 dk adım, 24 saat
    prices = np.where(
        (hours >= 0) & (hours < 6),
        2.94,
        np.where(
            (hours >= 17) & (hours < 20),
            6.17,
            np.where(
                (hours >= 6) & (hours < 17),
                4.38,
                2.94
            )
        )
    )
    
    result = optimizer.optimize_v2g_schedule(vehicles, hours, prices)
    
    print(f"  Toplam V2G Enerjisi: {result['total_energy_discharged']:.1f} kWh")
    print(f"  V2G Kazanç: {result['v2g_benefit_tl']:.2f} TL")
    
    print("=" * 60)
    print()


if __name__ == "__main__":
    test_v2g_strategy()
