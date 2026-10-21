"""EMS Modülü Kullanım Örnekleri (YM-3).

Bu modül EM-3 tarafından geliştirilmektedir.
Hafta 1 ve Hafta 2 için örnek kullanım senaryoları.

Kullanım:
    python3 -m microgrid.ems.example
"""

import numpy as np

from .bess import BESS, BESSConfig
from .strategy import (
    rule_based,
    ChargeStrategyConfig,
    HybridStrategy
)
from .optimizer import EMSOptimizer, OptimizationConfig


def example_1_rule_based_charge():
    """Kural tabanlı akıllı şarj örneği."""
    print("=" * 60)
    print("ÖRNEK 1: KURAL TABANLI ŞARJ")
    print("=" * 60)
    
    # Konfigürasyon
    config = ChargeStrategyConfig()
    
    # Veriler
    hour = 2  # Saat (gece - düşük fiyat)
    max_power = 100  # kW
    tariff_price = 2.94  # TL/kWh (gece periyodu)
    soc = 0.3  # Düşük SOC
    
    # Şarj gücü hesapla
    charge_power = rule_based(
        charge_demand_kw=50,
        tariff_price=tariff_price,
        soc=soc,
        max_power_kw=max_power,
        strategy_type="hybrid"
    )
    
    print(f"Parametreler:")
    print(f"  Saat: {hour}:00")
    print(f"  Tarife: {tariff_price} TL/kWh (gece)")
    print(f"  SOC: {soc:.0%}")
    print(f"  Maksimum Güç: {max_power} kW")
    print()
    print(f"Sonuç:")
    print(f"  Önerilen Şarj Gücü: {charge_power:.1f} kW")
    print()
    
    # 24 saatlik simülasyon
    hours = np.arange(24)
    tariffs = []
    for h in hours:
        if 0 <= h < 6 or h >= 22:
            tariffs.append(2.94)  # Gece
        elif 6 <= h < 17:
            tariffs.append(4.38)  # Gündüz
        else:
            tariffs.append(6.17)  # Puant
    
    print("24 Saatlik Şarj Profili (Hibrit Strateji):")
    for h, t in zip(hours[:6], tariffs[:6]):
        power = rule_based(50, t, 0.5, max_power, "hybrid")
        period = "gece" if t == 2.94 else ("puant" if t > 5.5 else "gunduz")
        print(f"  Saat {h:2d}:00 ({period:8s}): {power:.1f} kW")
    print()


def example_2_bess_simulation():
    """BESS simülasyon örneği."""
    print("=" * 60)
    print("ÖRNEK 2: BESS SİMÜLASYONU")
    print("=" * 60)
    
    # BESS oluştur
    config = BESSConfig(
        capacity_kwh=200,
        max_power_kw=100,
        soc_min=0.1,
        soc_max=0.95,
        initial_soc=0.3
    )
    bess = BESS(config)
    
    print(f"BESS Parametreleri:")
    print(f"  Kapasite: {bess.config.capacity_kwh} kWh")
    print(f"  Maksimum Güç: {bess.config.max_power_kw} kW")
    print(f"  Başlangıç SOC: {bess.config.initial_soc:.0%}")
    print()
    
    # 1 saatlik şarj (4 adım)
    bess.reset(soc=0.3)
    print("1 saatlik maksimum şarj:")
    for i in range(4):
        soc, power = bess.step(charge_power=100)
        print(f"  Adım {i+1}: SOC = {soc:.0%}, Güç = {power:.1f} kW")
    
    print(f"  Bitiş SOC: {bess.soc:.0%}")
    print()
    
    # Günlük simülasyon
    print("24 saatlik şarj profili:")
    bess.reset(soc=0.3)
    
    # Gündüz şarj (10:00-18:00), max PV gücü 50 kW
    power_profile = []
    for h in range(24):
        if 10 <= h < 18:
            power_profile.extend([50, 50, 50, 50])  # Her 15 dk
        else:
            power_profile.extend([0, 0, 0, 0])
    
    results = bess.simulate(np.array(power_profile))
    print(f"  Başlangıç SOC: 30%")
    print(f"  Maksimum SOC: {results['max_soc']:.0%}")
    print(f"  Bitiş SOC: {results['soc'][-1]:.0%}")
    print()


def example_3_optimization():
    """MILP optimizasyon örneği."""
    print("=" * 60)
    print("ÖRNEK 3: MILP OPTİMİZASYONU")
    print("=" * 60)
    
    # Veri oluştur
    n_periods = 96  # 24 saat / 15 dk adım
    hours = np.arange(n_periods) / 4
    
    # Tipik yük profili (akşam saatlerinde yüksek)
    load = np.where(
        (hours >= 18) & (hours <= 22),
        70 + 30 * np.sin((hours - 18) * np.pi / 4),
        50 + 10 * np.sin(hours * np.pi / 12)
    )
    
    # PV üretimi (gün içinde yüksek)
    pv = np.where(
        (hours >= 6) & (hours <= 18),
        50 * np.sin((hours - 6) * np.pi / 12),
        0
    )
    pv = np.maximum(pv, 0)
    
    # Tarife profili
    prices = np.where(
        (hours >= 0) & (hours < 6),
        2.94,
        np.where(
            (hours >= 6) & (hours < 17),
            4.38,
            np.where(
                (hours >= 17) & (hours < 20),
                6.17,
                2.94
            )
        )
    )
    
    print("Veri Özeti:")
    print(f"  Yük: {load.mean():.1f} kW ortalama, {load.max():.1f} kW maksimum")
    print(f"  PV: {pv.mean():.1f} kW ortalama, {pv.max():.1f} kW maksimum")
    print(f"  Ortalama Fiyat: {prices.mean():.2f} TL/kWh")
    print()
    
    # Optimizasyonu çalıştır
    opt_config = OptimizationConfig(
        bess_capacity_kwh=200,
        bess_max_power_kw=100,
        initial_soc=0.5
    )
    
    opt = EMSOptimizer(opt_config)
    result = opt.optimize(load, pv, prices)
    
    print(f"Optimizasyon Sonucu:")
    print(f"  Durum: {result['status']}")
    if result['status'] == 'Optimal':
        print(f"  Toplam Maliyet: {result['total_cost']:.2f} TL")
        print(f"  BESS Throughput: {result['bess_throughput']:.1f} kWh")
        
        # SOC profili
        print()
        print("SOC Profili:")
        print(f"  Başlangıç: {result['soc'][0]:.0%}")
        print(f"  Minimum: {min(result['soc']):.0%}")
        print(f"  Maksimum: {max(result['soc']):.0%}")
        print(f"  Bitiş: {result['soc'][-1]:.0%}")
        
        # Grid power özet
        grid_power = result['grid_power']
        net_consumption = np.sum(grid_power) * 0.25
        print()
        print("Enerji Akışı:")
        print(f"  Toplam Çekilen Enerji: {net_consumption:.1f} kWh")
        print(f"  Toplam PV Üretimi: {np.sum(pv) * 0.25:.1f} kWh")
        print(f"  Toplam Yük: {np.sum(load) * 0.25:.1f} kWh")
    
    print()


def example_4_full_system():
    """Tam sistem entegrasyon örneği."""
    print("=" * 60)
    print("ÖRNEK 4: TAM SİSTEM ENTEGRASYONU")
    print("=" * 60)
    
    # Konfigürasyonlar
    bess_config = BESSConfig(
        capacity_kwh=200,
        max_power_kw=100,
        soc_min=0.2,
        soc_max=0.9
    )
    
    opt_config = OptimizationConfig(
        bess_capacity_kwh=200,
        bess_max_power_kw=100,
        initial_soc=0.5
    )
    
    # Veri oluştur
    n_periods = 96
    hours = np.arange(n_periods) / 4
    
    load = np.where(
        (hours >= 18) & (hours <= 22),
        70 + 30 * np.sin((hours - 18) * np.pi / 4),
        50 + 10 * np.sin(hours * np.pi / 12)
    )
    
    pv = np.where(
        (hours >= 6) & (hours <= 18),
        50 * np.sin((hours - 6) * np.pi / 12),
        0
    )
    pv = np.maximum(pv, 0)
    
    prices = np.where(
        (hours >= 0) & (hours < 6),
        2.94,
        np.where(
            (hours >= 6) & (hours < 17),
            4.38,
            np.where(
                (hours >= 17) & (hours < 20),
                6.17,
                2.94
            )
        )
    )
    
    print("Simülasyon Senaryosu:")
    print(f"  Periyot: {n_periods} adım (15 dk, 24 saat)")
    print(f"  BESS: {bess_config.capacity_kwh} kWh, {bess_config.max_power_kw} kW")
    print()
    
    # Optimizasyonla şarj planını al
    opt = EMSOptimizer(opt_config)
    result = opt.optimize(load, pv, prices)
    
    if result['status'] == 'Optimal':
        # BESS simülasyonu
        bess = BESS(bess_config)
        bess.reset(soc=0.5)
        
        actual_soc = [0.5]
        for t in range(n_periods):
            charge_power = result['charge'][t]
            discharge_power = result['discharge'][t]
            
            if charge_power > 0:
                soc, _ = bess.step(charge_power=charge_power)
            elif discharge_power > 0:
                soc, _ = bess.step(discharge_power=discharge_power)
            else:
                actual_soc.append(bess.soc)
                continue
            
            actual_soc.append(soc)
        
        print("Optimizasyon vs Simülasyon Karşılaştırması:")
        print(f"  Optimizasyon SOC: {result['soc'][0]:.0%} - {max(result['soc']):.0%}")
        print(f"  Simülasyon SOC: {actual_soc[0]:.0%} - {max(actual_soc):.0%}")
        print(f"  Fark: {abs(max(result['soc']) - max(actual_soc)):.1%}")
    
    print()


if __name__ == "__main__":
    example_1_rule_based_charge()
    example_2_bess_simulation()
    example_3_optimization()
    example_4_full_system()