# Canlı demo akışı (YM-4)

Süre: **6–7 dakika**. Demoyu YM-4 yapar, anlatımda ilgili modülün sahibi bir cümle ekler.
Amaç tek bir hikâye anlatmak: *istasyon akşam şebekeyi zorluyor → akıllı yönetim bunu çözüyor → ama bedeli var.*

## Demo öncesi kontrol listesi (sunumdan bir gün önce ve sabah)

- [ ] `git pull` → `main` güncel, `pytest` yeşil
- [ ] `pip install -r requirements.txt` (PuLP 3.x; 4.x'te S5/S6 çalışmaz)
- [ ] `python -m microgrid.data` çalıştırılmış: dashboard'da **sarı "sahte girdi" uyarısı görünmemeli**
- [ ] Dashboard açık, **"Bütün senaryoları çalıştır" bir kez basılmış** (ilk çalıştırma ~40 s; sonra önbellekten anında gelir).
      Sunum boyunca terminal kapatılmaz, yoksa önbellek gider.
- [ ] Tarayıcıda sekmeler hazır (aşağıdaki bağlantılar), yakınlaştırma %110–125 (projeksiyonda okunsun)
- [ ] İnternet gerekmez (veri yerelde). Wi-Fi kapalıyken bir kez denenmiş olsun
- [ ] Yedek: `docs/sunum/` altındaki demo ekran kaydı masaüstünde, bir tıkla açılabilir

Hazır sekmeler (`streamlit run dashboard/app.py` sonrası):

1. `http://localhost:8501/?senaryo=S2`
2. `http://localhost:8501/?senaryo=S3`
3. `http://localhost:8501/?senaryo=S6` (kenar çubuğundan **Aralık** seçilecek)

## Akış

| # | Süre | Ekranda | Söylenecek |
| --- | --- | --- | --- |
| 0 | 0:45 | S2, üstteki **canlı tek hat şeması** | "Sayfa günün tepe anında (19:45) açılıyor. Şemada güç şebekeden trafoya, oradan iki kabloya akıyor; çizgi kalınlığı güç. Kırmızı: site sınırı ve otopark kablosu (%117) aşılmış. Sağda otopark: 10 ünitenin hepsi dolu." **▶ Oynat**a basıp günü akıt; akşam kırmızıya dönüşü göster, sonra durdur. |
| 1 | 0:30 | S2, **Güç akışları** | "Site otoparkı: 20 araç, 10 ünite. Akşam eve dönen herkes aynı anda takıyor. Kırmızı çizgi istasyon; puant saatinde (gölgeli) şebeke alımı site sınırını (kesikli çizgi) aşıyor." |
| 2 | 1:00 | S2, **Şarj istasyonu** | "Her satır bir ünite. 18:00'den sonra hepsi dolu, tam güçte. Alttaki tablo araç başına: geliş, bekleme, SOC, hedefe ulaştı mı (YM-2'nin istasyon modeli: CC-CV, sıra, nöbetleşe şarj)." |
| 3 | 0:45 | S2, **Şebeke** | "Yük akışı (pandapower): en düşük gerilim ve trafo yüklenmesi. Kontrolsüz şarj gerilimi de düşürüyor." (EM-2 bir cümle) |
| 4 | 1:30 | **Senaryo karşılaştırması** | "Aynı gün, altı senaryo. Akıllı şarj (S3) puanttaki tepeyi 232'den 33 kW'a indiriyor; batarya (S4) ve optimizasyon (S5) puantta hiç alım bırakmıyor ve maliyeti daha da düşürüyor." Tabloda **verilen enerji** satırını da göster: maliyetler farklı enerji miktarları üzerinden. Tabloda tepe, maliyet ve **hedefe ulaşan araç** satırlarını göster. |
| 5 | 1:00 | Karşılaştırma grafiği, sabah saatleri | "Ama tepe yok olmuyor, kayıyor: optimizasyon şarjı gece tarifesinin bitişine (05–06) yığıyor ve site sınırına dayanıyor. Maliyeti en aza indirmek ile tepeyi en aza indirmek aynı şey değil." |
| 6 | 0:45 | S6, **Aralık**, **Şarj istasyonu** | "V2G: mavi hücreler araçtan şebekeye. Hiçbir araç %30'un altına inmiyor, ayrılışta hedef SOC garanti. Ama bu sitede miktar küçük: Aralık'ta 21 kWh, Haziran'da hiç; araçlar akşam zaten düşük dolulukla geliyor." (YM-3 bir cümle) **Haziran'da gösterme: V2G hiç kullanılmıyor, ekranda mavi görünmez.** |
| 7 | 0:30 | **Dinamik (Simulink)** | "Python günün kritik anını buluyor; elektrik ekibi o anı Simulink'te saniye mertebesinde inceliyor: frekans, gerilim." (EM-1/EM-2 sonuçları varsa grafiği aç) |
| 8 | 0:15 | Kenar çubuğu | İstenirse canlı: araç sayısını 20 → 35 yap, S2'de tepenin ve sınır aşımının arttığını göster. |

> Sayılar ve sıralamalar 26.11.2026'da `sonuclar` iş akışının **gerçek veri** tablosuyla kontrol edildi (rapor, Entegrasyon
> bölümü Tablo 4.1–4.2). Model değişirse demo öncesi yeniden kontrol edilmeli.

## Bir şey ters giderse

| Sorun | Ne yapılır |
| --- | --- |
| Dashboard açılmıyor / hata | Yedek ekran kaydına geç, anlatıma aynı akışla devam et |
| Sarı "sahte girdi" uyarısı | Veri hazırlanmamış. Demoya devam etme; sayıları rapordaki tablodan göster |
| Karşılaştırma çok yavaş | Yük akışını kenar çubuğundan kapat (gerilim boş kalır, güç ve maliyet aynı) |
| Hoca kodu görmek isterse | `src/microgrid/sim/scenarios.py` (senaryolar tek dosyada) ve `src/microgrid/interfaces.py` (modüller arası sözleşme) |

## Sayılar nereden?

Demoda görünen sayılar dashboard'un o an hesapladıklarıdır. Raporda ve slaytlarda kullanılan sayılar ise GitHub
Actions'taki `sonuclar` iş akışının ürettiği tablodan alınır; ikisi aynı kodla hesaplandığı için aynı çıkmalıdır.
Farklıysa önce `git pull` ve veri sürümü kontrol edilir.
