# Rapor: EMS ve optimizasyon (YM-3, Hafta 10)

Rapora girecek bölüm. Sayıların kaynağı: [hafta9-ym3-ems-optimizasyon.md](hafta9-ym3-ems-optimizasyon.md) (`scripts/ym3_hafta9_sonuclar.py`).

## 1. Amaç

Projenin sorusu: şarj istasyonu mikro-şebekeye ne yük getiriyor ve akıllı yönetimle bu yük ne kadar azaltılabiliyor? Enerji yönetim
sistemi (EMS) bu sorunun "akıllı yönetim" tarafıdır. Her 15 dakikada iki karar verir: her araca kaç kW verilecek (V2G'de negatif) ve
bataryanın gücü ne olacak. Şebeke gücü bir karar değil, güç dengesinin sonucudur:
`grid = sabit yük + araçlar + batarya − PV`.

## 2. Yöntem

Aynı arayüze (`prepare`, `decide`) takılan üç EMS karşılaştırıldı.

**Kontrolsüz (S2).** Araç bağlandığı an ünitenin tam gücüyle şarj olur. Bu, sorunun görüldüğü referanstır.

**Kural tabanlı (S3, S4).** Her araç için ayrılışa kadarki pencerede en ucuz tarife adımları seçilir ve ihtiyaç bu adımlara
*eşit* yayılır. Tam güçle başlatmak, tüm araçların gece diliminin ilk adımında aynı anda şarja geçip 22:00'de yeni bir tepe
yaratmasına yol açar; eşit yayma bunu önler. SOC eşiği: 0.30 altındaki araç tarifeden bağımsız şarj edilir. PV fazlası ücretsiz
olduğu için araçlara verilir. Toplam, istasyon (150 kW) ve site (180 kW) sınırlarıyla kısılır. Bataryada öncelik sırası: site sınırı,
PV fazlası, puantta deşarj, gece ucuz tarifeyle şarj.

**Optimizasyon (S5, S6).** Kayan ufuklu karma tamsayılı doğrusal program (PuLP, CBC çözücüsü). Her adımda bağlı araçlar için bu
adımdan günün sonuna kadar çözülür, yalnızca ilk adım uygulanır. Gün başında tek çözüm yapılamaz: araçların geliş saati, SOC'si ve
ayrılışı o an bilinmiyor.

Amaç (TL), $t$ adımları, $\Delta t$ = 0.25 saat:

$$\min \sum_t \pi_t\, P^{\mathrm{imp}}_t \Delta t \;+\; w_{\mathrm{peak}}\, P^{\mathrm{peak}} \;+\; c_{\mathrm{bess}} \sum_t P^{\mathrm{dis}}_t \Delta t \;+\; c_{\mathrm{v2g}} \sum_{v,t} P^{\mathrm{v2g}}_{v,t} \Delta t \;+\; \text{ceza}$$

Kısıtlar:

| Kısıt | İfade |
| --- | --- |
| Güç dengesi | $P^{\mathrm{imp}}_t - P^{\mathrm{exp}}_t = P^{\mathrm{yük}}_t + \sum_v (P^{\mathrm{ch}}_{v,t} - P^{\mathrm{v2g}}_{v,t}) + P^{\mathrm{bch}}_t - P^{\mathrm{bdis}}_t - P^{\mathrm{pv}}_t$ |
| Site sınırı | $P^{\mathrm{imp}}_t \le 180$ kW (cezalı gevşeme) |
| İstasyon sınırı | $\sum_v (P^{\mathrm{ch}}_{v,t} - P^{\mathrm{v2g}}_{v,t}) \le 150$ kW |
| Batarya | $E_{t+1} = E_t + (\eta P^{\mathrm{bch}}_t - P^{\mathrm{bdis}}_t/\eta)\Delta t$, SOC bandı $[0.1, 0.9]$, günün sonunda SOC $\ge$ başlangıç |
| Araç hedefi | ayrılışta SOC $\ge$ 0.80 (cezalı gevşeme) |
| V2G | araç SOC'si $\ge$ 0.30; aynı adımda hem şarj hem deşarj yok (ikili değişken) |

Tepe terimi $w_{\mathrm{peak}}$ = 0.2 TL/kW küçüktür; maliyeti aynı olan çözümler arasında düz olanı seçtirir.

## 3. Bulgular (Aralık hafta içi, 5 araç filosu ortalaması)

| Senaryo | Maliyet (TL) | Tepe alım (kW) | Puant şarj payı |
| --- | ---: | ---: | ---: |
| S2 Kontrolsüz | 3696 | 208 | 0.59 |
| S3 Akıllı şarj (kural) | 3076 (−17%) | 107 (−49%) | 0.01 |
| S4 + batarya (kural) | 2854 (−23%) | 107 (−49%) | 0.01 |
| S5 MILP | 2656 (−28%) | 67 (−68%) | 0.00 |
| S6 V2G (MILP) | 2633 (−29%) | 68 (−67%) | 0.00 |

1. Şarj saatini kaydırmak tek başına tepe yükü yarıya indirir. Bu, bataryasız ve yatırım gerektirmeyen çözümdür.
2. Batarya yazın (PV fazlası) kışa göre daha değerlidir: Haziran'da S3 → S4 maliyette −%26, Aralık'ta −%7.
3. Optimizasyon kural tabanlıya göre tepede %36–37, maliyette %7–15 daha iyi. Fark, bataryanın tarife farkından (gündüz 4.38, puant
   6.17 TL) yararlanmasından ve araç şarjıyla birlikte planlanmasından geliyor.
4. V2G bu sitede kazancı çok az artırıyor (−%1 ila −%3.5): araçlar akşam düşük SOC'yle geliyor ve sabah dolu ayrılmak zorunda.
   Aşınma bedeli 4 TL/kWh olursa V2G tamamen kapanıyor.

## 4. Tartışma ve sınırlar

- **Tahmin hatası.** Gerçek tarihli bir günde (20 Aralık) YM-1'in tahminiyle MILP kusursuz bilgiye göre %5.5 pahalı (2381 → 2512 TL) ve
  kural tabanlı S4 ile (2502 TL) maliyette pratik olarak başa baş. Tepe avantajı kalıyor (66 ve 107 kW). Tek gün; genelleme yapılmamalı.
- **İstasyon modeli.** Sonuçlar sahte istasyonla (CC-CV ve ünite paylaşımı yok) üretildi. YM-2'nin istasyonu eklenince yeniden
  çalıştırılacak; senaryoda tek satır (`station=`).
- **Varsayımlar.** Şebekeye satış ücretsiz; V2G araçların %40'ı, 11 kW, verim 0.95; V2G aşınması 0.5 TL/kWh (ölçüm değil, varsayım);
  yük profili BDEW standardı.
- **Yöntem sınırı.** Kayan ufuk gelecekteki araç gelişlerini bilmiyor; bu yüzden yeni gelen araçlar planı değiştirebiliyor. İleride
  gelişler için olasılıksal bir model eklenirse plan daha iyi olabilir.
- **PuLP sürümü.** PuLP 4 CBC'yi içermiyor ve API'yi değiştirdi; proje `pulp<4` kullanıyor.

## 5. "Hazır örnekten farkınız ne?" (EMS tarafı için cevap)

MathWorks V2G örneği saniyeler mertebesinde dinamik davranışı (frekans, gerilim) gösterir; bir günün enerji yönetimini yapmaz.
Bizim katkımız gün ölçeğinde bir karar katmanı: gerçek PV, yük ve tarife verisiyle, istasyon ve site sınırlarına uyarak araç şarjını ve bataryayı
planlıyor ve bu kararların tepe yüke, maliyete ve kullanıcı memnuniyetine (hedef SOC) etkisini ölçüyor. Simulink tarafı (EM-1, EM-2)
bu planın dinamik olarak kararlı olup olmadığını gösteriyor; iki katman birbirini tamamlıyor.

## 6. Sunum için notlar (EMS slaytları)

Slayt önerisi (3 slayt):

1. **Sorun ve çözüm yolu:** Aralık, kontrolsüz şarj 208 kW tepe (site sınırı 180 kW). Üç seviye: kontrolsüz, kural, MILP.
   Görsel: `hafta9-ym3-senaryolar.png` (üst panel).
2. **Sonuç:** yukarıdaki tablo; vurgu: tepe −%49 (kural) ve −%68 (MILP), maliyet −%17 ile −%29.
3. **Sınırlar:** batarya yazın daha değerli, V2G kazancı küçük, tahmin hatası maliyet avantajını eritiyor, istasyon sahte.

Olası sorular:

- *Kural neden eşit yayıyor, tam güçle şarj edip bitirmiyor?* Aynı anda başlayan araçlar gece diliminin başında yeni bir tepe yaratır.
- *MILP gerçek zamanlı çalışır mı?* Tek çözüm yaklaşık 0.1 sn; adım süresi 15 dk. Çözücü hata verirse kural tabanlı EMS'e düşer.
- *V2G neden bu kadar az kazandırıyor?* Araçlar akşam düşük SOC'yle gelip sabah hedefe dolu gitmek zorunda; taban SOC ile hedef arasındaki bant dar.
- *Tahmin yanlışsa ne olur?* Tepe avantajı korunuyor, maliyet avantajı bir günlük denemede S4 seviyesine iniyor (Hafta 9, bölüm "tahmin hatası").
