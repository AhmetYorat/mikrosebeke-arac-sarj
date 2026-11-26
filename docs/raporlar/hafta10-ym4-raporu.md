# Hafta 10 · YM-4 (Entegrasyon) · Rapor birleştirme, sunum taslağı, gerçek veri sonuçları

## Bu hafta yapılanlar

- **Gerçek veriyle sonuçlar.** `sonuclar` iş akışı artık modeli değiştiren PR'larda da çalışıyor. Altı senaryo,
  iki temsili gün, gerçek PVGIS verisi ve yük akışıyla çalıştırıldı (26.11.2026). Rapordaki bütün sayılar buradan.
- **Rapor birleştirme (`scripts/rapor_birlestir.py`).** Bölümleri sırayla `docs/rapor/RAPOR.md`'de topluyor ve
  pandoc varsa Word'e (`RAPOR.docx`) çeviriyor. Eksik bölümün yerine "bekleniyor" kutusu, eksik şeklin yerine not
  koyuyor; şekil yollarını düzeltiyor. Her bölüm sahibinin kendi dosyasında kalıyor, RAPOR.md elle düzenlenmiyor.
- **YM-4 bölümü (`docs/rapor/ym4-entegrasyon-ve-sonuclar.md`):** mimari, senaryolar, doğrulama, gerçek veri
  tabloları, bulgular, entegrasyonda bulunan hatalar, sınırlamalar.
- **Giriş ve Sonuç taslakları** (`giris.md`, `sonuc.md`). Ekip gözden geçirmeli.
- **Sunum taslağı (`docs/sunum/sunum-taslagi.md`):** 20 slayt; her slaytın sunanı, şekli ve tek ana mesajı.
- **Demo akışı gerçek veriye göre düzeltildi.** Gerçek veride Haziran'da V2G hiç kullanılmıyor; V2G adımı Aralık
  gününde gösterilecek.

## Raporun durumu

| # | Bölüm | Sorumlu | Durum |
| --- | --- | --- | --- |
| 1 | Giriş | YM-4 | taslak, ekip onayı bekliyor |
| 2 | Veri ve Yöntem | YM-1 | branch'te (`ym1/hafta9-duyarlilik`), **PR açılmadı** |
| 3 | Şarj İstasyonu Modeli | YM-2 | hazır; Tablo 2 S3–S6 ile güncellenmeli |
| 4 | EMS ve Optimizasyon | YM-3 | hazır ama **sayılar sahte istasyonla**; gerçek istasyonla güncellenmeli |
| 5 | Sistem Tasarımı, Şebeke ve Dinamik | EM-1, EM-2 | **yok** |
| 6 | Entegrasyon ve Senaryo Karşılaştırması | YM-4 | hazır (karşılaştırma şekilleri gerçek veriyle yerelde üretilecek) |
| 7 | Sonuç | YM-4 | taslak |

## Gerçek veriyle öne çıkanlar (Haziran)

- Kontrolsüz şarj: şebeke tepesi 23 → 232 kW, site sınırı 5 adım aşılıyor, şarjın %90'ı puantta.
- Akıllı şarj: puant tepe 232 → 33 kW (S3), S4–S6'da 0.
- Araçların ek maliyeti kWh başına 5,71 TL (S2) → 1,83 TL (S5).
- Tepe kayıyor: S5/S6'nın tepesi 05:45'te ve site sınırında (180 kW).
- Bekleme 0,2 → 4–5 saat; araçların %5–20'si hedefe yetişmiyor.

## Tutarsızlık uyarısı

YM-3'ün bölümünde S5 tepe alımı **67 kW** (sahte istasyonla), gerçek istasyonla **177–180 kW**. Raporda iki farklı sayı
olmamalı; YM-3 bölümünün sayıları `python -m microgrid.sim.sonuclar` tablosuyla güncellenmeli. Birleşik raporda bu
bölümün başına editör notu konuldu.
