# Şarj istasyonu sınıf tasarımı (YM-2)

Durum: **Hafta 9 son hâli.** Hafta 2 tasarımı (`docs/raporlar/sinif-diyagrami.png`) aynı dört sınıfla başladı;
Hafta 3–8'de sözleşmedeki `requests/apply` arayüzüne göre yeniden düzenlendi. Kod: `src/microgrid/station/`.

```mermaid
classDiagram
    direction LR
    class ChargingStation {
        +units: dict~str, ChargingUnit~
        +vehicles: list~ElectricVehicle~
        +queue: list~ElectricVehicle~
        +n_chargers: int
        +requests(ctx) list~VehicleRequest~
        +apply(ctx, ev_kw) dict~str, float~
        +sessions() DataFrame
        +planned_sessions() DataFrame
    }
    class ChargingUnit {
        +charger_id: str
        +kind: AC | DC
        +power_kw: float
        +vehicle: ElectricVehicle
        +connect(vehicle, ts)
        +disconnect() ElectricVehicle
        +max_charge_kw(threshold, min_fraction) float
        +max_discharge_kw(ts, dt_h, min_soc, eff) float
    }
    class ElectricVehicle {
        +vehicle_id, model_name: str
        +battery_kwh, soc, soc_arrival, target_soc: float
        +arrival, departure: Timestamp
        +max_ac_kw, max_dc_kw: float
        +v2g_capable: bool
        +energy_needed_kwh: float
        +reached_target: bool
        +max_charge_kw(kind, unit_kw, threshold, min_fraction) float
        +max_discharge_kw(ts, dt_h, unit_kw, p_charge_kw, min_soc, eff) float
        +charge(p_kw, dt_h, eff)
        +discharge(p_kw, dt_h, eff)
    }
    class DemandModel {
        +generate_fleet(start) list~ElectricVehicle~
    }
    ChargingStation "1" *-- "10" ChargingUnit
    ChargingStation "1" o-- "*" ElectricVehicle
    ChargingUnit "1" --> "0..1" ElectricVehicle : bağlı araç
    ChargingStation ..> DemandModel : filo üretir
```

## Sorumluluklar

| Sınıf / modül | Ne yapar |
| --- | --- |
| `ElectricVehicle` (`vehicle.py`) | Aracın kimliği, donanımı (batarya, OBC, V2G) ve durumu (SOC, bağlı olduğu ünite, aldığı/verdiği enerji). Şarj fiziği: `cc_cv_limit`, V2G garantileri. |
| `ChargingUnit` (`charging_unit.py`) | Tek AC/DC ünite; bağlı aracın o üniteden çekebileceği/verebileceği sınırı hesaplar. |
| `ChargingStation` (`charging_station.py`) | Döngünün gördüğü tek nesne. Her adım: ayrılanlar → gelenler sıraya → nöbetleşe şarj → boş üniteye atama (önce AC) → `VehicleRequest` listesi. `apply` güçleri kırpar ve uygular. |
| `DemandModel` (`demand_model.py`) | Config'teki dağılımlar ve araç kataloğundan bir günlük filo. |
| `strategies.py` | `uncontrolled`, `by_departure` (EMS için güç dağıtım kuralları), `satisfaction` (kullanıcı memnuniyeti KPI'ı). |
| `analysis.py` | Araç sayısı–tepe yük analizi, istasyonun kritik anı. |

## Hafta 2 tasarımından farklar

| Hafta 2 | Son hâl | Neden |
| --- | --- | --- |
| `bagli_araclar(saat)` → sözlük listesi | `requests(ctx)` → `VehicleRequest` | Ekip sözleşmesi (`docs/arayuz-sozlesmesi.md`) |
| `apply_power_allocations(dict)` → `None` | `apply(ctx, ev_kw)` → uygulanan güç | Döngü gerçekte uygulanan gücü kaydeder |
| Saatler ondalık (17.5) | `pd.Timestamp` (Europe/Istanbul) | Gece yarısını geçen kalışlar |
| `AC-01` | `AC1` | Sözleşmedeki biçim |
| Parametreler kodda | `config/default.yaml` | Ortak kural |
| `get_total_power_kw`, `get_dashboard_state` | `SimResult.steps.ev_kw`, `SimResult.station` | Toplam güç ve ünite görünümünü döngü kaydediyor |
| `UnitStatus`, ünite taban gücü (1,4 kW) | kaldırıldı | EMS'i karmaşıklaştırıyordu; sonuçlara etkisi yok |
| — | Sıra, nöbetleşe şarj, `sessions()`, `planned_sessions()` | 20 araç / 10 ünite, memnuniyet KPI'ı, MILP |
