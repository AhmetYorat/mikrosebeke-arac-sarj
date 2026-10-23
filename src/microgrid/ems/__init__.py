"""EMS ve optimizasyon (YM-3): batarya yönetimi, kural tabanlı akıllı şarj, MILP (PuLP), V2G.

Hafta 1: Araştırma - akıllı şarj ve EMS yaklaşımları
Hafta 2: Kural tabanlı algoritma ve EMS arayüzü tanımı
Hafta 3: V2G, ada modu ve detaylı şarj istasyonu modellemesi

PRD v2 - Senaryolar:
1. Temel durum: EV yok, sadece PV + yük + şebeke
2. Kontrolsüz şarj: Araç geldiği an tam güçle şarja girer
3. Akıllı şarj (kural tabanlı): SOC eşikleri + tarife
4. Akıllı şarj + batarya: Batarya pik saatlerde istasyonu destekler
5. Optimizasyonlu EMS: Maliyeti minimize eden MILP modeli
6. V2G: Yüksek SOC'li araçlar akşam pikinde şebekeye enerji verir

Modül yapısı:
- __init__.py: Bu dosya, modül açıklaması ve kullanım örnekleri
- strategy.py: Kural tabanlı akıllı şarj stratejileri (tariff, SOC, hybrid)
- optimizer.py: MILP tabanlı optimizasyon (PuLP) - temel + V2G
- bess.py: Batarya enerji depolama sistemi (BESS) modeli
- kpi.py: EMS performans KPI'ları
- charging_station.py: Detaylı şarj istasyonu modeli (AC/DC üniteler)
- v2g.py: Vehicle-to-Grid stratejileri ve optimizasyonu
- islanded.py: Ada (islanded) mod yönetimi

Kullanım:
    from microgrid.ems import strategy, bess, optimizer
    from microgrid.ems.charging_station import ChargingStation
    from microgrid.ems.v2g import V2GStrategy
    
    # Kural tabanlı strateji
    charge_power = strategy.rule_based(charge_demand, tariff_price, soc)
    
    # BESS modeli
    bess_model = bess.BESS(capacity_kwh=200, power_kw=100)
    bess_model.step(charge_power, efficiency=0.95)
    
    # Detaylı şarj istasyonu
    station = ChargingStation(num_ac_units=8, num_dc_units=2, max_power_kw=100)
    station.add_vehicle(vehicle_id="EV001", arrival_time=18.0, soc_start=0.2)
    
    # V2G stratejisi
    v2g_strategy = V2GStrategy(soc_threshold=0.85)
    discharge_power = v2g_strategy.get_discharge_power(soc, max_power=50)
"""

from .strategy import rule_based, HybridStrategy, ChargeStrategyConfig
from .bess import BESS, BESSConfig

# PRD v2 yeni modülleri
from .charging_station import ChargingStation, ChargingUnitConfig
from .v2g import V2GStrategy, V2GOption
from .islanded import IslandedModeManager

__all__ = [
    'rule_based',
    'HybridStrategy', 
    'ChargeStrategyConfig',
    'BESS',
    'BESSConfig',
    # PRD v2 yeni modüller
    'ChargingStation',
    'ChargingUnitConfig',
    'V2GStrategy',
    'V2GOption',
    'IslandedModeManager',
]
