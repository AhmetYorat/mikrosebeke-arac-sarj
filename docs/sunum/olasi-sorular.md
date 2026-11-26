# Olası sorular ve cevaplar

> YM-4 hazırladı (Hafta 11). Provada her soruyu sahibi bir kez sesli cevaplasın. Sayılar rapordaki gerçek veri
> tablolarından (Entegrasyon bölümü, Tablo 4.1–4.2); başka sayı söylenmez. Bilmediğimiz bir şey sorulursa
> "bunu modellemedik / ölçmedik" demek, tahmin yürütmekten iyidir.

## Proje geneli

**Hazır MathWorks örneğinden farkınız ne?** (YM-3, YM-4)
Örnekte iki toplu batarya grubu (20'şer araç) ve saniyeler süren bir frekans testi var; şarj istasyonu, PV ve 24 saatlik
analiz yok. Bizde: üniteleri, sırası ve CC-CV eğrisi olan bir istasyon modeli; gerçek güneş ve tarife verisi; altı senaryonun
gün boyu karşılaştırması; pandapower ile şebeke analizi; Simulink tarafında örnek, PV, batarya ve AC/DC şarj dallarıyla genişletildi.

**Neden site otoparkı?** (YM-4)
Araçlar akşam puantında geliyor, sabah gidiyor: kontrolsüz şarjın sorunu en net bu tipte görünür ve akıllı şarjın
kaydırabileceği uzun bir gece penceresi var. AVM'de gelişler PV ile çakışır, otoyolda araç 20–30 dakika kalır;
kaydırma ve V2G anlamsızlaşır.

**Neden yalnızca iki temsili gün?** (YM-1)
Haziran (PV en yüksek) ve Aralık (yük en yüksek) iki uç durum. Yıla genişletme yöntemi Veri ve Yöntem bölümünde.
Sınırlama: günden güne değişkenlik ve tek bir araç gelişi örneği.

**Sonuçlar ne kadar güvenilir?** (YM-4)
Model doğrulanmış bir saha ölçümüyle kalibre edilmedi; sonuçlar senaryolar arası **karşılaştırma** için anlamlı, mutlak
değer tahmini olarak değil. Her adımda güç dengesi ve bütün sınırlar otomatik testlerle kontrol ediliyor; sayılar her
seferinde aynı kodla, temiz bir ortamda (GitHub Actions) üretiliyor.

## Şarj istasyonu (YM-2)

**Araç talebini nasıl modellediniz?** Geliş ~N(18,5; 1,5) saat, ayrılış ertesi sabah ~N(7,5; 1,0), geliş SOC'si %20–60
arası, hedef %80; araç modelleri gerçek bir katalogdan (batarya, AC/DC gücü, V2G desteği) paylarına göre seçiliyor.
Sentetik; ACN-Data ile kalibre edilmedi.

**20 araç neden 10 ünite?** Site otoparkında her daireye ünite yok; ünite paylaşımı ve sıra gerçek bir kısıt.
Sonuç: tepeyi araç sayısı değil ünite sayısı belirliyor (15 araçtan sonra tepe pek artmıyor).

**CC-CV neden önemli?** SOC %80'e yaklaşınca araç gücü düşüyor; bunu modellemezsek araçların daha hızlı dolduğunu ve
üniteyi daha erken bıraktığını varsayarız.

## EMS ve optimizasyon (YM-3)

**MILP neden kayan ufuklu?** Gelecekte hangi aracın ne zaman geleceği bilinmiyor; her adımda o an bağlı araçlarla gün
sonuna kadar planlanıyor, yalnızca ilk adım uygulanıyor.

**Optimizasyon en ucuzunu buluyorsa neden tepe sabaha kayıyor?** Amaç fonksiyonu maliyeti en aza indiriyor; gece
tarifesi 06:00'da bitiyor, en ucuz çözüm kalan şarjı bu saatten hemen önceye toplamak. Tepeye küçük bir ceza var ama
maliyet farkının yanında zayıf. Çözüm: tepe ağırlığını artırmak ya da sabah için güç sınırı koymak. Bunu bilinçli
olarak sonuç olarak gösteriyoruz: maliyeti en aza indirmek ile tepeyi en aza indirmek aynı şey değil.

**Neden bazı araçlar hedefe ulaşmıyor?** Şarj geceye yayıldığı için üniteler sabaha kadar dolu kalıyor ve sıradaki
araçlar geç bağlanıyor. MILP'te hedef kesin değil, cezalı bir kısıt. EMS'in ünite sırasını da planlaması gerekiyor (açık iş).

**V2G neden bu kadar az?** Araçlar akşam düşük dolulukla geliyor (%20–60) ve sabah %80'le ayrılmak zorunda; %30'un
altına inilmiyor. Verebilecekleri enerji az: Haziran'da hiç, Aralık'ta günde 21 kWh. Ofis ya da filo otoparkında
(araç gündüz dolu, uzun bekliyor) V2G daha anlamlı olurdu.

## Şebeke ve elektriksel taraf (EM-1, EM-2)

**Gerilim sorunu var mı?** Kontrolsüz şarjda en düşük gerilim 0,96 p.u. (sınır 0,95); trafo %60–64 yüklü. Bu sitede asıl
kısıt gerilim değil, 180 kW site sınırı (kontrolsüz şarjda 1–1,5 saat aşılıyor).

**Şebeke modeli nedir?** pandapower ile alçak gerilim ağı: 20/0,4 kV 400 kVA trafo, ana panodan iki kablo (site
150 m: sabit yük ve PV; otopark 100 m: istasyon ve batarya). Her 15 dakikada yük akışı çözülüyor. Kablo boyları ve güç
faktörleri varsayım; parametreler `docs/sebeke-modeli.md`.

**Simulink ile Python nasıl bağlanıyor?** Python günün en zorlayıcı anını (en yüksek şebeke alımı ve o anın güçleri)
buluyor; Simulink o anı başlangıç koşulu alıp saniyeler mertebesinde frekans/gerilim davranışını inceliyor. Sonuçlar
CSV ile dashboard'un Dinamik sekmesine geliyor.

## Yazılım / entegrasyon (YM-4)

**Dört kişi aynı kodda nasıl çalıştınız?** Modüller arası veri sözleşmesi (`interfaces.py`) 2. haftada yazıldı. Herkes
diğerlerinin sahte karşılığıyla çalıştı; gerçek modül gelince senaryoda tek satır değişti. `main`'e yalnızca PR ile,
otomatik testler yeşilse girildi.

**Entegrasyonda ne çıktı?** Ayrı ayrı testlerden geçen modüller birlikte çalışınca üç hata göründü: EMS istasyonun
%95 verimini hesaba katmıyordu (araçların %45'i hedefe ulaşmıyordu), KPI çözücü toleransını sınır aşımı sayıyordu,
EMS sonuçları sahte istasyonla üretilmişti (tepe 67 kW görünüyordu, gerçekte 177–180 kW). Hepsi düzeltildi.

**Maliyeti neden kWh başına verdiniz?** Senaryolar araçlara farklı miktarda enerji veriyor (486–590 kWh). Ham günlük
maliyet, az enerji veren senaryoyu haksız yere ucuz gösterir. Araçların ek maliyetini verilen enerjiye böldük.
