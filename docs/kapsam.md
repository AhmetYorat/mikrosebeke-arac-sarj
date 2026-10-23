# Kapsam kararı

Durum: **taslak**. 15 Ekim Perşembe ders sonrası toplantıda teyit edilecek.

## İstasyon tipi: site otoparkı

Ön karar site otoparkı. Gerekçe:

- Araçlar akşam eve dönüşte gelir (ortalama ~18:30), sabah ayrılır. Geliş saati PV üretiminin bittiği,
  sabit yükün ve puant tarifesinin (17–22) zirve yaptığı saate denk gelir. Kontrolsüz şarjın yarattığı
  sorun (tepe yük, gerilim düşümü, maliyet) en net bu tipte görünür.
- Araçlar ~13 saat bağlı kalır ama şarj için birkaç saat yeter. Aradaki boşluk akıllı şarjın yükü
  geceye kaydırmasına imkân verir; Senaryo 3–5'in anlamlı sonuç vermesi buna bağlı.
- Uzun bağlı kalma süresi V2G'yi (Senaryo 6) gerçekçi kılar: araç akşam pikinde enerji verip sabaha
  kadar yeniden dolabilir.

Diğer seçenekler neden geri planda:

| Tip | Sorun |
| --- | --- |
| AVM otoparkı | Gelişler gündüz, PV ile çakışır; kalış kısa olduğu için yük kaydırma payı küçük. Kontrolsüz ve akıllı şarj farkı zayıf kalabilir. |
| Otoyol hızlı şarj | Araç 20–30 dk kalır; erteleme ve V2G neredeyse anlamsız. Senaryo 3 ve 6 zayıflar. |

## Bileşenler (taslak değerler `config/default.yaml` içinde)

- PV dizisi, sabit batarya (BESS), ana şebeke bağlantısı (PCC), sabit yükler (site binaları), şarj istasyonu, EMS.
- Rüzgâr türbini: şimdilik kapsam dışı (opsiyonel).

## Toplantıda kapatılacak açık sorular

1. **İstasyon tipi teyidi:** site otoparkı kesinleşsin mi?
2. **DC üniteler:** Site otoparkında araçlar gece boyu kaldığı için DC hızlı şarj tipik değil. 2 × DC 50 kW
   kalsın mı (Simulink'te AC/DC dallarını ayrı göstermek için), yoksa yalnızca AC mi? (EM-1 + YM-2)
3. **Zaman kapsamı:** 1 temsili gün mü, hafta/yıl mı? Öneri: v0'a kadar temsili gün, genişletme Hafta 6'da.
4. **Konum:** PVGIS verisi için hangi şehir? (YM-1)
5. **Boyutlar:** Kısmen karar verildi (EM-1, Hafta 2):
   - Site: 50 daire × 2.400 kWh/yıl = 120 MWh/yıl, ortak alan + dükkân 80 MWh/yıl; araç şarjı hariç 200 MWh/yıl.
   - PV: 100 kWp, 30° eğim, güneye dönük.
   - Sınırlar: istasyon 150 kW, site toplamı 180 kW, trafo 400 kVA.
   - Açık: araç sayısı, BESS kWh/kW, DC ünite sorusu.
