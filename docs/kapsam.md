# Kapsam kararı

Durum: **kesinleşti**. İstasyon tipi olarak **Site Otoparkı** seçildi.

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

1. **İstasyon tipi teyidi:** **Site otoparkı kesinleşti.** (Akşam geliş, gece boyu kalış, puant tepe tıraşlama ve V2G için en uygun model).
2. **DC üniteler:** 2 × DC 50 kW ünitenin kalması kararlaştırıldı (Acil dolum ihtiyacı olan site sakinleri/misafirler ve Simulink modelinde AC/DC dönüştürücü dallarını ayrı doğrulamak için).
3. **Zaman kapsamı:** 1 temsili gün mü, hafta/yıl mı? Öneri: v0'a kadar temsili gün, genişletme Hafta 6'da.
4. **Konum:** PVGIS verisi için hangi şehir? (YM-1)
5. **Boyutlar:** araç sayısı, PV kW, BESS kWh/kW, trafo kVA. (EM-1, Hafta 2 parametre tablosu)
