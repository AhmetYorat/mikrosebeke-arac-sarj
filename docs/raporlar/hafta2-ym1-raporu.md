# Hafta 2 · YM-1 (Veri katmanı) · 15–21 Ekim 2026

Rapor: Perşembe 22 Ekim

## Bu hafta yapılanlar

- **PVGIS verisi indirildi ve temizlendi.** `python -m microgrid.data.pvgis` artık indirip temizliyor ve
  `data/processed/pv_bandirma_2023.csv` dosyasını yazıyor: yerel saatte tam yıl, 8760 saat.
  Tek düzeltme, UTC → Türkiye saati kaymasıyla ertesi yıla taşan 3 saatti. Eksik, tekrar eden veya hatalı değer çıkmadı.
  Bu kontroller kodda duruyor, başka yıl veya konum indirilirse rapor ediliyor.
- **Konut ve ticari yük profilleri hazırlandı (saatlik).** BDEW standart profilleri (H0 konut, G0 ticari) Türkiye resmî
  tatilleriyle üretilip config'deki yıllık tüketimle ölçekleniyor: `python -m microgrid.data.loads` →
  `data/processed/yuk_profilleri_2023.csv`.
  Taslak ölçek: 120 daire × 2400 kWh + ticari 80 MWh, toplam 368 MWh/yıl.
- **Temsili gün fonksiyonu:** `average_day(df, months, weekdays)` hem PV hem yük için 24 saatlik ortalama gün veriyor.
  v0'daki temsili gün kararına hazır.
- **Testler:** PV temizleme (3 test) ve yük profilleri (4 test) eklendi. İnternete çıkmadan çalışıyorlar. Toplam 13 test geçiyor.
- Kaynak, format ve varsayımlar: `docs/veri-kaynaklari.md` (bölüm 1 ve 4).

## Kanıt

![PV ve sabit yük](hafta2-ym1-pv-yuk.png)

| | Haziran (hafta içi) | Aralık (hafta içi) |
| --- | --- | --- |
| PV tepe (100 kWp) | 71 kW, 13:00 | 32 kW, 12:00 |
| Sabit yük tepe | 53 kW, 12:00 | 75 kW, 19:00 |
| 19:00'da PV / sabit yük | 4 kW / 46 kW | 0 kW / 75 kW |

Yıllık: PV 133 MWh, sabit yük 368 MWh, yıllık tepe yük 84 kW (30 Aralık 19:00).
PV'nin %86'sı aynı saatte sabit yükte tüketiliyor; ~19 MWh fazla, BESS veya akıllı şarj için kullanılabilir.

**Yorum:** Akşam sabit yük tepesi, puant tarifesi (17–22) ve araçların varışı (~18:30) aynı saatte. PV o saatte yok.
Kontrolsüz şarj en yüksek yükün üstüne biniyor; bu, akıllı şarj ve BESS senaryolarının neden gerektiğini veriyle gösteriyor.

## Sorunlar ve hocaya sorular

- BDEW profilleri Almanya kaynaklı. Türkiye'deki bir site için kabul edilebilir mi? (Yaz klima yükü profilde yok.)
- Daire sayısı ve daire başına tüketim varsayım. EM-1'in boyutlandırmasıyla kesinleşecek.
- YM-2'nin parametre tablosunda istasyon konsepti "Karma Ticari / AVM", kapsam dokümanında "site otoparkı" yazıyor.
  Ekipte netleşmeli. Yük profillerindeki konut/ticari oranı buna göre değişir (yalnızca config).

## Gelecek hafta (Hafta 3)

- PV modeli: temiz ışınım verisinden kurulu güce göre üretim, 15 dakikalık adıma ara değerleme.
- Tarife modülü: üç zamanlı tarifeden her zaman adımının fiyatı. EPDK resmî tablosundan fiyat doğrulaması.
