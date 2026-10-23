"""MILP tabanlı EMS optimizasyonu (YM-3, Hafta 2).

Bu modül EM-3 tarafından geliştirilmektedir.
Optimizasyon yaklaşımı: Mixed Integer Linear Programming (PuLP)

Amaç: Toplam energetic maliyeti minimize et
Kısıtlar:
- Batarya dinamikleri (SOC balansı)
- Güç dengesi
- SOC limitleri
- Şarj/deşarj hız限制leri

Optimizasyon modeli:
    min: Σ(t) price[t] * grid_power[t]
    
    subject to:
        SOC[t+1] = SOC[t] + (charge[t]*η_c - discharge[t]/η_d) * Δt
        SOC_min ≤ SOC[t] ≤ SOC_max
        0 ≤ charge[t] ≤ max_power
        0 ≤ discharge[t] ≤ max_power
        grid_power[t] = load[t] + charge[t] - pv[t] + discharge[t]
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pulp


@dataclass
class OptimizationConfig:
    """Optimizasyon yapılandırması."""
    
    # Zaman parametreleri
    time_step_hours: float = 0.25   # 15 dk = 0.25 saat
    horizon_hours: int = 24         # Optimizasyon periyodu
    
    # BESS parametreleri
    bess_capacity_kwh: float = 200.0
    bess_max_power_kw: float = 100.0
    bess_soc_min: float = 0.1
    bess_soc_max: float = 0.95
    bess_charge_eff: float = 0.95
    bess_discharge_eff: float = 0.92
    
    # V2G parametreleri
    max_v2g_power_kw: float = 50.0      # Maksimum V2G deşarj gücü
    v2g_soc_threshold: float = 0.85     # V2G başlangıç SOC eşiği
    v2g_min_soc: float = 0.40           # Minimum V2G SOC
    v2g_efficiency: float = 0.92        # V2G verimlilik
    
    # Başlangıç SOC
    initial_soc: float = 0.5


class EMSOptimizer:
    """EMS için MILP optimizasyon modülü.
    
    Özellikler:
    - Günlük optimizasyon (24 saatlik horizon)
    - Tarife tabanlı maliyet optimizasyonu
    - Batarya寿命 koruma constraints
    - Çıkarım能力 constraint'leri
    
    Kullanım:
        # Verileri hazırla
        load = np.array([50, 60, 70, ...])  # Her 15 dk için
        pv = np.array([0, 10, 80, ...])
        prices = np.array([2.94, 2.94, 4.38, ...])
        
        # Optimizasyonu çalıştır
        opt = EMSOptimizer(config)
        result = opt.optimize(load, pv, prices)
        
        # Sonuçları al
        print(f"Optimal grid power: {result['grid_power']}")
        print(f"Total cost: {result['total_cost']} TL")
    """
    
    def __init__(self, config: Optional[OptimizationConfig] = None):
        """EMS Optimizasyon modülünü başlat."""
        self.config = config or OptimizationConfig()
        
        # Optimizasyon değişkenleri
        self.problem: Optional[pulp.LpProblem] = None
        self.variables: dict = {}
        
        # Sonuçlar
        self.status: str = "not_run"
        self.result_data: dict = {}
    
    def _create_problem(self) -> None:
        """MILP problemini oluştur."""
        # Problem başlat
        self.problem = pulp.LpProblem("EMS_Optimization", pulp.LpMinimize)
        
        # Zaman indeksi
        n_periods = int(self.config.horizon_hours / self.config.time_step_hours)
        
        # Karar değişkenleri (sürekli, non-negative)
        self.variables['charge'] = pulp.LpVariable.dicts(
            "charge", range(n_periods), lowBound=0, upBound=self.config.bess_max_power_kw
        )
        
        self.variables['discharge'] = pulp.LpVariable.dicts(
            "discharge", range(n_periods), lowBound=0, upBound=self.config.bess_max_power_kw
        )
        
        self.variables['grid_power'] = pulp.LpVariable.dicts(
            "grid_power", range(n_periods), lowBound=None  # Negatif olabilir (geri besleme)
        )
        
        self.variables['soc'] = pulp.LpVariable.dicts(
            "soc", range(n_periods + 1), lowBound=self.config.bess_soc_min,
            upBound=self.config.bess_soc_max
        )
    
    def _add_constraints(self, load: np.ndarray, pv: np.ndarray) -> None:
        """Problem constraint'lerini ekle."""
        n_periods = len(load)
        
        # SOC balans constraints
        for t in range(n_periods):
            self.problem += (
                self.variables['soc'][t + 1] ==
                self.variables['soc'][t] +
                (self.variables['charge'][t] * self.config.bess_charge_eff -
                 self.variables['discharge'][t] / self.config.bess_discharge_eff) *
                self.config.time_step_hours / self.config.bess_capacity_kwh,
                f"soc_balance_{t}"
            )
        
        # Başlangıç SOC constraint
        self.problem += (
            self.variables['soc'][0] == self.config.initial_soc,
            "initial_soc"
        )
        
        # Güç dengesi constraints
        for t in range(n_periods):
            self.problem += (
                self.variables['grid_power'][t] ==
                load[t] + self.variables['charge'][t] - pv[t] + self.variables['discharge'][t],
                f"power_balance_{t}"
            )
        
        # Batarya power limit constraints (zaten değişken tanımlamada var)
        for t in range(n_periods):
            self.problem += (
                self.variables['charge'][t] <= self.config.bess_max_power_kw,
                f"max_charge_{t}"
            )
            self.problem += (
                self.variables['discharge'][t] <= self.config.bess_max_power_kw,
                f"max_discharge_{t}"
            )
        
        # V2G constraints -_vehicle can discharge to grid during high price periods
        max_v2g_power = self.config.max_v2g_power_kw
        if max_v2g_power > 0:
            for t in range(n_periods):
                # V2G discharge cannot exceed vehicle SOC threshold
                self.problem += (
                    self.variables['soc'][t] >= self.config.v2g_min_soc,
                    f"v2g_min_soc_{t}"
                )
    
    def _set_objective(self, prices: np.ndarray) -> None:
        """Optimizasyon objektif fonksiyonunu ayarla."""
        n_periods = len(prices)
        
        # Toplam maliyeti minimize et
        total_cost = pulp.lpSum(
            prices[t] * self.variables['grid_power'][t] * self.config.time_step_hours
            for t in range(n_periods)
        )
        
        self.problem += total_cost, "Total_Energy_Cost"
    
    def optimize(self, load: np.ndarray, pv: np.ndarray,
                 prices: np.ndarray) -> dict:
        """EMS optimizasyonunu çalıştır.
        
        Args:
            load: Yük gücü zaman serisi (kW)
            pv: PV üretim zaman serisi (kW)
            prices: Elektrik fiyatı zaman serisi (TL/kWh)
        
        Returns:
            dict: Optimizasyon sonuçları
        """
        # Girdileri kontrol et
        n_periods = int(self.config.horizon_hours / self.config.time_step_hours)
        
        if len(load) != n_periods or len(pv) != n_periods or len(prices) != n_periods:
            raise ValueError(
                f"Input arrays must have length {n_periods} "
                f"(horizon={self.config.horizon_hours}h, step={self.config.time_step_hours}h)"
            )
        
        # Problem oluştur
        self._create_problem()
        
        # Constraint'leri ekle
        self._add_constraints(load, pv)
        
        # Objektif fonksiyonu ayarla
        self._set_objective(prices)
        
        # Çözümle
        self.status = "solving"
        solver = pulp.PULP_CBC_CMD(msg=False)
        
        try:
            self.problem.solve(solver)
            self.status = pulp.LpStatus[self.problem.status]
        except Exception as e:
            self.status = f"error: {str(e)}"
        
        # Sonuçları parse et
        if self.status == "Optimal":
            self._extract_results(n_periods)
        
        return self.result_data
    
    def _extract_results(self, n_periods: int) -> None:
        """Optimizasyon sonuçlarını parse et."""
        self.result_data = {
            'status': self.status,
            'total_cost': pulp.value(self.problem.objective),
            'optimization_time': self.problem.solutionTime,
            
            # Zaman serileri
            'grid_power': np.array([
                self.variables['grid_power'][t].varValue for t in range(n_periods)
            ]),
            'charge': np.array([
                self.variables['charge'][t].varValue for t in range(n_periods)
            ]),
            'discharge': np.array([
                self.variables['discharge'][t].varValue for t in range(n_periods)
            ]),
            'soc': np.array([
                self.variables['soc'][t].varValue for t in range(n_periods + 1)
            ]),
            
            # KPI'lar
            'bess_throughput': np.sum(
                self.result_data.get('charge', 0) + self.result_data.get('discharge', 0)
            ) * self.config.time_step_hours,
            'self_sufficiency': np.sum(
                np.maximum(0, pv - load)
            ) / np.sum(load) if 'pv' in dir() and 'load' in dir() else 0,
        }
    
    def get_schedule(self) -> dict:
        """Optimizasyon sonucu elde edilen şarj planını döndür."""
        if self.status != "Optimal":
            raise RuntimeError("No optimal solution available.")
        
        return {
            'grid_power': self.result_data['grid_power'],
            'bess_charge': self.result_data['charge'],
            'bess_discharge': self.result_data['discharge'],
            'bess_soc': self.result_data['soc'][:-1],  # Son SOC değerini çıkar
            'total_cost': self.result_data['total_cost'],
        }


def test_optimizer():
    """EMS optimizasyonunu test et."""
    print("=" * 60)
    print("EMS MILP OPTİMİZASYONU - TEST")
    print("=" * 60)
    
    # Veri oluştur
    n_periods = 96  # 24 saat / 15 dk adım
    
    import numpy as np
    hours = np.arange(n_periods) / 4  # Her adım 15 dk
    
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
    
    # Tarife profili (3 periyot)
    prices = np.where(
        (hours >= 0) & (hours < 6),
        2.94,  # Gece
        np.where(
            (hours >= 6) & (hours < 17),
            4.38,  # Gündüz
            np.where(
                (hours >= 17) & (hours < 20),
                6.17,  # Puant
                2.94   # Gece tekrar
            )
        )
    )
    
    print("Veri Özeti:")
    print(f"  Periyot: {n_periods} adım (15 dk aralıklar, 24 saat)")
    print(f"  Yük: {load.mean():.1f} kW ortalama, {load.max():.1f} kW maksimum")
    print(f"  PV: {pv.mean():.1f} kW ortalama, {pv.max():.1f} kW maksimum")
    print(f"  Fiyat: {prices.mean():.2f} TL/kWh ortalama")
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
        print()
        
        #compare with rule-based
        from .strategy import HybridStrategy, ChargeStrategyConfig
        
        strategy = HybridStrategy(ChargeStrategyConfig())
        
        rule_based_cost = 0
        soc = opt_config.initial_soc
        bess_charge = result['charge']
        bess_discharge = result['discharge']
        
        for t in range(n_periods):
            # Rule-based stratejisi ile şarj/deşarj
            hour = hours[t]
            period = "gece" if prices[t] < 3.5 else ("puant" if prices[t] > 5.0 else "gunduz")
            rule_power = strategy.get_charge_power(hour, opt_config.bess_max_power_kw, period, soc)
            
            # SOC güncelle
            if rule_power > 0:
                soc = soc + (rule_power * opt_config.bess_charge_eff) * \
                      opt_config.time_step_hours / opt_config.bess_capacity_kwh
            elif bess_discharge[t] > 0:
                soc = soc - (bess_discharge[t] / opt_config.bess_discharge_eff) * \
                      opt_config.time_step_hours / opt_config.bess_capacity_kwh
            
            soc = max(opt_config.bess_soc_min, min(soc, opt_config.bess_soc_max))
            
            # Grid power hesapla
            grid_power = load[t] + max(0, rule_power) - pv[t] + max(0, bess_discharge[t])
            rule_based_cost += grid_power * prices[t] * opt_config.time_step_hours
        
        print(f"  Kural Tabanlı Maliyet: {rule_based_cost:.2f} TL")
        print(f"  MILP ile Tasarruf: {rule_based_cost - result['total_cost']:.2f} TL")
        print()
        
        # SOC profili
        print("SOC Profili:")
        print(f"  Başlangıç: {result['soc'][0]:.0%}")
        print(f"  Minimum: {min(result['soc']):.0%}")
        print(f"  Maksimum: {max(result['soc']):.0%}")
        print(f"  Bitiş: {result['soc'][-1]:.0%}")
    
    print()
    print("=" * 60)
    print()


if __name__ == "__main__":
    test_optimizer()