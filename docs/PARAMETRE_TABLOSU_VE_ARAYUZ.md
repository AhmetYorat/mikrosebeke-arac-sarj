# PARAMETRE TABLOSU VE MODÜL ARAYÜZ DOKÜMANI
**Proje:** Mikro-Şebeke Modellenmesi ve Analizi (EV Şarj İstasyonu İçeren Sistem)  
**Rol:** YM-2 (Şarj İstasyonu Modeli)  
**Tarih:** 21 Ekim 2026 (Hafta 2 Çıktısı) · Hafta 9'da güncellendi  
**İlgili Paydaşlar:** EM-1 (Tek Hat Şeması), YM-3 (EMS & Optimizasyon), YM-4 (Entegrasyon & Dashboard)

---

## 📋 1. İstasyon ve Bileşen Parametre Tablosu

| Parametre Adı | Değer | Birim | Kaynak / Açıklama | İlgili Rol |
| :--- | :--- | :--- | :--- | :--- |
| **İstasyon Konsepti** | Konut / Site Otoparkı | - | EM-1 ve YM-2 ortak kararı (bkz. `docs/kapsam.md`, `config/default.yaml`) | EM-1, YM-2 |
| **AC Şarj Soketi Sayısı** | 8 | Adet | Tip-2 Mennekes standardı (Site sakinlerinin ev tipi gece parklanması ve şarjı) | EM-1, YM-2 |
| **AC Soket Nominal Gücü** | 22.0 | kW | 3 Faz, 400V, 32A | EM-1, YM-2 |
| **DC Şarj Soketi Sayısı** | 2 | Adet | CCS2 Combo standardı (Site sakinleri acil dolum / misafir araçlar ve Simulink DC dalı) | EM-1, YM-2 |
| **DC Soket Nominal Gücü** | 50.0 | kW | Hızlı şarj doğrultucu ünitesi | EM-1, YM-2 |
| **İstasyon Toplam Kurulu Güç** | **276.0** | **kW** | $(8 \times 22) + (2 \times 50)$ kW teorik tavan | EM-1, YM-4 |
| **İstasyon güç sınırı** | **150.0** | **kW** | `station.power_limit_kw` (EM-1); EMS aşmamalı | EM-1, YM-3 |
| **Site şebeke alım sınırı** | **180.0** | **kW** | `grid.site_import_limit_kw` (EM-1) | EM-1, YM-3 |
| **Aşırı Yük Payı (Over-subscription)** | %184 | - | Kurulu güç / istasyon sınırı $(276 / 150)$ | EM-2, YM-2 |
| **V2G alt SOC** | 0.30 | Oran | `vehicles.v2g_min_soc` | YM-2, YM-3 |
| **Nöbetleşe şarj** | açık | - | `station.rotate_when_full` | YM-2 |
| **Şarj Verimliliği ($\eta$)** | 0.95 | Oran | Dönüştürücü ve batarya iç kayıpları | YM-2, YM-3 |
| **CC-CV Kırılma Eşiği** | 0.80 (%80) | Oran | Sabit akımdan sabit gerilime geçiş noktası | YM-2, EM-1 |
| **Zaman Adımı ($\Delta t$)** | 0.25 | Saat | 15 dakikalık simülasyon adımı (günde 96 adım) | YM-1..4 |

---

## 🚗 2. Araç Filosu Parametre Havuzu

| Model | Batarya (kWh) | Max AC (kW) | Max DC (kW) | V2G Desteği | Dağılımdaki Ağırlık |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Renault Zoe E-Tech** | 52.0 | 22.0 | 50.0 | Hayır | %25 |
| **Tesla Model 3 SR+** | 60.0 | 11.0 | 170.0 | Evet | %30 |
| **Togg T10X Uzun Menzil** | 88.5 | 22.0 | 150.0 | Hayır | %25 |
| **Hyundai Ioniq 5** | 77.4 | 11.0 | 220.0 | Evet | %10 |
| **Peugeot e-208** | 50.0 | 11.0 | 100.0 | Hayır | %10 |

---

## 🔌 3. Modül arayüzü (Hafta 9 son hâli)

Hafta 2'de önerilen `bagli_araclar / apply_power_allocations / get_total_power_kw` imzaları, ekip sözleşmesine
uyması için `requests / apply` ile değiştirildi. Güncel arayüz ve bütün ayrıntılar:
[docs/arayuz-sozlesmesi.md](arayuz-sozlesmesi.md), "YM-2: Şarj istasyonu" bölümü. Özet:

| Kim | Çağrı | Döner |
| --- | --- | --- |
| Döngü (YM-4) | `station.requests(ctx)` | bağlı araçlar: `VehicleRequest(charger_id, vehicle_id, soc, battery_kwh, target_soc, departure, max_charge_kw, max_discharge_kw)` |
| Döngü (YM-4) | `station.apply(ctx, ev_kw)` | ünite başına uygulanan güç (kW) |
| EMS (YM-3) | `by_departure(vehicles, budget_kw, dt_h, eff)` | ayrılışa göre güç dağıtımı |
| MILP (YM-3) | `station.planned_sessions()`, `station.n_chargers` | araç başına kısıtlar |
| KPI (YM-1) | `satisfaction(result.sessions)` | kullanıcı memnuniyeti |
| EM-1/EM-2 | `critical_station_snapshot(result, cfg)` | istasyon tepe anı: güç, şarj eden AC/DC sayısı, ortalama SOC |

Parametre değerleri `config/default.yaml`'dadır (`station:`, `vehicles:`); bu belgedeki tablo onlarla aynıdır.
Değişiklik config'te yapılır, bu tablo ona göre güncellenir.
