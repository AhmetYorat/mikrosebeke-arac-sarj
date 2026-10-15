# Veri kaynakları (YM-1, Hafta 1)

Üç kaynağa erişim denendi. Her biri için nereden geldiği, formatı ve projede nasıl kullanılacağı aşağıda.
Verinin nasıl indirileceği: [data/README.md](../data/README.md).

## Özet

| Veri | Kaynak | Erişim | Durum | Projede kullanan |
| --- | --- | --- | --- | --- |
| Güneş ışınımı / PV üretimi | PVGIS v5.3 (AB JRC) | Açık API, anahtar yok | Çalışıyor, Bandırma 2023 indirildi | YM-1 PV modeli → EMS, döngü |
| EV şarj oturumları | Caltech ACN-Data | API, ücretsiz token | Kod hazır, token bekleniyor | YM-2 talep modeli |
| Elektrik tarifesi | EPDK üç zamanlı tarife | Elle (EPDK tablosu) | Fiyatlar girildi, resmi tablodan doğrulanacak | YM-3 EMS, YM-1 KPI (maliyet) |
| Sabit yük profilleri | Açık veri / sentetik | — | Hafta 2 | YM-1 yük modeli |

## 1. PVGIS: güneş verisi

- **Konum:** Bandırma, 40.352° K, 27.977° D (rakım 43 m). `config/default.yaml → site`.
- **Sorgu:** `seriescalc` uç noktası, 1 kWp sistem, eğim 30°, güneye bakan, %14 kayıp, yıl 2023.
  1 kWp için indirildiği için kurulu güç değişince yeniden indirmek gerekmez: `pv_kw = installed_kw × pv_kw_per_kwp`.
- **Ham format:** JSON, yıl boyunca 8760 saatlik satır.

| PVGIS alanı | Anlamı | Birim | Bizdeki sütun |
| --- | --- | --- | --- |
| `time` | `20230621:0910` biçimi, **UTC** | — | `timestamp` (Türkiye saati, UTC+3) |
| `P` | 1 kWp'lik sistemin AC gücü | W | `pv_kw_per_kwp` (kW/kWp) |
| `G(i)` | Panel düzlemine gelen ışınım | W/m² | `irradiance_w_m2` |
| `T2m` | Hava sıcaklığı | °C | `temp_c` |
| `WS10m` | Rüzgâr hızı (10 m) | m/s | `wind_m_s` |

- **Dikkat edilecekler:**
  - Saatler UTC gelir, `:10` dakikası saatin temsil anıdır. Saate yuvarlayıp Türkiye saatine çeviriyoruz.
    Bu kaymadan dolayı dosya 1 Ocak 03:00'te başlar, son 3 saat 2024'e taşar.
  - Saatlik çözünürlük. Config'deki 15 dk'lık adım için ara değerleme gerekecek (Hafta 3, PV modeli).
  - PVGIS v5.3'te kullanılabilen son yıl 2023.
- **İlk sonuçlar (Bandırma, 1 kWp):** yıllık **1332 kWh/kWp**, yani 100 kWp için ~133 MWh/yıl.
  Haziranda ortalama günlük tepe 13:00'te 0,67 kW/kWp, Aralıkta 0,34 kW/kWp.
  Aylık üretim Temmuzda en yüksek (174 kWh/kWp), Ocakta en düşük (58 kWh/kWp).

![Bandırma PVGIS](raporlar/hafta1-ym1-pvgis-bandirma.png)

**Proje açısından anlamı:** Haziranda bile PV üretimi 19:00'da neredeyse sıfıra iniyor.
Site otoparkında araçların ortalama varışı 18:30, puant tarifesi 17–22 arası.
Yani kontrolsüz şarj, PV'nin olmadığı ve elektriğin en pahalı olduğu saate denk geliyor.
Bu durum, kapsam dokümanındaki site otoparkı seçiminin gerekçesini veriyle destekliyor.
Gündüz PV fazlası bataryaya (BESS) aktarılıp akşam kullanılabilir (Senaryo 4).

## 2. ACN-Data: gerçek şarj oturumları

- **Kaynak:** Caltech Adaptive Charging Network, ABD'deki üç sitenin oturumları: `caltech`, `jpl` ve `office001`.
- **Erişim:** `https://ev.caltech.edu/api/v1/sessions/<site>` adresi. Token gerekir; ücretsiz kayıt: https://ev.caltech.edu/register.
  Token, HTTP Basic Auth'da kullanıcı adı olarak verilir, şifre boş bırakılır. Tokensiz istek `401` döner (denendi).
  Sayfa başına 25 oturum gelir, sonraki sayfa `_links.next` alanında.
- **Önemli alanlar:**

| Alan | Anlamı | Birim / format |
| --- | --- | --- |
| `connectionTime` | Aracın takıldığı an | RFC 1123, **UTC** |
| `disconnectTime` | Aracın çıkarıldığı an | RFC 1123, UTC |
| `doneChargingTime` | Şarjın bittiği an | RFC 1123, UTC |
| `kWhDelivered` | Verilen enerji | kWh |
| `timezone` | Sitenin saat dilimi (UTC'den çevirmek için) | ör. `America/Los_Angeles` |
| `userInputs[].kWhRequested`, `requestedDeparture` | Kullanıcının istediği enerji ve ayrılış (mobil uygulamadan) | kWh, tarih |

- **Kod:** `microgrid.data.acn.sessions_to_frame` oturumları talep modeline uygun sütunlara indirir:
  varış saati (yerel), kalış süresi (saat), verilen ve istenen enerji.
- **Dikkat edilecekler:**
  - Veri **işyeri** otoparkları (sabah gelip akşam ayrılma) içindir. Bizim site otoparkımızda (akşam gelip sabah ayrılma)
    varış saatleri doğrudan kullanılamaz. Kalış süresi ve enerji ihtiyacı dağılımları ise kullanılabilir.
    Öneri: varış/ayrılış saatleri için config'deki Normal dağılımı kullanmak, enerji ihtiyacını ACN'den almak (YM-2 ile konuşulacak).
  - Web arayüzünden 10 Ekim 2019 öncesi indirilen dosyalarda 7–8 saatlik kayma var. API'de bu sorun yok.

## 3. EPDK tarifesi

- **Girilen değerler (`config/default.yaml → tariff`):** Mesken üç zamanlı, 4 Nisan 2026 dönemi, vergiler hariç.

| Dilim | Saat | TL/kWh |
| --- | --- | --- |
| Gündüz | 06–17 | 4,38 |
| Puant | 17–22 | 6,17 |
| Gece | 22–06 | 2,94 |

- **Kaynak durumu:** Değerler ikincil kaynaklardan alındı (akillitarife.com, piagrid.com).
  EPDK'nın resmi tablo sayfası (epdk.gov.tr → Elektrik Faturalarına Esas Tarife Tabloları) dosyaları JavaScript ile yüklediği için
  otomatik indirilemedi. **Yapılacak:** Tablo tarayıcıdan elle indirilip değerler doğrulanacak. Temmuz ve Ekim 2026 güncellemesi varsa
  o kullanılacak.
- **Kararlaştırılacak:** Site otoparkı bir apartman/site aboneliği olduğu için mesken tarifesi uygun görünüyor.
  Ticarethane veya "genel aydınlatma" tarifesi istenirse yalnızca config değişir.
- Vergiler (KDV, BTV) dahil edilmedi. Senaryolar arası karşılaştırmada oranlar değişmediği için sade tutuldu.
- Gece fiyatı puantın yaklaşık yarısı (2,94 / 6,17 ≈ 0,48). Akıllı şarjın tasarrufu buradan gelecek.

## Ekibe ve hocaya sorular

1. **Tarife grubu:** Mesken mi, ticarethane mi? (Öneri: mesken, site otoparkı.)
2. **Vergiler:** Maliyet KPI'ı vergi hariç mi verilsin? (Öneri: hariç.)
3. **ACN-Data (YM-2):** Varış saatleri işyeri profiline göre. Enerji ihtiyacını ACN'den, saatleri sentetik dağılımdan almak uygun mu?
4. **Temsili gün (herkes):** Hangi gün temsil edecek? Öneri: v0 için yıllık ortalama veya Haziran ve Aralık ortalama günleri.
