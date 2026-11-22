# EV ŞARJ İSTASYONU SINIF TASARIMI VE UML SINIF DİYAGRAMI
**Ders:** Akıllı Şebekeler Projesi  
**Rol:** YM-2 (Şarj İstasyonu Modeli)  
**Aşama:** Hafta 2 (Tasarım: Şema, Boyutlar ve Modül Arayüzleri)  

---

## 🖼️ Görsel Şema Çıktıları
- **Mermaid Şema Resmi (PNG):** [docs/mermaid-diagram-2026-10-16-140115.png](file:///Users/sude/Desktop/ak%C4%B1ll%C4%B1%20sebekeler%20proje/docs/mermaid-diagram-2026-10-16-140115.png) *(Mermaid Live Editor'dan alınan görsel şema)*
- **Alternatif UML Kutu Şeması (PNG):** [docs/sinif_diyagrami.png](file:///Users/sude/Desktop/ak%C4%B1ll%C4%B1%20sebekeler%20proje/docs/sinif_diyagrami.png) *(Klasik mühendislik UML diyagramı)*
- **İnteraktif Web Önizleme & SVG İndirici:** [docs/diagram_preview.html](file:///Users/sude/Desktop/ak%C4%B1ll%C4%B1%20sebekeler%20proje/docs/diagram_preview.html) *(Tarayıcınızda açıp tek tıkla vektörel SVG olarak indirebilirsiniz)*

---

## 🏛️ 1. Mimari Tasarım Prensipleri

Nesne yönelimli tasarımımız 3 temel katmandan ve sınıftan oluşur:

1. **`ElectricVehicle` (Araç Modeli):**
   - Tek bir elektrikli aracın fiziksel batarya özelliklerini, anlık şarj durumunu ($SOC$), şarj gereksinimini ve Li-ion CC-CV eğrisine göre maksimum çekebileceği gücü yönetir.
   - V2G (şebekeye enerji geri besleme) yeteneğini ve güvenlik eşiğini barındırır.
2. **`ChargingUnit` (Soket / Ünite Modeli):**
   - İstasyondaki her bir fiziksel şarj portunu (AC Tip-2 veya DC CCS2) temsil eder.
   - Soketin maksimum/minimum güç sınırlarını, anlık güç atamasını ve soket durumunu (`AVAILABLE`, `CHARGING`, `IDLE`, `DISCHARGING`) yönetir.
3. **`ChargingStation` (İstasyon Yönetim Modeli):**
   - Tüm şarj soketlerini bünyesinde toplar.
   - Yeni gelen araçları uygun boş soketlere bağlar (`plug_in_vehicle`), süresi dolan araçları ayırır (`auto_handle_departures`).
   - EMS'e bağlı araçların listesini döner (`bagli_araclar`), EMS güç atamalarını dağıtır (`apply_power_allocations`).
   - pandapower için anlık toplam istasyon yükünü (`get_total_power_kw`) ve trafo aşım durumunu hesaplar.

---

## 📊 2. UML Sınıf Diyagramı (Class Diagram)

```mermaid
classDiagram
    direction TB

    class UnitStatus {
        <<enumeration>>
        AVAILABLE
        OCCUPIED_CHARGING
        OCCUPIED_IDLE
        OCCUPIED_DISCHARGING
    }

    class ElectricVehicle {
        +str vehicle_id
        +str model_name
        +float battery_capacity_kwh
        +float initial_soc
        +float current_soc
        +float target_soc
        +float arrival_time
        +float departure_time
        +float max_ac_power_kw
        +float max_dc_power_kw
        +bool v2g_capable
        +bool is_connected
        +str connected_unit_id
        +float total_energy_charged_kwh
        +float total_energy_discharged_kwh
        +energy_needed_kwh : float
        +remaining_parking_duration_hours : float
        +is_fully_charged() bool
        +get_max_charging_power(unit_type: str, unit_max_kw: float) float
        +charge(power_kw: float, dt_hours: float, efficiency: float) float
        +discharge(power_kw: float, dt_hours: float, efficiency: float) float
        +to_dict() dict
    }

    class ChargingUnit {
        +str unit_id
        +str unit_type
        +float max_power_kw
        +float min_power_kw
        +float current_power_kw
        +float total_energy_delivered_kwh
        +UnitStatus status
        +ElectricVehicle connected_vehicle
        +is_occupied : bool
        +connect_vehicle(vehicle: ElectricVehicle) bool
        +disconnect_vehicle() ElectricVehicle
        +get_max_deliverable_power() float
        +set_power(power_kw: float) float
        +step(dt_hours: float) float
        +to_dict() dict
    }

    class ChargingStation {
        +str station_id
        +str name
        +float transformer_limit_kw
        +Dict~str, ChargingUnit~ units
        +float total_energy_delivered_kwh
        +int completed_sessions_count
        +list overload_history
        +total_capacity_kw : float
        +active_connected_vehicles_count : int
        +get_unit(unit_id: str) ChargingUnit
        +get_available_units(unit_type: str) List~ChargingUnit~
        +plug_in_vehicle(vehicle: ElectricVehicle, preferred_type: str) str
        +unplug_vehicle(unit_id: str) ElectricVehicle
        +auto_handle_departures(current_time: float) List~ElectricVehicle~
        +bagli_araclar(current_time: float) List~dict~
        +apply_power_allocations(allocations: Dict) void
        +get_total_power_kw() float
        +is_transformer_overloaded() bool
        +step(dt_hours: float, current_time: float) dict
        +get_dashboard_state() dict
    }

    class DemandModel {
        +int random_seed
        +generate_fleet(total_vehicles: int, profile: str) List~ElectricVehicle~
        -_sample_vehicle_spec() dict
    }

    ChargingStation "1" *-- "1..*" ChargingUnit : barındırır
    ChargingUnit "1" o-- "0..1" ElectricVehicle : şarj eder
    ChargingUnit ..> UnitStatus : durum takibi
    DemandModel ..> ElectricVehicle : üretir
```

---

## ⚙️ 3. Sınıf Alanları ve Metot Tanımları

### `ElectricVehicle`
- **`battery_capacity_kwh`**: Nominal batarya kapasitesi (kWh).
- **`current_soc`**: Anlık şarj durumu ($0.0 \le \text{SOC} \le 1.0$).
- **`target_soc`**: Kullanıcının ayrılırken beklediği hedef şarj ($0.85 - 1.00$).
- **`get_max_charging_power(unit_type, unit_max_kw)`**: 
  - Araç dahili OBC limiti (`max_ac_power_kw`), soket limiti (`unit_max_kw`) ve Li-ion CC-CV eğrisinin ortak kesişimindeki anlık çekilebilir tavan gücü hesaplar.
- **`charge(power_kw, dt_hours, efficiency)`**:
  - Bataryaya $\Delta E = P \times \Delta t \times \eta$ kadar net enerji aktarır ve SOC'yi günceller.

### `ChargingUnit`
- **`unit_id`**: Benzersiz soket kodu (`AC-01` ... `AC-08`, `DC-01`, `DC-02`).
- **`unit_type`**: `AC` (22 kW Tip-2) veya `DC` (50 kW CCS2).
- **`set_power(power_kw)`**:
  - EMS'ten gelen komutu soketin ve bağlı aracın fiziksel sınırlarıyla sınırlar. Negatif güç gelirse ve araç V2G yetenekliyse deşarj moduna geçer.
- **`step(dt_hours)`**:
  - Zaman adımını ilerleterek bağlı araca şarj uygular ve harcanan enerjiyi toplar.

### `ChargingStation`
- **`transformer_limit_kw`**: Şebeke / trafo bağlantı limiti (180 kW).
- **`bagli_araclar(current_time)`**:
  - EMS optimizasyon döngüsünün girdi alabilmesi için bağlı araçların aciliyet, SOC ve enerji gereksinimlerini liste olarak üretir.
- **`apply_power_allocations(allocations)`**:
  - EMS karar sözlüğünü soketlere paylaştırır.
- **`get_total_power_kw()`**:
  - Tüm soketlerin çektiği gücü toplayarak pandapower için anlık yük çıktısı verir.
