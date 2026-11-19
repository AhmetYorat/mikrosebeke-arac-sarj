# Hafta 8–9 · YM-1 (Veri katmanı) · Senaryo tablosu ve duyarlılık analizi

## Bu hafta yapılanlar

- **Analiz modülü** (`src/microgrid/analysis.py`): bir senaryo (istasyon, EMS, batarya, config değişiklikleri) 24 temsili
  günde çalıştırılıp yıllık KPI'ya çevriliyor. `scenario_table` senaryoları, `sweep` bir parametrenin değerlerini karşılaştırıyor.
  - **Döngüsel batarya:** her temsili gün, bataryanın bir önceki çalıştırmada bittiği doluluk ile başlıyor
    (gün 2 kez ısınma için tekrarlanıyor). Böyle yapılmasaydı batarya her gün %50 dolu başlar, boşalttığı enerji
    her gün bedavaya geri gelirdi; 600 kWh bataryada yıllık tasarruf ~2 kat büyük çıkıyordu.
- **Hafta 8, senaryo tablosu** (`scripts/ym1_hafta8_senaryolar.py` → `hafta8-ym1-senaryolar.md`): S1 ve S2 yıllık, pandapower ile.
  S3–S6 sütunları YM-2 istasyonu ve YM-3 EMS'i ana koda girince aynı betikle tek satır ekleyerek dolacak.
- **Hafta 9, duyarlılık analizi** (`scripts/ym1_hafta9_duyarlilik.py`): araç sayısı, PV gücü, batarya kapasitesi.
- Sahte bataryada kapasite 0 olunca sıfıra bölme hatası düzeltildi (`sim/mocks.py`, YM-4 dosyası).
- **Testler:** senaryo tablosu, duyarlılık, döngüsel bataryanın bedava enerji vermemesi. 5 yeni test, toplam 57.

## Senaryo tablosu (yıllık)

Bkz. [hafta8-ym1-senaryolar.md](hafta8-ym1-senaryolar.md). Kontrolsüz şarj yıllık maliyeti 525 bin TL'den 1,25 milyon TL'ye,
yılın tepe alımını 38 kW'tan 179 kW'a çıkarıyor; araç şarjının %53'ü puant diliminde.

## Duyarlılık analizi

![Duyarlılık](hafta9-ym1-duyarlilik.png)

| Parametre (mevcut değer) | Bulgu |
| --- | --- |
| **Araç sayısı** (20) | Her 5 araç yıllık maliyeti ~100–250 bin TL artırıyor. **25 araçta site sınırı (180 kW) aşılıyor** (yılda 3,2 MWh), 30'da 10 MWh. Mevcut tasarım (20 araç) sınırın tam kıyısında. 30'dan sonra artış duruyor çünkü 10 ünite dolu, araçlar sırada bekliyor. |
| **PV gücü** (100 kWp) | 100 → 200 kWp yıllık maliyeti %11 (133 bin TL) düşürüyor, yenilenebilir payını %26'dan %34'e çıkarıyor. Ama **tepe yükü değiştirmiyor** (179 → 178 kW): tepe akşam, PV yokken. Öz tüketim düşüyor (fazla PV şebekeye gidiyor, satış modelde yok). |
| **Batarya** (200 kWh) | Geçici basit kuralla (PV fazlasını sakla, puantta kullan): 200 kWh yıllık ~205 bin TL tasarruf, 300 kWh'ten sonra doyuyor. **Tepe yük düşmüyor:** yılın tepesi kışın bulutlu bir günde, bataryayı dolduracak PV yok. |

**Sonuç:** Tepe yükü PV ve batarya tek başına çözmüyor; çözüm araç şarjını zamanda kaydırmak (akıllı şarj, Senaryo 3)
veya bataryayı gece ucuz tarifeden doldurup akşam kullanmak (EMS, Senaryo 4–5). YM-3 için girdi: batarya kuralı gece
şebekeden şarjı içermeli.

## Sınırlamalar

- İstasyon sahte (her gün aynı 20 araç, 10 ünite). Batarya kuralı geçici; YM-3 EMS'i gelince batarya duyarlılığı
  yeniden çalıştırılmalı (betik aynı, yalnızca `ems=` değişir).
- Duyarlılık noktalarında hız için yük akışı yok; gerilim/yüklenme senaryo tablosunda (pandapower ile).
- Yıllık değerler 24 temsili günden; tam yıla göre ~%3 düşük (Hafta 6).
