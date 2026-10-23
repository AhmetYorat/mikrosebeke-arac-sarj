"""V2G (Vehicle-to-Grid) ve islanded mode testleri (PRD v2 - Senaryo 6).

Hafta 3: V2G optimizasyonu ve ada modu desteği
"""
import sys
sys.path.insert(0, '/Users/berke/Developer/mikrosebeke-arac-sarj/src')

import numpy as np
import pytest

from microgrid.ems.optimizer import EMSOptimizer, OptimizationConfig
from microgrid.ems.v2g import V2GStrategy, VehicleState, V2GOptimizer, V2GOption
from microgrid.ems.islanded import IslandedModeManager, IslandedConfig


class TestV2GStrategy:
    """V2G strateji testleri."""
    
    def test_v2g_option_defaults(self):
        """V2G opsiyonu varsayılan değerleri kontrol et."""
        option = V2GOption()
        
        assert option.v2g_soc_threshold == 0.85
        assert option.max_discharge_power_kw == 50.0
    
    def test_vehicle_state_creation(self):
        """Araç durumu oluşturulabilir mi kontrol et."""
        vehicle = VehicleState(
            vehicle_id="EV001",
            arrival_time=18.0,
            departure_time=22.0,
            soc_start=0.90,
            energy_required_kwh=10.0,
            soc_target=0.85,
            max_power_kw=50.0
        )
        
        assert vehicle.vehicle_id == "EV001"
        assert vehicle.soc_start == 0.90
    
    def test_v2g_strategy_add_vehicle(self):
        """Araç V2G stratejisine eklenebilir mi."""
        strategy = V2GStrategy()
        
        vehicle = VehicleState(
            vehicle_id="EV001",
            arrival_time=18.0,
            departure_time=22.0,
            soc_start=0.90,
            energy_required_kwh=10.0,
            soc_target=0.85,
            max_power_kw=50.0
        )
        
        strategy.add_vehicle(vehicle)
        
        assert "EV001" in strategy.connected_vehicles
    
    def test_v2g_high_soc_discharge(self):
        """Yüksek SOC'da deşarj yapılmalı mı."""
        option = V2GOption(v2g_soc_threshold=0.85)
        strategy = V2GStrategy(option)
        
        vehicle = VehicleState(
            vehicle_id="EV001",
            arrival_time=18.0,
            departure_time=22.0,
            soc_start=0.90,  # Yüksek SOC - deşarj yapmalı
            energy_required_kwh=10.0,
            soc_target=0.85,
            max_power_kw=50.0
        )
        
        strategy.add_vehicle(vehicle)
        
        # Pahalı saatte (puant) ve yüksek grid talebi
        discharge = strategy.get_vehicle_discharge_power(
            "EV001", current_time=19.0, grid_price=6.17, grid_demand_high=True
        )
        
        assert discharge > 0
    
    def test_v2g_low_soc_no_discharge(self):
        """Düşük SOC'da deşarj yapılmamalı."""
        option = V2GOption(v2g_soc_threshold=0.85)
        strategy = V2GStrategy(option)
        
        vehicle = VehicleState(
            vehicle_id="EV001",
            arrival_time=18.0,
            departure_time=22.0,
            soc_start=0.75,  # Düşük SOC - deşarj yapmayacak
            energy_required_kwh=25.0,
            soc_target=0.95,
            max_power_kw=50.0
        )
        
        strategy.add_vehicle(vehicle)
        
        discharge = strategy.get_vehicle_discharge_power(
            "EV001", current_time=19.0, grid_price=6.17, grid_demand_high=True
        )
        
        assert discharge == 0.0


class TestV2GOptimizer:
    """V2G optimizasyon testleri."""
    
    def test_v2g_optimize_schedule(self):
        """V2G şarj/deşarj planı optimize edilebilir mi."""
        option = V2GOption(v2g_soc_threshold=0.85)
        optimizer = V2GOptimizer(option)
        
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
        ]
        
        hours = np.arange(96) / 4.0
        prices = np.where(
            (hours >= 17) & (hours < 20),
            6.17,
            np.where((hours >= 6) & (hours < 17), 4.38, 2.94)
        )
        
        result = optimizer.optimize_v2g_schedule(vehicles, hours, prices)
        
        assert 'v2g_discharge' in result
        assert 'total_energy_discharged' in result
        assert result['total_energy_discharged'] >= 0
    
    def test_v2g_benefit_calculation(self):
        """V2G kazanç doğru hesaplanmalı mı."""
        option = V2GOption(v2g_soc_threshold=0.85)
        optimizer = V2GOptimizer(option)
        
        vehicles = [
            VehicleState(
                vehicle_id="EV001",
                arrival_time=18.0,
                departure_time=22.0,
                soc_start=0.90,
                energy_required_kwh=15.0,
                soc_target=0.85,
                max_power_kw=50.0
            ),
        ]
        
        hours = np.arange(96) / 4.0
        prices = np.where(
            (hours >= 17) & (hours < 20),
            6.17,
            np.where((hours >= 6) & (hours < 17), 4.38, 2.94)
        )
        
        result = optimizer.optimize_v2g_schedule(vehicles, hours, prices)
        
        # Kazanç pozitif olmalı (pahalı saatte discharge)
        assert result['v2g_benefit_tl'] >= 0


class TestIslandedMode:
    """Ada modu testleri."""
    
    def test_islanded_config_defaults(self):
        """Islanded config varsayılan değerleri kontrol et."""
        config = IslandedConfig()
        
        assert config.freq_min == 0.95
        assert config.freq_max == 1.05
    
    def test_add_loads(self):
        """Yükler eklenebilir mi."""
        manager = IslandedModeManager()
        
        manager.add_load("Lighting", 15.0, is_critical=True)
        manager.add_load("EV_Charging", 40.0, is_critical=False)
        
        assert manager.total_load_kw == 55.0
    
    def test_grid_disconnect(self):
        """Grid bağlantısı kesilebilir mi."""
        manager = IslandedModeManager()
        manager.set_grid_status(False)
        
        assert not manager.grid_connected
    
    def test_power_balance(self):
        """Güç dengesi hesaplanabilir mi."""
        config = IslandedConfig()
        manager = IslandedModeManager(config)
        
        # Yükleme
        manager.add_load("Critical_Load", 20.0, is_critical=True)
        manager.add_load("NonCritical_Load", 30.0, is_critical=False)
        
        # Güç kaynakları
        manager.set_pv_power(25.0)
        manager.set_bess_power(-30.0)  # Deşarj (negatif)
        manager.set_v2g_power(15.0)
        
        # Toplam kullanılabilir güç
        available = manager.get_available_power()
        assert available == 70.0  # 25 + 30 + 15
        
        # Load shedding hesapla
        manager.set_grid_status(False)
        shed_loads = manager.calculate_load_shedding()
        
        # Eksik güç: 50 - 70 = negatif (yeterli)
        assert manager.total_load_kw == 50.0
    
    def test_islanding_time_estimate(self):
        """Ada modunda kalış süresi tahmini yapılabilir mi."""
        manager = IslandedModeManager()
        
        # Yükleme
        manager.add_load("Critical_Load", 10.0, is_critical=True)
        manager.add_load("EV_Charging", 40.0, is_critical=False)
        
        # BESS ile güç sağlayan
        manager.set_bess_power(-50.0)  # Deşarj
        
        # Grid bağlantısı kesiliyor
        manager.set_grid_status(False)
        
        # Tahmini süre
        est_time = manager.estimate_islanding_time()
        
        assert est_time > 0 and est_time < float('inf')


class TestEMSOptimizerWithV2G:
    """EMS optimizer V2G entegrasyon testleri."""
    
    def test_optimizer_config_with_v2g(self):
        """V2G parametreleri config'e eklenebilir mi."""
        config = OptimizationConfig(
            bess_capacity_kwh=200,
            max_v2g_power_kw=50.0,
            v2g_soc_threshold=0.85
        )
        
        assert config.max_v2g_power_kw == 50.0
        assert config.v2g_soc_threshold == 0.85
    
    def test_v2g_in_optimization(self):
        """V2G optimizasyona dahil edilebilir mi."""
        config = OptimizationConfig(
            bess_capacity_kwh=200,
            bess_max_power_kw=100,
            max_v2g_power_kw=50.0,
            initial_soc=0.8
        )
        
        # Basit test verisi
        n_periods = 96
        load = np.ones(n_periods) * 50
        pv = np.zeros(n_periods)
        prices = np.ones(n_periods) * 6.17  # Yüksek fiyatlar
        
        optimizer = EMSOptimizer(config)
        
        # Optimizasyon çalıştırılabilir mi?
        result = optimizer.optimize(load, pv, prices)
        
        assert 'status' in result
        assert result['status'] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
