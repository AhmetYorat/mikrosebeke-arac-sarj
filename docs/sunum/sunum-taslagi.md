# Sunum taslağı · 24 Aralık 2026

> YM-4 hazırladı (Hafta 10). Toplam ~20 dakika + soru-cevap. Her slaytta **tek mesaj**; sayılar rapordaki gerçek veri
> tablolarından (Entegrasyon bölümü, Tablo 4.1–4.2) alınır, başka kaynaktan sayı konmaz.
> YM-2'nin istasyon slaytları: `ym2-istasyon-slaytlari.md`; YM-3'ün EMS notları: rapor bölümü, kısım 6.

| # | Slayt | Sunan | Görsel | Ana mesaj |
| --- | --- | --- | --- | --- |
| 1 | Başlık | YM-4 | — | Proje adı, ekip ve roller |
| 2 | Problem | YM-4 | Basit şema: site + otopark + şebeke | "Akşam herkes aynı anda şarja takıyor; bu, sitenin şebekeye ne yük getiriyor ve akıllı yönetimle ne kadar azalır?" |
| 3 | Sistem | EM-1 | Tek hat şeması | 100 kWp PV, 200 kWh batarya, 10 ünite (8 AC + 2 DC), 150 kW istasyon / 180 kW site sınırı, 400 kVA trafo |
| 4 | Yöntem: iki katman | YM-4 | Mimari şema (Python zaman serisi ↔ Simulink dinamik) | Python günün kritik anını bulur, Simulink o anı saniye mertebesinde inceler |
| 5 | Veri | YM-1 | `ym1-1-sorun-aralik-gunu.png` | Gerçek veri: Bandırma PVGIS, BDEW yük profilleri, EPDK tarifesi; Haziran ve Aralık temsili günleri |
| 6 | Şarj istasyonu modeli | YM-2 | `ym2-cc-cv.png`, `ym2-unite-dolulugu.png` | Araç kataloğu, CC-CV, sıra ve nöbetleşe şarj; "tepeyi araç sayısı değil ünite sayısı belirliyor" |
| 7 | **Sorun: kontrolsüz şarj** | YM-2 | Karşılaştırma şekli, yalnızca S1 ve S2 | Şebeke alımı 23 → 232 kW (×10), site sınırı 1–1,5 saat aşılıyor, şarjın %90'ı puantta |
| 8 | EMS: kural tabanlı | YM-3 | Akış şeması | Ucuz saate yay, SOC tabanı, PV fazlası, sınırlar |
| 9 | EMS: optimizasyon ve V2G | YM-3 | MILP amaç ve kısıtları (sade) | Kayan ufuklu MILP; V2G'de %30 taban ve ayrılışta hedef garanti |
| 10 | **Sonuç: altı senaryo** | YM-4 | Karşılaştırma şekli (Haziran) + KPI tablosu | Puant tepe 232 → 33 kW (S3), 0 kW (S4–S6); site sınırı hiç aşılmıyor |
| 11 | Adil maliyet | YM-4 | TL/kWh çubuk grafiği (S2–S6) | Araçların ek maliyeti kWh başına 5,7 → 1,8 TL (Haziran); ham günlük maliyet yanıltıcı, verilen enerji farklı |
| 12 | **Ama: tepe kayıyor** | YM-4 | Karşılaştırma şekli, 04:00–07:00 yakın plan | Optimizasyon şarjı 06:00'dan önceye yığıyor, sabah site sınırına dayanıyor. Maliyeti en aza indirmek ≠ tepeyi en aza indirmek |
| 13 | Kullanıcı tarafı | YM-2 | Hedefe ulaşan araç ve bekleme tablosu | Bekleme 0,2 sa → 4–5 sa; araçların %5–20'si hedefe yetişmiyor |
| 14 | Batarya ve V2G | YM-3 | Haziran/Aralık S3 → S4 maliyeti | Batarya yazın %20, kışın %6 tasarruf; V2G bu sitede günde 0–21 kWh |
| 15 | Şebeke kalitesi | EM-2 | Gerilim/trafo grafiği (dashboard Şebeke sekmesi) | En düşük gerilim 0,96 p.u. (sınırın içinde); asıl kısıt güç sınırı |
| 16 | Dinamik analiz | EM-1/EM-2 | Simulink D1–D4 grafikleri | Kritik anda frekans/gerilim davranışı (**sonuçlar gelince doldurulacak**) |
| 17 | **Canlı demo** | YM-4 | Dashboard | `demo-akisi.md`'deki akış, en fazla 4 dk |
| 18 | Sonuç ve öneriler | YM-4 | — | Yatırımsız akıllı şarj en verimli adım; batarya yazın değerli; optimizasyona sabah tepe sınırı eklenmeli |
| 19 | "Hazır örnekten farkımız" | YM-3 | — | MathWorks örneğinde istasyon, PV ve 24 saatlik analiz yok; bizde gerçek istasyon modeli, gerçek veri, altı senaryo |
| 20 | Teşekkürler / sorular | — | — | — |

## Şekillerin kaynağı

| Şekil | Nasıl üretilir |
| --- | --- |
| Karşılaştırma (Haziran / Aralık) | `python -m microgrid.sim.sonuclar` → `results/sonuclar/karsilastirma_*.png` (gerçek veriyle, `python -m microgrid.data` sonrası) |
| TL/kWh çubuk grafiği | Rapordaki 5.3 tablosundan; yalnızca S2–S6 |
| İstasyon ve CC-CV | YM-2: `scripts/ym2_rapor_grafikleri.py` |
| Veri şekilleri | YM-1: `scripts/ym1_sunum_grafikleri.py` (branch `ym1/hafta9-duyarlilik`) |
| Gerilim / trafo | Dashboard → Şebeke sekmesi (S2, Haziran), ekran görüntüsü |

## Kurallar

- Slayt başına en fazla bir grafik ve üç madde. Tablo gerekiyorsa yalnızca anlatılan satırlar.
- Renkler dashboard'la aynı: istasyon kırmızı, batarya mavi, PV sarı, şebeke siyah; senaryo renkleri karşılaştırma şekliyle aynı.
- Her sayının yanında birimi; mevsim belirtilmeli (Haziran / Aralık).
- Sahte girdiyle üretilmiş hiçbir sayı ya da şekil slayta girmez (dashboard'da sarı uyarı görünüyorsa o ekran kullanılmaz).
