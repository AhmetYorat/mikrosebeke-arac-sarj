# Giriş

> Taslak (YM-4, Hafta 10). Ekip gözden geçirecek.

## Problem

Elektrikli araçların yaygınlaşmasıyla birlikte konutlarda ve otoparklarda şarj istasyonları kuruluyor. Bu istasyonlar
dağıtım şebekesi için büyük ve zamanlaması öngörülmesi zor bir yük. Bir site otoparkında araçların çoğu akşam eve
dönüşte, aynı saat aralığında takılıyor. Bu saat hem sitenin kendi tüketiminin hem de elektrik fiyatının (puant
tarife, 17–22) en yüksek olduğu saattir.

Projenin sorusu:

> Şarj istasyonu bu mikro-şebekeye ne yük getiriyor ve akıllı yönetimle bu yük ne kadar azaltılabiliyor?

## Kapsam

Bandırma'da 50 daireli bir siteyi temsil eden bir mikro-şebeke modellendi:

- **Sabit yük:** konutlar, ortak alan ve dükkânlar (yılda yaklaşık 200 MWh, araç şarjı hariç)
- **PV:** 100 kWp çatı sistemi
- **Batarya (BESS):** 200 kWh / 100 kW
- **Şarj istasyonu:** 8 × AC 22 kW ve 2 × DC 50 kW ünite, günde 20 araç; istasyon sınırı 150 kW
- **Şebeke bağlantısı:** 400 kVA trafo; site toplamı 180 kW ile sınırlı

İstasyon tipi olarak **site otoparkı** seçildi: araçlar akşam gelip sabah ayrıldığı için hem kontrolsüz şarjın
sorunu en net bu tipte görünür hem de akıllı şarjın yükü geceye kaydırabileceği uzun bir zaman penceresi vardır
(gerekçe: `docs/kapsam.md`). Fiziksel bir maket kurulmadı; bütün çalışma bilgisayar simülasyonudur.

## Yöntemin özeti

Çalışma iki katmanda yürütüldü:

1. **Zaman serisi simülasyonu (Python).** 15 dakikalık adımlarla bir temsili gün: gerçek güneş verisi (PVGIS),
   standart yük profilleri (BDEW) ve EPDK tarifesiyle. Her adımda şarj istasyonu modeli araçların isteklerini,
   enerji yönetim sistemi (EMS) kararları, pandapower da şebekenin gerilim ve yüklenmesini hesaplar. Altı senaryo
   karşılaştırıldı: araçsız temel durum, kontrolsüz şarj, kural tabanlı akıllı şarj, akıllı şarj + batarya,
   optimizasyon (MILP) ve araçtan şebekeye enerji (V2G).
2. **Dinamik analiz (MATLAB/Simulink).** MathWorks'ün *Microgrid with Electric Vehicles V2G Support* örneği temel
   alınarak saniyeler mertebesindeki frekans ve gerilim davranışı incelenir. Zaman serisi simülasyonu günün en zorlayıcı
   anını bulur; dinamik model o anı ayrıntılı inceler.

## Ekip ve bölümler

| Bölüm | Sorumlu |
| --- | --- |
| Veri ve yöntem (güneş, yük, tarife, KPI) | YM-1 |
| Şarj istasyonu modeli | YM-2 |
| Enerji yönetim sistemi ve optimizasyon | YM-3 |
| Entegrasyon, senaryo karşılaştırması, dashboard | YM-4 |
| Sistem tasarımı, şebeke ve dinamik analiz | EM-1, EM-2 |
