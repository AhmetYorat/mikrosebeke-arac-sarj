# Sonuç

> Taslak (YM-4, Hafta 10). Sayılar Entegrasyon bölümündeki gerçek veri tablolarındandır. Ekip gözden geçirecek.

**Şarj istasyonu bu mikro-şebekeye ne yük getiriyor?** Kontrolsüz şarjda 20 aracın istasyonu, sitenin şebekeden
çektiği en yüksek gücü araçsız güne göre yaklaşık on kat artırıyor (Haziran'da 23 kW'tan 232 kW'a). Bu tepe akşam
19:45'te, puant tarifesine denk geliyor; site sınırı (180 kW) 1–1,5 saat boyunca aşılıyor ve araç şarjının %90'ı en
pahalı tarife diliminde yapılıyor. Gerilim sınırların içinde kalıyor (en düşük 0,96 p.u.), trafo %60–64 yüklü. Yani
bu sitede asıl kısıt gerilim değil **güç sınırı ve maliyet**.

**Akıllı yönetimle ne kadar azaltılabiliyor?** Şarjı ucuz saatlere kaydıran basit bir kural bile puanttaki tepeyi
Haziran'da %86, Aralık'ta %71 düşürüyor ve site sınırı hiç aşılmıyor. Batarya ve optimizasyon puant alımını tamamen
ortadan kaldırıyor. Araçların siteye getirdiği ek maliyet kWh başına 5,7–5,9 TL'den 1,8–2,3 TL'ye iniyor.

**Ama üç bedeli var:**

1. **Tepe kayıyor.** Maliyeti en aza indiren yönetim, kalan şarjı gece tarifesinin bittiği 06:00'dan hemen önceye
   topluyor; optimizasyonda sabah tepesi site sınırına dayanıyor. Maliyeti ve tepeyi birlikte gözeten bir amaç gerekiyor.
2. **Üniteler meşgul kalıyor.** Şarj geceye yayılınca 10 ünite sabaha kadar dolu kalıyor; ortalama bekleme 0,2 saatten
   4–5 saate çıkıyor ve araçların %5–20'si hedef doluluğa yetişemiyor. Ünite sayısı sınırlıyken EMS gücün yanında
   sırayı da yönetmeli.
3. **V2G bu kullanım tipinde sınırlı.** Akşam düşük doluluğa gelen ve sabah dolu ayrılması gereken araçların
   şebekeye verebileceği enerji az (günde 0–21 kWh).

**Öneriler:** Site otoparkı için en verimli adım yatırım gerektirmeyen akıllı şarj kuralıdır. Batarya yazın (PV
fazlasıyla) kışa göre çok daha değerlidir. Optimizasyon kullanılacaksa sabah tepesini sınırlayan bir kısıt ya da tepe
cezası eklenmelidir.

**Gelecek çalışmalar:** gerçek şarj oturumu verisiyle (ör. ACN-Data) talep modelinin kalibrasyonu; tek temsili gün
yerine çok günlü/olasılıksal simülasyon; ünite sırasını da planlayan bir EMS; Simulink dinamik sonuçlarının zaman
serisi sonuçlarıyla birlikte değerlendirilmesi.
