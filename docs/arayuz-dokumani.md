# Arayüz Dokümanı

Durum: **taslak**. 22 Ekim Perşembe ders sonrası toplantıda teyit edilecek.

## Birimler

| Değişken | Birim | Açıklama |
| --- | --- | --- |
| Güç | kW | Matematiksel: 10³ W |
| Enerji | kWh | Güç × süre (1 kWh = 3.6 MJ) |
| Süre | saat | Ondalık saat: 18.5 = 18:30 |
| SOC | (0–1) | State of Charge, kismi dolum oranı |
| Gerilim | p.u. | Per-unit sistemi (baz = 1 p.u.) |
| Enerji maliyeti | TL/kWh | Türk Lirası per kilowatt-saat |

## Modül Arayüzleri

### 1. Veri Katmanı (`src/microgrid/data/`)

**Sorumlu:** YM-1

#### PV Modeli
```python
# Girdi: timestamp (datetime)
# Çıktı: dict with keys:
#   - pv_kw_per_kwp (kW/kWp): ışınım → üretim dönüşümü
#   - irradiance_w_m2 (W/m²)
#   - temp_c (°C), wind_m_s (m/s)

def get_pv_production(timestamp, config):
    """PVGIS verisinden saatlik üretim."""
    pass
```

#### Yük Modeli
```python
# Girdi: timestamp (datetime)
# Çıktı: dict with keys:
#   - fixed_load_kw (kW): bina, aydınlatma
#   - ev_demand_kw (kW): istasyon yükü

def get_load_profile(timestamp, config):
    """Sabit + EV yükleri."""
    pass
```

#### Tarife Modeli
```python
# Girdi: timestamp (datetime)
# Çıktı: dict with keys:
#   - price_tl_per_kwh (TL/kWh)
#   - period_name: "gece" | "gunduz" | "puant"

def get_tariff(timestamp, config):
    """Üç zamanlı tarife."""
    pass
```

---

### 2. Şarj İstasyonu (`src/microgrid/station/`)

**Sorumlu:** YM-2

#### Vehicle Sınıfı
```python
class Vehicle:
    def __init__(self, vehicle_id, battery_kwh,
                 arrival_hour, departure_hour,
                 arrival_soc, target_soc):
        self.vehicle_id = vehicle_id
        self.battery_kwh = battery_kwh
        self.arrival_hour = arrival_hour  # ondalık saat
        self.departure_hour = departure_hour
        self.arrival_soc = arrival_soc
        self.target_soc = target_soc
        
    def energy_required_kwh(self):
        """Hedef SOC'ye ulaşmak için gereken enerji."""
        return self.battery_kwh * (self.target_soc - self.arrival_soc)
    
    def charging_duration_hours(self, charge_power_kw):
        """Belirli güçte şarj süresi."""
        energy = self.energy_required_kwh()
        efficiency = 0.9  # DC şarj verimi
        return energy / (charge_power_kw * efficiency)
```

#### ChargingStation Sınıfı
```python
class ChargingUnit:
    def __init__(self, unit_id, kind, power_kw):
        self.unit_id = unit_id
        self.kind = kind  # "AC" veya "DC"
        self.power_kw = power_kw
        self.occupied_by = None  # Vehicle instance veya None
        self.scheduled_power_kw = 0.0

class ChargingStation:
    def __init__(self, config):
        self.units = []  # ChargingUnit listesi
        self.current_load_kw = 0.0
        
    def assign_vehicle(self, vehicle):
        """Aracı uygun üniteye ata."""
        pass
    
    def get_schedule(self, timestamp):
        """Her ünite için 15 dk'lık güç planı döner."""
        pass
```

#### CC-CV Şarj Profili
```python
# Girdi: vehicle, current_soc, max_power_kw
# Çıktı: charge_profile (dict of {time_step: power_kw})

def get_cc_cv_profile(vehicle, current_soc, max_power_kw):
    """CC-CV eğrisi: CC fazı (sabit güç), CV fazı (sabit voltaj)."""
    # CC: %0–80 SOC, max_power_kw sabit
    # CV: %80–100 SOC, güç azalarak hedef SOC'ye ulaşılır
    pass
```

---

### 3. Enerji Yönetim Sistemi (EMS) (`src/microgrid/ems/`)

**Sorumlu:** YM-3

#### EMS Strateji Arayüzü
```python
class BaseStrategy:
    """EMS strateji arayüzü."""
    
    def decide(self, state):
        """
        Girdi: dict with keys:
          - pv_kw (kW): anlık PV üretimi
          - fixed_load_kw (kW): sabit yük
          - ev_demand_kw (kW): şarj isteği
          - bess_soc: batarya SOC (0–1)
          - time_period: saat dilimi (gece/gunduz/puant)
        
        Çıktı: dict with keys:
          - grid_power_kw (kW): şebekeden alınan/verilen güç
          - bess_power_kw (kW): batarya gücü (+şarj, -deşarj)
          - ev_power_schedule: her ünite için güç (kW)
          - v2g_active: bool, V2G modunda mı
        """
        pass
```

#### BESS Modeli
```python
class Battery:
    def __init__(self, capacity_kwh, power_kw,
                 efficiency, soc_min, soc_max):
        self.capacity_kwh = capacity_kwh
        self.power_kw = power_kw  # max şarj/deşarj gücü
        self.efficiency = efficiency
        self.soc_min = soc_min
        self.soc_max = soc_max
    
    def update_soc(self, power_kw, duration_hours):
        """Güç ve süre verilince SOC'yu günceller."""
        pass
    
    def can_discharge(self, energy_kwh):
        """Belirli enerji deşarj edilebilir mi?"""
        pass
    
    def can_charge(self, energy_kwh):
        """Belirli enerji şarj edilebilir mi?"""
        pass
```

#### Optimizasyon (MILP)
```python
# Kullanılan kütüphane: PuLP veya Pyomo

def optimize_dispatch(pv_forecast, load_forecast,
                      vehicle_schedule, bess_params,
                      tariff_rates):
    """
    Amaç: 24 saatlik toplam maliyeti minimize et
    
    Karar değişkenleri:
      - grid_power[t]: saat t'nde şebekeden alınan güç
      - bess_charge[t], bess_discharge[t]: batarya işlemleri
      - ev_power[t][i]: saat t'nde ünite i'nin gücü
    
    Kısıtlar:
      - Güç dengesi: pv + bess_discharge + grid = load + ev_power + bess_charge
      - Batarya SOC sınırları
      - İstasyon güç limiti
      - EV şarj hedefleri
    
    Çıktı: dict of {variable_name: time_series_array}
    """
    pass
```

---

### 4. Grid Modülü (`src/microgrid/grid/`)

**Sorumlu:** EM-2 + YM-4

#### Pandapower Entegrasyonu
```python
import pandapower as pp

# Ağa yeni bileşenler eklemek için
def add_pv_bus(net, pv_kw, bus_id):
    """PV üreticiyi grid'e ekle."""
    pass

def add_bess(net, bess_kw, bus_id):
    """BESS'i grid'e ekle."""
    pass

def run_loadflow(net):
    """
    Çıktı: dict with keys:
      - bus_voltages (p.u.)
      - line_loadings (%)
      - transformer_loadings (%)
    """
    pass
```

---

### 5. Simülasyon Döngüsü (`src/microgrid/sim/`)

**Sorumlu:** YM-4

```python
def run_simulation(config, strategy):
    """
    24 saatlik zaman serisi simülasyonu.
    
    Zaman adımı: 15 dk (96 adım/gün)
    
    Her adımda:
      1. get_pv_production()
      2. get_load_profile()
      3. strategy.decide(state)
      4. ChargingStation.update_power_schedule()
      5. BESS.update_soc()
      6. Grid.run_loadflow() → sonuçları kaydet
    
    Çıktı: dict with keys:
      - timeseries: list of timestamps
      - pv_kw, load_kw, grid_power_kw, bess_soc,
        ev_charge_kwh, cost_tl, voltage_min_pu, etc.
    """
    pass
```

---

### 6. Simulink → Python Entegrasyonu

```python
# CSV formatı: simulink/outputs/*.csv

def load_simulink_csv(filepath):
    """
    CSV sütunları:
      - time (s): simülasyon süresi
      - pv_power (kW)
      - load_power (kW)
      - grid_power (kW)
      - bess_soc (-)
      - bus_voltage (p.u.)
      
    Dönen format: pandas.DataFrame
    """
    pass

def align_time_series(python_ts, simulink_ts):
    """
    Python (15 dk adım) ve Simulink (saniye adım)
    verilerini ortak zamana getir.
    
    Python verisi Simulink'e göre:
      - interpolasyon ile saniyelik çözünürlüğe yükselt
      - veya Simulink verisini 15 dk'lık binlere böl
    """
    pass
```

---

## Hata Kontrolleri ve Validasyon

```python
# Her modül için common checks:

def validate_power_balance(pv, load, grid, bess):
    """Güç dengesi: pv + bess_discharge = load + grid + bess_charge"""
    imbalance = abs((pv + bess) - (load + grid))
    if imbalance > 0.01:  # %1 tolerans
        raise ValueError(f"Güç dengesi hatası: {imbalance} kW")
```

---

## Sonraki Adımlar

- EM-2 ile pandapower ağı parametrelerini onayla
- EM-1 ile Simulink → CSV formatını sabitle
- Hafta 3'te her modül tek başına test edilecek
