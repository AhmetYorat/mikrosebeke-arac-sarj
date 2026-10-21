"""Ada (islanded) mod yönetimi (PRD v2 - Simulink D4 Senaryosu).

Bu modül EM-3 tarafından geliştirilmektedir.

PRD v2 - Ada Modu (Islanded Mode):
Senaryo D4: Şebeke kesilir; PV + batarya + V2G ile sistem ayakta kalıyor mu?
- Ana şebeke bağlantısı kesilir
- PV üretimi, batarya ve V2G ile yükler beslenir
- Kritik yük önceliklendirme
- Frekans ve gerilim kontrolü

Ada modu çalışması için:
1. grid_connected = False durumu
2. PV + BESS + V2G gücü toplam yüke yeterli mi?
3. Kritik yüklerin korunması
4. Frekans sınırları içinde kalma (0.95-1.05 p.u.)
"""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class IslandedConfig:
    """Ada modu yapılandırması."""
    
    # Frekans sınırları (p.u.)
    freq_min: float = 0.95
    freq_max: float = 1.05
    
    # Gerilim sınırları (p.u.)
    voltage_min: float = 0.90
    voltage_max: float = 1.10
    
    # Kritik yük oranları (toplam yüke göre)
    critical_load_ratio: float = 0.30  # En az %30 kritik yük korunmalı
    
    # Batarya limitleri
    bess_min_soc: float = 0.20         # Minimum SOC (kurtarma için)
    
    # V2G sınırları
    v2g_min_soc: float = 0.40          # V2G için minimum SOC


@dataclass
class LoadCategory:
    """Yük kategorisi."""
    
    name: str
    power_kw: float
    is_critical: bool = False


class IslandedModeManager:
    """Ada modu yönetimi ve yük kesme stratejisi.
    
    Özellikler:
    - Ada modu geçişi yönetimi
    - Kritik/non-kritik yük ayırt etme
    - load shedding (yük kesme) stratejisi
    - Frekans ve gerilim takibi (basitleştirilmiş)
    """
    
    def __init__(self, config: Optional[IslandedConfig] = None):
        """Ada modu yöneticisini başlat."""
        self.config = config or IslandedConfig()
        
        # Mod durumu
        self.grid_connected: bool = True
        self.islanded_since: Optional[float] = None
        
        # Yüpler
        self.loads: dict[str, LoadCategory] = {}
        self.total_load_kw: float = 0.0
        
        # Güç kaynakları
        self.pv_power_kw: float = 0.0
        self.bess_discharge_kw: float = 0.0
        self.bess_charge_kw: float = 0.0
        self.v2g_power_kw: float = 0.0
        
        # Yük kesme durumu
        self.Shedded_loads: dict[str, float] = {}  # Kesilen yükler ve süreleri
    
    def add_load(self, load_id: str, power_kw: float, is_critical: bool = False) -> None:
        """Bir yük ekle.
        
        Args:
            load_id: Yük ID'si
            power_kw: Yêu gücü (kW)
            is_critical: Kritik yük mü?
        """
        self.loads[load_id] = LoadCategory(
            name=load_id,
            power_kw=power_kw,
            is_critical=is_critical
        )
        self.total_load_kw += power_kw
    
    def set_grid_status(self, connected: bool) -> None:
        """Grid bağlantısı durumunu ayarla.
        
        Args:
            connected: Grid bağlı mı?
        """
        if connected and not self.grid_connected:
            # Grid bağlanıyor - islanded modundan çık
            self.islanded_since = None
        elif not connected and self.grid_connected:
            # Grid kesiliyor - islanded mode başlıyor
            self.islanded_since = 0.0
        
        self.grid_connected = connected
    
    def set_pv_power(self, pv_kw: float) -> None:
        """PV üretim gücünü ayarla.
        
        Args:
            pv_kw: PV üretimi (kW)
        """
        self.pv_power_kw = max(0, pv_kw)
    
    def set_bess_power(self, bess_kw: float) -> None:
        """BESS gücünü ayarla.
        
        Args:
            bess_kw: BESS gücü (+şarj, -deşarj)
        """
        # Sadece deşarj gücü kullanılabilir güçte yer alır
        self.bess_discharge_kw = max(0, -bess_kw)  # Negatifse deşarj
        self.bess_charge_kw = max(0, bess_kw)       # Pozitifse şarj
    
    def set_v2g_power(self, v2g_kw: float) -> None:
        """V2G gücünü ayarla.
        
        Args:
            v2g_kw: V2G gücü (+deşarj, -şarj)
        """
        self.v2g_power_kw = max(0, v2g_kw)  # Sadece deşarj katkısı
    
    def get_available_power(self) -> float:
        """Kullanılabilir toplam gücü hesapla.
        
        Returns:
            Kullanılabilir güç (kW)
        """
        return self.pv_power_kw + self.bess_discharge_kw + self.v2g_power_kw
    
    def calculate_load_shedding(self) -> dict[str, float]:
        """Yük kesme (load shedding) planını hesapla.
        
        Strateji:
        1. Non-kritik yükleri önce kes
        2. Kritik yükler her zaman korunmalı
        3. Güç dengesi sağlanana kadar devam et
        
        Returns:
            Kesilecek yükler ve miktarları
        """
        available = self.get_available_power()
        deficit = self.total_load_kw - available
        
        if deficit <= 0:
            # Yeterli güç var, yük kesmeye gerek yok
            return {}
        
        # Kesilecek yükler
        shed_loads: dict[str, float] = {}
        
        # Non-kritik yükleri kes
        for load_id, load in sorted(self.loads.items(), 
                                    key=lambda x: not x[1].is_critical):
            if deficit <= 0:
                break
            
            if not load.is_critical and load_id not in self.Shedded_loads:
                # Bu yükün tamamını kesebilir miyiz?
                if load.power_kw <= deficit:
                    shed_loads[load_id] = load.power_kw
                    self.Shedded_loads[load_id] = load.power_kw  # Update here too
                    deficit -= load.power_kw
                else:
                    # Kısmi kesim
                    shed_loads[load_id] = deficit
                    self.Shedded_loads[load_id] = deficit  # Update here too
                    deficit = 0
        
        return shed_loads
    
    def get_critical_load_power(self) -> float:
        """Kritik yüklerin toplam gücünü döndür.
        
        Returns:
            Kritik yük gücü (kW)
        """
        return sum(l.power_kw for l in self.loads.values() if l.is_critical)
    
    def get_total_shed_load(self) -> float:
        """Toplam kesilen yükü döndür.
        
        Returns:
            Kesilen yük (kW)
        """
        return sum(self.Shedded_loads.values())
    
    def is_stable(self) -> bool:
        """Sistem stabil mı kontrol et.
        
        Returns:
            Stabil mi?
        """
        available = self.get_available_power()
        total_shed = self.get_total_shed_load()
        
        # Yük kesmeden önceki toplam yük
        original_total = self.total_load_kw + total_shed
        
        if original_total == 0:
            return True
        
        # Yeterli güç var mı?
        if available >= self.total_load_kw:
            return True
        
        # Load shedding ile dengeleniyor mu?
        effective_total = self.total_load_kw - total_shed
        return available >= effective_total * 0.95  # %5 tolerans
    
    def estimate_islanding_time(self) -> float:
        """Ada modunda tahmini kalış süresini hesapla (BESS tabanlı).
        
        Returns:
            Tahmini süre (saat)
        """
        # BESS kapasitesinden tahmin
        if self.bess_discharge_kw <= 0:
            return float('inf')
        
        # Örnek: 200 kWh BESS, 50 kW yükte ~4 saat
        # Basitleştirilmiş hesap
        bess_energy_kwh = 200.0 * (1 - self.config.bess_min_soc)  # Kullanılabilir enerji
        avg_load_kw = self.total_load_kw * (1 - self.config.critical_load_ratio)
        
        if avg_load_kw <= 0:
            return float('inf')
        
        return bess_energy_kwh / avg_load_kw


def test_islanded_mode():
    """Ada modunu test et."""
    print("=" * 60)
    print("ADA (ISLANDED) MODU YÖNETİCİSİ - TEST")
    print("=" * 60)
    
    # Konfigürasyon
    config = IslandedConfig(
        critical_load_ratio=0.30,
        bess_min_soc=0.20
    )
    
    manager = IslandedModeManager(config)
    
    # Yükleme (örnek bir bina)
    print("\nYük Tanımları:")
    test_loads = [
        ("Lighting", 15.0, True),       # Kritik: Aydınlatma
        ("HVAC", 30.0, False),          # Non-kritik: HVAC
        ("Computers", 10.0, True),      # Kritik: Bilgisayarlar
        ("Kitchen", 20.0, False),       # Non-kritik: Mutfak
        ("EV_Charging", 40.0, False),   # Non-kritik: EV şarj
    ]
    
    for load_id, power, is_critical in test_loads:
        manager.add_load(load_id, power, is_critical)
        print(f"  {load_id}: {power:.1f} kW {'[KRİTİK]' if is_critical else ''}")
    
    print(f"\nToplam Yük: {manager.total_load_kw:.1f} kW")
    
    # Grid bağlantısı kesiliyor
    print("\n--- GRID KESİLİYOR ---")
    manager.set_grid_status(False)
    
    # Güç kaynakları
    print("\nGüç Kaynakları:")
    manager.set_pv_power(25.0)   # PV üretimi
    manager.set_bess_power(-50.0)  # BESS deşarj (50 kW)
    manager.set_v2g_power(30.0)  # V2G deşarj (30 kW)
    
    available = manager.get_available_power()
    print(f"  PV: {manager.pv_power_kw:.1f} kW")
    print(f"  BESS (deşarj): {abs(manager.bess_discharge_kw):.1f} kW")
    print(f"  V2G: {manager.v2g_power_kw:.1f} kW")
    print(f"  Toplam Kullanılabilir: {available:.1f} kW")
    
    # Load shedding
    print("\nGüç Dengeleme:")
    deficit = manager.total_load_kw - available
    print(f"  Eksik Güç: {deficit:.1f} kW")
    
    shed_loads = manager.calculate_load_shedding()
    
    if shed_loads:
        print("\nYük Kesme Planı:")
        total_shed = 0.0
        for load_id, power in shed_loads.items():
            print(f"  {load_id}: {power:.1f} kW kesilecek")
            total_shed += power
        print(f"\n  Toplam Kesilen: {total_shed:.1f} kW")
        
        # Kritik yük korunuyor mu?
        critical_power = manager.get_critical_load_power()
        print(f"\n  Kritik Yük Gücü (Korunan): {critical_power:.1f} kW")
    else:
        print("  Yük kesme gerekmedi - güç yeterli!")
    
    # Stabillik
    print("\nStabillik Durumu:")
    stable = manager.is_stable()
    print(f"  Sistem {'STABIL' if stable else 'DENGESIZ'}")
    
    # Tahmini islanding süresi
    est_time = manager.estimate_islanding_time()
    print(f"  Tahmini Kalış Süresi: {est_time:.1f} saat")
    
    print("=" * 60)
    print()


if __name__ == "__main__":
    test_islanded_mode()
