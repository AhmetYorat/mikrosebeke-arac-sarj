# Parametre Tablosu

Durum: **taslak**. 22 Ekim Perşembe ders sonrası toplantıda teyit edilecek.

## Mikro-Şebeke Bileşenleri

| Parametre | Değer | Birim | Açıklama | Kaynak |
| --- | --- | --- | --- | --- |
| **PV Sistemi** |  |  |  |  |
| installed_kw | 100 | kWp | Kurulu güneş paneli gücü | EM-1 |
| pvgis_year | 2023 | - | PVGIS veri yılı | YM-1 |
| tilt_deg | 30 | ° | Panel eğimi (Bandırma optimumu) | EM-1 |
| azimuth_deg | 0 | ° | Güneye bakan (PVGIS standardı) | EM-1 |
| loss_percent | 14 | % | Kablo, inverter, kirlenme kayıpları | PVGIS varsayılanı |
| **Batarya (BESS)** |  |  |  |  |
| capacity_kwh | 200 | kWh | Toplam depolama kapasitesi | EM-1 |
| power_kw | 100 | kW | Maksimum şarj/deşarj gücü | EM-1 |
| efficiency | 0.95 | - | Şarj/deşarj verimi | Teknik veri |
| soc_min | 0.10 | - | Minimum SOC (koruma) | EM-1 |
| soc_max | 0.90 | - | Maksimum SOC (koruma) | EM-1 |
| soc_initial | 0.50 | - | Başlangıç SOC | Simülasyon |
| **EV Şarj İstasyonu** |  |  |  |  |
| type | site_otoparki | - | İstasyon tipi | Kapsam kararı |
| power_limit_kw | 150 | kW | Bağlantı/trafo limiti | EM-1 |
| vehicle_count | 20 | adet | Araç sayısı | EM-1 |
| battery_kwh | 60 | kWh | Araç batarya kapasitesi | YM-2 (ACN-Data'dan) |
| **Şarj Üniteleri** |  |  |  |  |
| AC_units | 8 | adet | AC şarj üniteleri | EM-1 |
| AC_power | 22 | kW | Her AC ünite gücü | TÜİK standardı |
| DC_units | 2 | adet | DC hızlı şarj üniteleri | EM-1 |
| DC_power | 50 | kW | Her DC ünite gücü | TÜİK standardı |
| **Araç Talebi** |  |  |  |  |
| arrival_hour_mean | 18.5 | saat | Geliş saatinin ortalaması (18:30) | Site otoparkı profili |
| arrival_hour_std | 1.5 | saat | Geliş saati standart sapması | - |
| departure_hour_mean | 7.5 | saat | Ayrılış saatinin ortalaması (07:30) | - |
| departure_hour_std | 1.0 | saat | Ayrılış saati standart sapması | - |
| arrival_soc_min | 0.20 | - | Minimum arrived SOC | -
| arrival_soc_max | 0.60 | - | Maksimum arrived SOC | -
| target_soc | 0.80 | - | Hedef doluluk oranı | -
| **Grid/PCC** |  |  |  |  |
| transformer_kva | 400 | kVA | Trafo kapasitesi | EM-1 |
| voltage_min_pu | 0.95 | p.u. |Minimum gerilim limiti | EN 50160 |
| voltage_max_pu | 1.05 | p.u. | Maksimum gerilim limiti | EN 50160 |
| max_loading_percent | 100 | % | Maksimum yüklenme | - |
| **Simülasyon** |  |  |  |  |
| step_minutes | 15 | dakika | Zaman adımı | PRD v2 |
| horizon_hours | 24 | saat | Simülasyon periyodu | PRD v2 |

## Elektriksel Sınır Değerleri

| Parametre | Min | Max | Birim | Açıklama |
| --- | --- | --- | --- | --- |
| Bara gerilimi | 0.95 | 1.05 | p.u. | EN 50160 standardı |
| Hat akımı | - | 1.0 × rated | % | Hata koruma sınırları |
| Trafo yüklenmesi | - | 100 | % | Sürekli çalışma |
| BESS SOC | 0.10 | 0.90 | - | Ömür koruması |
| PV üretimi | 0 | 100 | kW |Installed kapasite |

## Timings (15 dk adım, 96 dönem/gün)

| Zaman dilimi | Başlangıç | Bitiş | Açıklama |
| --- | --- | --- | --- |
| Gece | 22:00 | 06:00 | Düşük talep, düşük fiyat |
| Gunduz | 06:00 | 17:00 | Orta talep, orta fiyat |
| Puant | 17:00 | 22:00 | Yüksek talep, yüksek fiyat |
| Gecikmeli puant | 22:00 | 00:00 | Düşüş dönemi |

## Gerilim ve Yüklenme Hata Ayıklama Eşiği

| Sensitivite | Değer | Birim |
| --- | --- | --- |
| Gerilim düşümü toleransı | 0.05 | p.u. |
| Hattan aşırı yüklenme | 1.0 × rated | % |
| Trafo aşırı yüklenme | 1.0 × rated | % |
| Güç dengesi toleransı | 0.01 | kW |

---

## Notlar

- **EM-1** = Elektrik mühendisi sorumluluğu
- **YM-2** = Yazılım mühendisi (araç verileri için ACN-Data kaynaklı)
