# Veri ve Yöntem (YM-1)

Bu bölüm, simülasyona giren zaman serilerinin (güneş üretimi, sabit yük, elektrik fiyatı) nereden geldiğini,
nasıl işlendiğini ve sonuçların nasıl değerlendirildiğini anlatır. Bütün sayılar `config/default.yaml` içinden
okunur; kod `src/microgrid/data/`, `src/microgrid/kpi.py` ve `src/microgrid/analysis.py` altındadır.

## 1. Konum ve sistem

Mikro-şebeke Bandırma'da (40,352° K, 27,977° D, rakım 43 m) 50 daireli bir siteyi temsil eder. Sitenin
otoparkında 8 × 22 kW AC ve 2 × 50 kW DC şarj ünitesi, çatıda 100 kWp güneş paneli (PV) ve 200 kWh / 100 kW
sabit batarya (BESS) bulunur. Elektrik ekibinin (EM-1) belirlediği üç sınır kullanılır: şarj istasyonu 150 kW,
sitenin şebekeden çekebileceği toplam güç 180 kW, trafo 400 kVA. Site otoparkı tipi seçilmiştir: araçlar akşam
eve dönüşte gelir (ortalama 18:30), sabah ayrılır.

## 2. Veri kaynakları

| Veri | Kaynak | Çözünürlük | Not |
| --- | --- | --- | --- |
| Güneş ışınımı ve PV üretimi | PVGIS v5.3 (AB Ortak Araştırma Merkezi) | saatlik, 2023 | Ücretsiz API, 1 kWp için |
| Sabit yük | BDEW standart yük profilleri (H0 konut, G0 ticari) | 15 dk → saatlik | `demandlib` paketi, Türkiye tatilleri |
| Elektrik fiyatı | EPDK tarife tablosu, 4 Nisan 2026 | dilim | Üç zamanlı mesken |
| EV şarj oturumları | Caltech ACN-Data | oturum | Erişim denendi; talep modeli YM-2'de |

### 2.1 Güneş verisi (PVGIS)

PVGIS'ten Bandırma için 2023 yılının saatlik verisi, 30° eğimli, güneye bakan, %14 sistem kayıplı 1 kWp'lik
bir sistem için indirilmiştir. Kurulu güce ölçekleme `pv_kw = kurulu güç × pv_kw_per_kwp` ile yapılır; böylece
PV gücü değiştiğinde veri yeniden indirilmez. PVGIS zamanları UTC'dir; Türkiye saatine (UTC+3) çevrilir ve
yıl başına kayan üç saat düzeltilir. Eksik, tekrar eden veya negatif değer bulunmamıştır (kontroller kodda durur).

Bandırma'da yıllık üretim **1332 kWh/kWp**'tir; 100 kWp için yaklaşık 133 MWh/yıl. Aylık üretim Temmuz'da en
yüksek (174 kWh/kWp), Ocak'ta en düşüktür (58 kWh/kWp).

**Doğrulama:** PVGIS sonucu, panel düzlemi ışınımı ve hava sıcaklığından basit bir fiziksel modelle
(NOCT 45 °C, güç sıcaklık katsayısı −%0,4/°C) bağımsız olarak yeniden hesaplanmıştır. Saatlik değerler
R² = 0,999 ile örtüşür, yıllık fark %3,5'tir.

### 2.2 Sabit yük (BDEW profilleri)

Site binalarının (daireler, ortak alanlar, küçük dükkânlar) tüketimi, Almanya'da saatlik sayacı olmayan aboneler
için kullanılan BDEW standart yük profillerinden üretilmiştir: konut için H0 (mevsime göre değişen dinamik katsayı
ile), ticari kısım için G0. Profiller hafta içi, cumartesi ve pazar ile kış, yaz ve geçiş dönemlerini ayırır.
Türkiye'nin resmî tatilleri (2023'te 13 gün) pazar gibi işlenir. Ölçek EM-1 kararıdır: 50 daire × 2400 kWh/yıl
(120 MWh) + ortak alan ve dükkânlar 80 MWh = **200 MWh/yıl** (araç şarjı hariç). Yılın tepe yükü yaklaşık 41 kW'tır.

### 2.3 Elektrik tarifesi (EPDK)

EPDK'nın 4 Nisan 2026'dan itibaren geçerli tablosunda AG tek terimli mesken (8 kWh/gün üstü) çok zamanlı tarifesi
kullanılmıştır. Vergiler hariç fiyat, aktif enerji bedeli ile dağıtım bedelinin (242,49 kr/kWh) toplamıdır:

| Dilim | Saat | TL/kWh |
| --- | --- | --- |
| Gündüz | 06–17 | 4,3755 |
| Puant | 17–22 | 6,1725 |
| Gece | 22–06 | 2,9386 |

Gece fiyatı puantın yarısından azdır; akıllı şarjın maliyet avantajı buradan gelir. Şebekeye satılan PV fazlası
bu aşamada ücretlendirilmemiştir.

## 3. Zaman çözünürlüğü

Simülasyon 15 dakikalık adımlarla çalışır; temsili gün öğlen 12:00'de başlar ve ertesi gün 12:00'de biter, böylece
akşam gelen aracın gece boyunca süren şarjı tek pencereye sığar. Saatlik veriler 15 dakikaya doğrusal ara
değerlemeyle çevrilir. Güç anlık bir büyüklük olduğu için bölünmez; her saatlik değer temsil ettiği ana yerleştirilir
(PV için PVGIS'in hesap anı olan saatin 10. dakikası, yük için saatlik ortalamanın merkezi olan 30. dakika).
Bu yöntemle günlük enerji %2'den az farkla korunur.

## 4. Temsili günler ve yıla genişletme

Pandapower yük akışıyla bir günlük simülasyon yaklaşık bir saniye sürdüğünden yıl, temsili günlerle özetlenmiştir:
4 mevsim (kış Ara–Şub, ilkbahar Mar–May, yaz Haz–Ağu, sonbahar Eyl–Kas) × 2 gün tipi (hafta içi; hafta sonu ve
resmî tatil) × 3 gökyüzü sınıfı = **24 temsili gün**. Gökyüzü sınıfı, her mevsim ve gün tipindeki günlerin
günlük PV enerjisine göre üç eşit gruba (bulutlu, orta, güneşli) bölünmesiyle elde edilir. Her temsili gün, gruptaki
günlerin saatlik ortalamasıdır ve yıllık sonuca gruptaki gün sayısıyla ağırlıklandırılarak katılır.

**Doğrulama:** Araçsız senaryo 365 günün tamamı için simüle edilmiş ve temsili gün tahminleriyle karşılaştırılmıştır.

| Temsili gün | Yıllık maliyet hatası |
| --- | --- |
| 8 (mevsim × gün tipi) | %−11,1 |
| 16 (+ güneşli / bulutlu) | %−4,6 |
| 24 (+ bulutlu / orta / güneşli) | **%−3,1** |

Gökyüzü ayrımı yapılmadığında güneşli günlerin PV fazlası ile bulutlu günlerin şebeke alımı ortalamada birbirini
götürür ve maliyet olduğundan düşük çıkar. 24 temsili gün bu hatayı üçte birine indirir. PV ve tüketimin yıllık
toplamı her durumda birebir korunur.

Bataryanın temsili günlerde bedava enerji kazanmaması için gün döngüsel çalıştırılır: her temsili gün, bataryanın
bir önceki çalıştırmada bittiği doluluk ile yeniden başlatılır (iki ısınma turu).

Kritik an tespiti için temsili günler ayrıca kullanılabilir: yılın en yüksek şebeke yükü kışın bulutlu bir hafta
içi günü, 17:45 civarında oluşur.

## 5. Ertesi gün tahmini

Optimizasyonlu EMS (Senaryo 5) günü başında planlar. Plan gerçek değerlerle yapılırsa optimizasyonun başarısı
olduğundan iyi görünür; bu nedenle yalnızca geçmiş günlerin verisini kullanan gün öncesi tahminler hazırlanmıştır.
Yöntemler: dünün aynı saati (persistence), son 7 günün aynı saatteki ortalaması (climatology; yükte yalnızca aynı
gün tipinden) ve ikisinin karışımı (blend: %30 + %70). Yıl boyu karşılaştırmada seçilenler:

| Değişken | Yöntem | Saatlik hata (nMAE) | Günlük enerji hatası |
| --- | --- | --- | --- |
| PV | blend | kurulu gücün %5,1'i | 97 kWh/gün (ortalama üretim 365 kWh/gün) |
| Sabit yük | climatology | ortalama yükün %1,9'u | 10 kWh/gün |

PV hatası mevsime bağlıdır: Temmuz'da günde ~30 kWh, Aralık'ta günlük üretimin yaklaşık yarısı kadardır. Yük
tahmininin bu kadar iyi olması, yük verisinin standart bir profil olmasından kaynaklanır; gerçek sayaç verisinde
hata daha yüksek olur. Fiyat tarife olduğu için önceden bilinir.

## 6. Performans göstergeleri (KPI)

Bütün senaryolar aynı tanımlarla değerlendirilir (dt = adım süresi; işaret kuralında şebekeden alım pozitiftir):

| KPI | Tanım |
| --- | --- |
| Tepe yük | Şebekeden en yüksek alım (kW) ve zamanı |
| Maliyet | Σ max(şebeke, 0) × fiyat × dt (TL); alım gündüz / puant / gece dilimlerine ayrılır |
| Yenilenebilir payı | (PV − şebekeye veriş) / (sabit yük + araç şarjı) |
| Öz tüketim | (PV − şebekeye veriş) / PV |
| Araç şarjının puant payı | Puant dilimindeki şarj enerjisi / toplam şarj enerjisi |
| Sınır aşımı | 180 kW site ve 150 kW istasyon sınırının aşıldığı adım sayısı ve enerji |
| Gerilim ve yüklenme | En düşük bara gerilimi (p.u., sınır 0,95), en yüksek kablo ve trafo yüklenmesi (%) |

Batarya bir depo olduğu için tüketim sayılmaz; kayıpları şebeke alımına yansır.

## 7. Duyarlılık analizi

Araç sayısı (0–40), PV kurulu gücü (0–300 kWp) ve batarya kapasitesi (0–600 kWh) birer birer değiştirilip
her değer için yıllık KPI'lar 24 temsili günden hesaplanmıştır; diğer parametreler varsayılan değerlerinde tutulur.

## 8. Varsayımlar ve sınırlamalar

- Yük verisi ölçüm değil, Alman standart profilidir; Türkiye'deki yaz klima yükü ve günlük dalgalanma yoktur.
- Daire başına 2400 kWh/yıl bir başlangıç varsayımıdır.
- Hava verisi tek yıldır (2023); yıllar arası değişkenlik incelenmemiştir.
- Vergiler (KDV, BTV) maliyete katılmamıştır; senaryolar arası oranları değiştirmez.
- PV fazlasının şebekeye satışı ücretlendirilmemiştir.
- Temsili gün yöntemi yıllık maliyeti tam yıla göre ~%3 düşük tahmin eder; fark senaryoların hepsinde aynı yöndedir.

## Kaynaklar

- Huld, T., Müller, R., Gambardella, A. (2012). A new solar radiation database for estimating PV performance in
  Europe and Africa. *Solar Energy*, 86(6), 1803–1815. PVGIS: https://re.jrc.ec.europa.eu/pvg_tools/
- Meier, H., Fünfgeld, C., Adam, T., Schieferdecker, B. (1999). *Repräsentative VDEW-Lastprofile*. VDEW.
  Uygulama: oemof `demandlib`, https://github.com/oemof/demandlib
- EPDK (2026). 4 Nisan 2026 tarihinden itibaren geçerli vergiler hariç elektrik tarifeleri. https://www.epdk.gov.tr
- Lee, Z. J., Li, T., Low, S. H. (2019). ACN-Data: Analysis and Applications of an Open EV Charging Dataset.
  *Proceedings of the 10th ACM International Conference on Future Energy Systems (e-Energy '19)*, 139–149.
