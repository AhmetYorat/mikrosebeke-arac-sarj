"""EMS performans metrikleri (KPI'lar) (YM-3, Hafta 2).

Bu modül EM-3 tarafından geliştirilmektedir.
KPI'lar: BESS verimliliği, maliyet optimizasyonu, green energy utilization

Metrikler:
- Cost savings from optimization
- BESS efficiency and throughput
- Self-consumption and self-sufficiency
- Carbon footprint reduction (if applicable)

Kullanım:
    from microgrid.ems.kpi import calculate_kpis, print_kpi_report
    
    kpis = calculate_kpis(
        load=load,
        pv=pv,
        grid_power=grid_power,
        bess_charge=bess_charge,
        bess_discharge=bess_discharge,
        prices=prices
    )
    print_kpi_report(kpis)
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class EMSPatterns:
    """EMS metrik hesaplama parametreleri."""
    
    # Zaman parametreleri
    time_step_hours: float = 0.25  # 15 dk
    
    # Maliyet parametreleri
    energy_cost_threshold: float = 4.0  # TL/kWh, düşük/fazla maliyet sınırları
    
    # BESS parametreleri
    bess_efficiency_range: tuple = (0.85, 0.95)  # Minimum/maximum verimlilik


@dataclass
class KPIs:
    """EMS KPI sonuçları."""
    
    # Maliyet metrikleri
    total_energy_cost: float = 0.0          # Toplam enerji maliyeti (TL)
    optimized_cost: float = 0.0             # Optimizasyon sonrası maliyet (TL)
    baseline_cost: float = 0.0              # Baseline maliyet (TL)
    cost_savings: float = 0.0               # Tasarruf (TL)
    cost_savings_pct: float = 0.0           # Tasarruf oranı (%)
    
    # BESS metrikleri
    bess_throughput: float = 0.0            # BESS throughput (kWh)
    bess_cycles: float = 0.0                # Tam döngü sayısı
    avg_charge_power: float = 0.0           # Ortalama şarj gücü (kW)
    avg_discharge_power: float = 0.0        # Ortalama deşarj gücü (kW)
    
    # SOC metrikleri
    max_soc: float = 0.0                    # Maksimum SOC (%)
    min_soc: float = 0.0                    # Minimum SOC (%)
    soc_variance: float = 0.0               # SOC varyansı
    
    # Güç akışı metrikleri
    grid_consumption: float = 0.0           # Gridden çekilen enerji (kWh)
    grid_export: float = 0.0                # Gride verilen enerji (kWh)
    self_consumption: float = 0.0           # Kendi tüketilen PV (%)
    self_sufficiency: float = 0.0           # Kendi karşılanma oranı (%)
    
    # Yükseltme metrikleri
    peak_shaving: float = 0.0               # Peak shaving (kW)
    load_flattening: float = 0.0            # Load flattening


def calculate_kpis(
    load: np.ndarray,
    pv: np.ndarray,
    grid_power: np.ndarray,
    bess_charge: Optional[np.ndarray] = None,
    bess_discharge: Optional[np.ndarray] = None,
    prices: Optional[np.ndarray] = None,
    soc_values: Optional[np.ndarray] = None
) -> KPIs:
    """EMS performans metriklerini hesapla.
    
    Args:
        load: Yük gücü zaman serisi (kW)
        pv: PV üretim zaman serisi (kW)
        grid_power: Gridden çekilen güç zaman serisi (kW, pozitif = tüketim)
        bess_charge: BESS şarj gücü (kW, opsiyonel)
        bess_discharge: BESS deşarj gücü (kW, opsiyonel)
        prices: Elektrik fiyatları (TL/kWh, opsiyonel)
        soc_values: SOC zaman serisi (0-1 arası, opsiyonel)
    
    Returns:
        KPIs: Hesaplanmış metrikler
    """
    # Zaman parametreleri
    n_periods = len(load)
    dt = 0.25  # 15 dk = 0.25 saat
    
    # Girdileri kontrol et
    if len(pv) != n_periods or len(grid_power) != n_periods:
        raise ValueError("All input arrays must have the same length.")
    
    # Maliyet hesaplaması
    if prices is not None:
        energy_cost = np.sum(grid_power * prices * dt)
    else:
        #varsayılan fiyat kullan
        avg_price = 4.38  # orta dönem fiyat
        energy_cost = np.sum(grid_power * avg_price * dt)
    
    # BESS metrikleri
    if bess_charge is not None and bess_discharge is not None:
        bess_throughput = np.sum(bess_charge + bess_discharge) * dt
        
        # Döngü sayısı (her döngü = şarj + deşarj)
        total_energy_transferred = np.sum(np.abs(bess_charge - bess_discharge)) * dt
        bess_cycles = total_energy_transferred / (2 * 200)  # 200 kWh kapasite varsayımı
        
        avg_charge_power = np.mean(bess_charge)
        avg_discharge_power = np.mean(bess_discharge)
    else:
        bess_throughput = 0.0
        bess_cycles = 0.0
        avg_charge_power = 0.0
        avg_discharge_power = 0.0
    
    # SOC metrikleri
    if soc_values is not None:
        max_soc = float(np.max(soc_values))
        min_soc = float(np.min(soc_values))
        soc_variance = float(np.var(soc_values))
    else:
        max_soc = 0.5
        min_soc = 0.5
        soc_variance = 0.0
    
    # Güç akışı metrikleri
    grid_consumption = np.sum(np.maximum(0, grid_power)) * dt
    grid_export = np.sum(np.minimum(0, grid_power)) * dt  # Negatif = export
    
    # Self-consumption ve self-sufficiency
    total_load = np.sum(load) * dt
    total_pv = np.sum(pv) * dt
    
    if total_load > 0:
        self_consumption = (total_pv - max(0, grid_export)) / total_load * 100
        self_sufficiency = (total_pv - max(0, grid_export)) / total_load * 100
    else:
        self_consumption = 0.0
        self_sufficiency = 0.0
    
    # Peak shaving ve load flattening
    peak_load = np.max(load)
    avg_load = np.mean(load)
    
    if grid_power is not None:
        peak_grid_power = np.max(np.abs(grid_power))
        avg_grid_power = np.mean(np.abs(grid_power))
        
        peak_shaving = peak_load - avg_load
        load_flattening = 1 - (avg_grid_power / peak_load) if peak_load > 0 else 0
    
    return KPIs(
        total_energy_cost=energy_cost,
        bess_throughput=bess_throughput,
        bess_cycles=bess_cycles,
        avg_charge_power=float(avg_charge_power),
        avg_discharge_power=float(avg_discharge_power),
        max_soc=max_soc,
        min_soc=min_soc,
        soc_variance=soc_variance,
        grid_consumption=grid_consumption,
        grid_export=-grid_export,  # Pozitif değer için
        self_consumption=self_consumption,
        self_sufficiency=self_sufficiency,
        peak_shaving=peak_shaving,
        load_flattening=load_flattening
    )


def compare_strategies(
    baseline_cost: float,
    optimized_cost: float,
    bess_throughput: float
) -> dict:
    """İki stratejiyi karşılaştır.
    
    Args:
        baseline_cost: Kural tabanlı maliyet (TL)
        optimized_cost: Optimizasyonlu maliyet (TL)
        bess_throughput: BESS throughput (kWh)
    
    Returns:
        dict: Karşılaştırma sonuçları
    """
    cost_savings = baseline_cost - optimized_cost
    savings_pct = (cost_savings / baseline_cost * 100) if baseline_cost > 0 else 0
    
    return {
        'baseline_cost': baseline_cost,
        'optimized_cost': optimized_cost,
        'cost_savings': cost_savings,
        'savings_pct': savings_pct,
        'bess_throughput': bess_throughput
    }


def print_kpi_report(kpis: KPIs, title: str = "EMS Performans Raporu") -> None:
    """KPI raporunu yazdır.
    
    Args:
        kpis: Hesaplanmış KPI'lar
        title: Rapor başlığı
    """
    print("=" * 60)
    print(title)
    print("=" * 60)
    
    # Maliyet
    print("\n💰 MALİYET METRİKLERİ:")
    print(f"  Toplam Enerji Maliyeti: {kpis.total_energy_cost:.2f} TL")
    if kpis.cost_savings > 0:
        print(f"  Tasarruf: {kpis.cost_savings:.2f} TL ({kpis.cost_savings_pct:.1f}%)")
    
    # BESS
    print("\n🔋 BESS METRİKLERİ:")
    print(f"  Throughput: {kpis.bess_throughput:.1f} kWh")
    print(f"  Döngü Sayısı: {kpis.bess_cycles:.2f} tam döngü")
    print(f"  Ort. Şarj Gücü: {kpis.avg_charge_power:.1f} kW")
    print(f"  Ort. Deşarj Gücü: {kpis.avg_discharge_power:.1f} kW")
    
    # SOC
    print("\n📊 SOC DİNAMİĞİ:")
    print(f"  Maksimum SOC: {kpis.max_soc:.0%}")
    print(f"  Minimum SOC: {kpis.min_soc:.0%}")
    print(f"  Varyans: {kpis.soc_variance:.6f}")
    
    # Güç Akışı
    print("\n⚡ GÜÇ AKIŞI:")
    print(f"  Gridden Çekilen: {kpis.grid_consumption:.1f} kWh")
    print(f"  Gride Verilen: {kpis.grid_export:.1f} kWh")
    print(f"  Self Consumption: {kpis.self_consumption:.1f}%")
    print(f"  Self Sufficiency: {kpis.self_sufficiency:.1f}%")
    
    # Yük Düzeltme
    print("\n📈 YÜK DÜZELTME:")
    print(f"  Peak Shaving: {kpis.peak_shaving:.1f} kW")
    print(f"  Load Flattening: {kpis.load_flattening:.1%}")
    
    print("\n" + "=" * 60)


def test_kpis():
    """KPI hesaplamalarını test et."""
    print("=" * 60)
    print("KPI HESAPLAMALARI - TEST")
    print("=" * 60)
    
    # Test verisi
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
    
    # Simüle edilmiş grid power (önceki optimizasyondan)
    np.random.seed(42)
    grid_power = load - pv + np.random.normal(0, 5, n_periods)
    grid_power = np.maximum(grid_power, 0)  # Sadece tüketim varsay
    
    # BESS verileri
    bess_charge = np.where(grid_power > 60, grid_power - 60, 0)
    bess_discharge = np.where(load > 70, load - 70, 0)
    
    # SOC profili
    soc_values = np.linspace(0.5, 0.6, n_periods)
    
    # KPI'ları hesapla
    kpis = calculate_kpis(
        load=load,
        pv=pv,
        grid_power=grid_power,
        bess_charge=bess_charge,
        bess_discharge=bess_discharge,
        prices=prices,
        soc_values=soc_values
    )
    
    # Raporu yazdır
    print_kpi_report(kpis)
    
    # Karşılaştırma
    baseline_cost = 8609.61  # Kural tabanlı maliyet
    optimized_cost = kpis.total_energy_cost
    
    comparison = compare_strategies(baseline_cost, optimized_cost, kpis.bess_throughput)
    
    print("\n📈 STRATEJI KARŞILAŞTIRMASI:")
    print(f"  Kural Tabanlı: {comparison['baseline_cost']:.2f} TL")
    print(f"  Optimizasyonlu: {comparison['optimized_cost']:.2f} TL")
    print(f"  Tasarruf: {comparison['cost_savings']:.2f} TL ({comparison['savings_pct']:.1f}%)")
    print()
    print("=" * 60)
    print()


if __name__ == "__main__":
    test_kpis()