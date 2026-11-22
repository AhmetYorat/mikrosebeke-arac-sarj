# Hafta 8 · YM-2 (Şarj istasyonu) · V2G

Rapor: 3 Aralık 2026.

## Bu hafta yapılanlar

- **V2G istasyon tarafı hazır.** `station.v2g_enabled: true` olunca V2G destekli araçlar (katalogda Tesla Model 3 ve
  Ioniq 5) `VehicleRequest.max_discharge_kw` ile deşarj sınırını bildirir; EMS negatif güç isterse `apply`
  bu sınıra kırpar. V2G kapalıyken (varsayılan) negatif istek 0 uygulanır.
- **Deşarj kuralı ve iki garanti** (`ElectricVehicle.max_discharge_kw`):
  1. **Minimum SOC:** araç `vehicles.v2g_min_soc` (0,3) altına indirilmez. 0,3'ün altında gelen araçtan hiç enerji alınmaz.
  2. **Ayrılışta hedef SOC:** bu adımda verilen enerji ayrılışa kadar geri doldurulabilir olmalı. Bu adımdan sonra
     kalan süre t, ünitedeki tam şarj gücü p, verim η, batarya B ise:
     `t · p · η ≥ (hedef − SOC) · B + E_çıkan`  ⇒  `E_çıkan ≤ t · p · η − (hedef − SOC) · B`.
     Adımın deşarj sınırı `min(ünite/OBC gücü, E_çıkan · η / dt)`.
- Hedefe ulaşmış ama hâlâ deşarj edebilecek araç da EMS'e listelenir (V2G için aday).
- `planned_sessions()`'ta `max_discharge_kw` artık V2G açıkken dolu (MILP için).
- Testler: V2G kapalı/uygun olmayan araç, ünite ve min SOC sınırı, ayrılışa yakın deşarj yok, enerji korunumu
  (şarj·η − deşarj/η = SOC artışı × B), "17–22 arası en fazla deşarj, sonra tam şarj" isteyen açgözlü bir EMS ile bile
  bütün araçların hedefe ulaşması.

## Kanıt (sahte girdi, Haziran; açgözlü test EMS'i)

| Araç sayısı | V2G destekli | Puantta şebekeye verilen (kWh) | En yüksek V2G gücü (kW) | Hedefe ulaşma |
| --- | --- | --- | --- | --- |
| 10 | 5 | 21,6 | 19,1 | 1,00 |
| 20 | 12 | 58,8 | 52,1 | 1,00 |

## YM-3 için not

Senaryo 6, `config={"station.v2g_enabled": True}` override'ı ve YM-3'ün V2G EMS'iyle eklenir. EMS, aracın
`max_discharge_kw`'sini aşan bir istek gönderse bile istasyon garantileri kendisi uygular.

## Gelecek hafta (Hafta 9)

- Şarj istasyonu rapor bölümü; sınıf diyagramı ve parametre belgesinin son hâli. 9 Aralık kod dondurma.
