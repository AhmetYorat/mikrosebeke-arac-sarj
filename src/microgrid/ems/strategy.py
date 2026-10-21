"""Kural tabanlı akıllı şarj stratejileri (YM-3, Hafta 1).

Bu modül EM-3 tarafından geliştirilmektedir.
Stratejiler: tariff-based, SOC-based, hybrid (tariff + SOC)

Akıllı şarj amacı: Elektrik fiyatlarına ve batarya durumuna göre
şarj gücünü modüle ederek maliyeti azaltmak ve tepe yükü önlemektir.

Stratejiler:
1. Tarife temelli: En ucuz saatlerde tam şarj
2. SOC temelli: Batarya doluluğuna göre şarj gücü ayarı
3. Hibrit: Tarife + SOC kombinasyonu (önerilen)
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class ChargeStrategyConfig:
    """Akıllı şarj strateji yapılandırması."""
    
    # Tarife period isimleri
    cheap_period: str = "gece"      # En ucuz periyot
    expensive_period: str = "puant"  # En pahalı periyot
    
    # SOC eşikleri
    soc_low_threshold: float = 0.3   # Alt eşik - acil şarj gerekli
    soc_high_threshold: float = 0.8  # Üst eşik - şarj yavaşlat
    
    # Şarj gücü modülasyonu
    max_charge_power_factor: float = 1.0   # Maksimum şarj gücü (normalized)
    min_charge_power_factor: float = 0.3   # Minimum şarj gücü (normalized)


class TariffBasedStrategy:
    """Tarife temelli akıllı şarj stratejisi.
    
    En ucuz saatlerde (gece) maksimum güçte şarj yapar.
    Puant saatlerinde minimal veya sıfır şarj.
    """
    
    def __init__(self, config: Optional[ChargeStrategyConfig] = None):
        self.config = config or ChargeStrategyConfig()
    
    def get_charge_power(self, hour: float, max_power: float,
                         tariff_period: str) -> float:
        """Verilen saat ve tarife periyodu için şarj gücünü belirle.
        
        Args:
            hour: Saat (0-24 arası ondalık, ör. 18.5 = 18:30)
            max_power: Maksimum şarj gücü (kW)
            tariff_period: Geçerli tarife periyodu ("gece", "gunduz", "puant")
        
        Returns:
            Ayarlanan şarj gücü (kW)
        """
        if tariff_period == self.config.cheap_period:
            # Gece saatleri - maksimum güçte şarj
            return max_power * self.config.max_charge_power_factor
        elif tariff_period == self.config.expensive_period:
            # Puant saatleri - minimum veya sıfır şarj
            return max_power * self.config.min_charge_power_factor
        else:
            # Gündüz saatleri - orta seviye şarj
            return max_power * 0.6
    
    def get_schedule(self, hours: np.ndarray, max_power: float,
                     tariff_periods: np.ndarray) -> np.ndarray:
        """Birden fazla saat için şarj planı oluştur.
        
        Args:
            hours: Saat dizisi (0-24 arası)
            max_power: Maksimum şarj gücü (kW)
            tariff_periods: Her saat için tarife periyodu dizisi
        
        Returns:
            Şarj gücü zaman serisi (kW)
        """
        return np.array([
            self.get_charge_power(h, max_power, tp)
            for h, tp in zip(hours, tariff_periods)
        ])


class SOCBasedStrategy:
    """SOC (State of Charge) temelli şarj stratejisi.
    
    Batarya doluluğuna göre şarj gücünü ayarlar:
    - Düşük SOC (< 30%): Hızlı şarj
    - Orta SOC (30-80%): Normal şarj
    - Yüksek SOC (> 80%): Yavaş şarj (batarya ömrü için)
    """
    
    def __init__(self, config: Optional[ChargeStrategyConfig] = None):
        self.config = config or ChargeStrategyConfig()
    
    def get_charge_power(self, soc: float, max_power: float) -> float:
        """SOC'a göre şarj gücünü belirle.
        
        Args:
            soc: Batarya doluluk oranı (0-1 arası)
            max_power: Maksimum şarj gücü (kW)
        
        Returns:
            Ayarlanan şarj gücü (kW)
        """
        if soc < self.config.soc_low_threshold:
            # Düşük SOC - hızlı şarj
            return max_power * self.config.max_charge_power_factor
        elif soc > self.config.soc_high_threshold:
            # Yüksek SOC - yavaş şarj
            return max_power * self.config.min_charge_power_factor
        else:
            # Orta SOC - normal şarj
            return max_power * 0.8
    
    def get_schedule(self, soc_values: np.ndarray, max_power: float) -> np.ndarray:
        """SOC zaman serisine göre şarj planı oluştur.
        
        Args:
            soc_values: SOC zaman serisi (0-1 arası)
            max_power: Maksimum şarj gücü (kW)
        
        Returns:
            Şarj gücü zaman serisi (kW)
        """
        return np.array([
            self.get_charge_power(soc, max_power)
            for soc in soc_values
        ])


class HybridStrategy:
    """Hibrit strateji: Tarife + SOC kombinasyonu.
    
    En iyi sonuçları vermesi beklenen strateji:
    - Tarife bilgisini temel alır
    - Ama SOC sınırlamalarını da dikkate alır
    - Akıllı şarj için önerilen strateji
    """
    
    def __init__(self, config: Optional[ChargeStrategyConfig] = None):
        self.config = config or ChargeStrategyConfig()
        self.tariff_strategy = TariffBasedStrategy(config)
        self.soc_strategy = SOCBasedStrategy(config)
    
    def get_charge_power(self, hour: float, max_power: float,
                         tariff_period: str, soc: float) -> float:
        """Hibrit strateji ile şarj gücünü belirle.
        
        Strateji:
        1. Tarife temelli power_FACTOR'ı al
        2. SOC temelli power_FACTOR'ı al
        3. İkisinin çarpımını (element-wise) kullan
        
        Args:
            hour: Saat (0-24 arası)
            max_power: Maksimum şarj gücü (kW)
            tariff_period: Geçerli tarife periyodu
            soc: Batarya doluluk oranı (0-1 arası)
        
        Returns:
            Ayarlanan şarj gücü (kW)
        """
        tariff_power = self.tariff_strategy.get_charge_power(
            hour, max_power, tariff_period
        )
        
        soc_power = self.soc_strategy.get_charge_power(soc, max_power)
        
        # Hibrit: tarife ve SOC'nin kombinasyonu (arithmetic mean)
        combined_power = (tariff_power + soc_power) / 2
        
        return min(combined_power, max_power)
    
    def get_schedule(self, hours: np.ndarray, max_power: float,
                     tariff_periods: np.ndarray, soc_values: np.ndarray
                     ) -> np.ndarray:
        """Hibrit strateji ile şarj planı oluştur.
        
        Args:
            hours: Saat dizisi
            max_power: Maksimum şarj gücü (kW)
            tariff_periods: Her saat için tarife periyodu
            soc_values: Her saat için SOC değeri
        
        Returns:
            Şarj gücü zaman serisi (kW)
        """
        return np.array([
            self.get_charge_power(h, max_power, tp, soc)
            for h, tp, soc in zip(hours, tariff_periods, soc_values)
        ])


# Varsayılan strateji
default_strategy = HybridStrategy()


def rule_based(charge_demand_kw: float, tariff_price: float,
               soc: float, max_power_kw: float,
               strategy_type: str = "hybrid") -> float:
    """Kural tabanlı akıllı şarj ana fonksiyonu.
    
    Bu fonksiyon EM-3 tarafından EMS entegrasyonu için kullanılacaktır.
    
    Args:
        charge_demand_kw: Şarj talebi (kW)
        tariff_price: Geçerli saat için tarife (TL/kWh)
        soc: Batarya doluluk oranı (0-1 arası)
        max_power_kw: Maksimum şarj gücü (kW)
        strategy_type: Kullanılacak strateji ("tariff", "soc", "hybrid")
    
    Returns:
        Ayarlanan şarj gücü (kW)
    
    Examples:
        >>> config = ChargeStrategyConfig()
        >>> rule_based(50, 2.94, 0.2, 100)  # Gece, düşük SOC -> hızlı şarj
        100.0
        
        >>> rule_based(50, 6.17, 0.8, 100)  # Puant, yüksek SOC -> yavaş şarj
        30.0
    """
    strategies = {
        "tariff": TariffBasedStrategy(),
        "soc": SOCBasedStrategy(),
        "hybrid": HybridStrategy()
    }
    
    strategy = strategies.get(strategy_type, default_strategy)
    
    # Sadece SOC bazlı strateji SOC kullanır
    if isinstance(strategy, SOCBasedStrategy):
        return strategy.get_charge_power(soc, max_power_kw)
    
    # Tarife ve/veya hybrid stratejiler tarife period'ı belirlemek için
    # fiyat bilgisini kullanır (basit bir sınıflandırma)
    if tariff_price <= 3.5:
        period = "gece"
    elif tariff_price >= 5.5:
        period = "puant"
    else:
        period = "gunduz"
    
    if isinstance(strategy, TariffBasedStrategy):
        return strategy.get_charge_power(12, max_power_kw, period)  # Örnek saat
    else:  # HybridStrategy
        return strategy.get_charge_power(12, max_power_kw, period, soc)


def test_strategies():
    """Stratejileri test et ve sonuçları yazdır."""
    import pandas as pd
    
    print("=" * 60)
    print("AKILLI ŞARJ STRATEJİLERİ - TEST")
    print("=" * 60)
    
    hours = np.arange(24)
    config = ChargeStrategyConfig()
    
    # Tarife periyotlarını oluştur
    tariff_periods = []
    for h in hours:
        if 0 <= h < 6 or h >= 22:
            tariff_periods.append("gece")
        elif 6 <= h < 17:
            tariff_periods.append("gunduz")
        else:
            tariff_periods.append("puant")
    
    max_power = 100
    
    # Her stratejiyi test et
    strategies = {
        "Tarife Temelli": TariffBasedStrategy(config),
        "SOC Temelli": SOCBasedStrategy(config),
        "Hibrit": HybridStrategy(config)
    }
    
    results = []
    
    for name, strategy in strategies.items():
        if isinstance(strategy, SOCBasedStrategy):
            # SOC temelli için ortalama bir SOC kullan
            powers = [strategy.get_charge_power(0.5, max_power) for _ in hours]
        elif isinstance(strategy, HybridStrategy):
            # Hibrit strateji için hem saat hem SOC lazım
            powers = [
                strategy.get_charge_power(h, max_power, tp, 0.5)
                for h, tp in zip(hours, tariff_periods)
            ]
        else:
            # Tariff based
            powers = [
                strategy.get_charge_power(h, max_power, tp)
                for h, tp in zip(hours, tariff_periods)
            ]
        
        total_energy = sum(powers) * 0.25  # 15 dk adım
        results.append({"Strateji": name, "Toplam Enerji (kWh)": total_energy})
    
    df = pd.DataFrame(results)
    print(df.to_string(index=False))
    print()
    
    # Hibrit strateji detaylı
    print("Hibrit Strateji - Saatlik Detay:")
    print("-" * 40)
    soc_values = [0.5] * 24  # Sabit SOC
    
    for h, tp in zip(hours[:6], tariff_periods[:6]):
        power = strategies["Hibrit"].get_charge_power(h, max_power, tp, 0.5)
        print(f"  Saat {h:2d}:00 ({tp:8s}): {power:.1f} kW")
    
    print("=" * 60)
    print()


if __name__ == "__main__":
    test_strategies()
