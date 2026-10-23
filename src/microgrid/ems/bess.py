"""Batarya enerji depolama sistemi (BESS) modeli (YM-3, Hafta 1).

Bu modül EM-3 tarafından geliştirilmektedir.
BESS modeli: durum değişkenleri, constraints, step fonksiyonu

Özellikler:
- SOC (State of Charge) tabanlı modelleme
- Verimlilik kayıpları (şarj/deşarj)
- SOC limitleri ve koruma
- Çıkarım能力 (power) sınırlamaları

Not: Bu modül kural tabanlı simülasyon için. MILP optimizasyonu icin
optimizer.py modülüne bak.
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class BESSConfig:
    """BESS yapılandırması."""
    
    # Kapasite
    capacity_kwh: float = 200.0      # Toplam kapasite (kWh)
    max_power_kw: float = 100.0      # Maksimum güç (kW)
    
    # SOC limitleri
    soc_min: float = 0.1             # Minimum SOC (10%)
    soc_max: float = 0.95            # Maximum SOC (95%)
    
    # Verimlilik
    charge_efficiency: float = 0.95  # Şarj verimi
    discharge_efficiency: float = 0.92  # Deşarj verimi
    
    # Başlangıç durumu
    initial_soc: float = 0.5         # Başlangıç SOC (50%)


class BESS:
    """Batarya Enerji Depolama Sistemi (BESS) modeli.
    
    Durum değişkenleri:
    - soc: State of Charge (0-1 arası)
    - energy_remaining: Kalan enerji (kWh)
    
    Girdiler:
    - charge_power: Şarj gücü (kW, pozitif)
    - discharge_power: Deşarj gücü (kW, negatif veya discharge_power parametresi)
    
    Çıktılar:
    - new_soc: Yeni SOC değeri
    - actual_charge_power: Gerçek şarj gücü (kayıp dahil)
    - actual_discharge_power: Gerçek deşarj gücü (kayıp dahil)
    
    Kullanım:
        bess = BESS(capacity_kwh=200, max_power_kw=100)
        bess.reset(soc=0.5)  # Başlangıç
        
        # Şarj et
        new_soc, actual_power = bess.step(charge_power=80)
        
        # Deşarj et
        new_soc, actual_power = bess.step(discharge_power=50)
    """
    
    def __init__(self, config: Optional[BESSConfig] = None):
        """BESS modelini başlat."""
        self.config = config or BESSConfig()
        
        # Durum değişkenleri
        self._soc: float = self.config.initial_soc
        self._energy_remaining: float = self._soc * self.config.capacity_kwh
        
        # Geçmiş veriler
        self.history: list = []
    
    def reset(self, soc: Optional[float] = None) -> None:
        """BESS'i başlangıç durumuna sıfırla veya belirli SOC ile başlat.
        
        Args:
            soc: Başlangıç SOC (0-1 arası). None ise config'deki değer.
        """
        if soc is not None:
            self._soc = max(self.config.soc_min, min(self.config.soc_max, soc))
        else:
            self._soc = self.config.initial_soc
        
        self._energy_remaining = self._soc * self.config.capacity_kwh
        self.history = []
    
    @property
    def soc(self) -> float:
        """Mevcut SOC değerini döndür."""
        return self._soc
    
    @property
    def energy_remaining(self) -> float:
        """Mevcut enerji miktarını döndür."""
        return self._energy_remaining
    
    def get_available_energy(self) -> float:
        """Kullanılabilir enerjiyi döndür."""
        return self._energy_remaining
    
    def get_max_discharge_power(self) -> float:
        """Maksimum deşarj gücünü döndür."""
        return self.config.max_power_kw
    
    def get_max_charge_power(self) -> float:
        """Maksimum şarj gücünü döndür."""
        return self.config.max_power_kw
    
    def step(self, charge_power: Optional[float] = None,
             discharge_power: Optional[float] = None) -> tuple:
        """BESS'in bir adım ilerlemesini simüle et.
        
        Args:
            charge_power: Şarj gücü (kW, pozitif). None ise şarj yok.
            discharge_power: Deşarj gücü (kW, pozitif). None ise deşarj yok.
        
        Returns:
            tuple: (new_soc, actual_power)
            - new_soc: Yeni SOC değeri
            - actual_power: Gerçek güç (şarj ise pozitif, deşarj ise negatif)
        
        Raises:
            ValueError: Çakışan şarj/deşarj talebi varsa
        """
        if charge_power is not None and discharge_power is not None:
            raise ValueError("Same step cannot have both charge and discharge power.")
        
        if charge_power is None and discharge_power is None:
            return self._soc, 0.0
        
        # Kapasite sınırlarını kontrol et
        max_charge = self.config.max_power_kw
        max_discharge = min(
            self.config.max_power_kw,
            self._energy_remaining / 0.25  # 15 dk için
        )
        
        if charge_power is not None:
            # Şarj işlemi
            effective_charge = min(charge_power, max_charge)
            
            # SOC limitlerini kontrol et
            energy_needed = effective_charge * 0.25 / self.config.charge_efficiency
            if self._energy_remaining + energy_needed > \
               self.config.capacity_kwh * self.config.soc_max:
                effective_charge = (
                    (self.config.capacity_kwh * self.config.soc_max - self._energy_remaining)
                    * self.config.charge_efficiency / 0.25
                )
            
            actual_power = effective_charge
            energy_stored = effective_charge * 0.25 * self.config.charge_efficiency
            self._energy_remaining += energy_stored
            
        else:  # discharge_power is not None
            # Deşarj işlemi
            effective_discharge = min(discharge_power, max_discharge)
            
            # SOC limitlerini kontrol et
            energy_available = effective_discharge * 0.25 * self.config.discharge_efficiency
            if self._energy_remaining - energy_available < \
               self.config.capacity_kwh * self.config.soc_min:
                effective_discharge = (
                    (self._energy_remaining - self.config.capacity_kwh * self.config.soc_min)
                    / 0.25 / self.config.discharge_efficiency
                )
            
            actual_power = -effective_discharge  # Negatif: deşarj
            energy_released = effective_discharge * 0.25 * self.config.discharge_efficiency
            self._energy_remaining -= energy_released
        
        # SOC'u güncelle
        self._soc = self._energy_remaining / self.config.capacity_kwh
        
        # Geçmişi kaydet
        self.history.append({
            'soc_before': self._soc,
            'power': actual_power,
            'energy_remaining': self._energy_remaining
        })
        
        return self._soc, actual_power
    
    def simulate(self, power_profile: np.ndarray) -> dict:
        """Verilen güç profili için BESS simülasyonu çalıştır.
        
        Args:
            power_profile: Güç zaman serisi (pozitif = şarj, negatif = deşarj)
        
        Returns:
            dict: Simülasyon sonuçları
        """
        soc_values = []
        energy_values = []
        actual_powers = []
        
        for power in power_profile:
            if power >= 0:
                soc, actual = self.step(charge_power=power)
            else:
                soc, actual = self.step(discharge_power=-power)
            
            soc_values.append(soc)
            energy_values.append(self._energy_remaining)
            actual_powers.append(actual)
        
        return {
            'soc': np.array(soc_values),
            'energy_remaining': np.array(energy_values),
            'actual_power': np.array(actual_powers),
            'max_soc': max(soc_values),
            'min_soc': min(soc_values)
        }


def test_bess():
    """BESS modelini test et."""
    import pandas as pd
    
    print("=" * 60)
    print("BESS MODELİ - TEST")
    print("=" * 60)
    
    # BESS oluştur
    bess = BESS()
    
    print(f"BESS Parametreleri:")
    print(f"  Kapasite: {bess.config.capacity_kwh} kWh")
    print(f"  Maksimum Güç: {bess.config.max_power_kw} kW")
    print(f"  Başlangıç SOC: {bess.config.initial_soc:.0%}")
    print()
    
    # Test 1: Tam şarj
    print("Test 1: Maksimum şarj")
    bess.reset(soc=0.5)
    print(f"  Başlangıç SOC: {bess.soc:.0%}")
    
    # 1 saat (4 adım) maksimum şarj
    for i in range(4):
        soc, power = bess.step(charge_power=bess.config.max_power_kw)
        print(f"  Adım {i+1}: SOC = {soc:.0%}, Güç = {power:.1f} kW")
    
    print(f"  Bitiş SOC: {bess.soc:.0%}")
    print()
    
    # Test 2: Deşarj
    print("Test 2: Maksimum deşarj")
    bess.reset(soc=bess.soc)
    print(f"  Başlangıç SOC: {bess.soc:.0%}")
    
    for i in range(4):
        soc, power = bess.step(discharge_power=bess.config.max_power_kw)
        print(f"  Adım {i+1}: SOC = {soc:.0%}, Güç = {power:.1f} kW")
    
    print(f"  Bitiş SOC: {bess.soc:.0%}")
    print()
    
    # Test 3: Simülasyon - sabit şarj
    print("Test 3: 24 saat simülasyon (sabit şarj)")
    bess.reset(soc=0.3)
    
    import numpy as np
    hours = 24
    power_profile = np.array([80] * (hours * 4))  # Her 15 dk'da 80 kW şarj
    
    results = bess.simulate(power_profile)
    
    df = pd.DataFrame({
        'SOC': results['soc'][::4],  # Her saat
        'Güç (kW)': results['actual_power'][::4]
    })
    
    print(df.head(6).to_string(index=False))
    print(f"  ... ({len(results['soc'])} adım)")
    print()
    print(f"  SOC Aralığı: {results['min_soc']:.0%} - {results['max_soc']:.0%}")
    print()
    
    # Test 4: Günlük döngü
    print("Test 4: Günlük şarj-deşarj döngüsü")
    bess.reset(soc=0.5)
    
    # Gündüz şarj (10:00-18:00), gece deşarj (20:00-06:00)
    power_profile = []
    for h in range(24):
        if 10 <= h < 18:  # Gündüz şarj
            power_profile.extend([60, 60, 60, 60])  # Her 15 dk
        elif 20 <= h < 24 or 0 <= h < 6:  # Gece deşarj
            power_profile.extend([-40, -40, -40, -40])
        else:
            power_profile.extend([0, 0, 0, 0])
    
    results = bess.simulate(np.array(power_profile))
    
    print(f"  Başlangıç SOC: 50%")
    print(f" Bitiş SOC: {results['soc'][-1]:.0%}")
    print(f"  Max SOC: {results['max_soc']:.0%}")
    print(f"  Min SOC: {results['min_soc']:.0%}")
    print()
    
    print("=" * 60)
    print()


if __name__ == "__main__":
    test_bess()