# Sunum · Şarj istasyonu slaytları (YM-2)

6 slayt, ~4 dakika. Görseller `docs/rapor/` ve `docs/raporlar/` altında; sunumdan önce gerçek veriyle yeniden
üretilmeli (`python -m microgrid.data`, sonra `scripts/ym2_hafta5_tepe_yuk.py` ve `scripts/ym2_rapor_grafikleri.py`).

## 1. Projenin merkezi: şarj istasyonu

- Site otoparkı: 8 × AC 22 kW + 2 × DC 50 kW, 20 araç, istasyon sınırı 150 kW
- MathWorks V2G örneğinde araçlar 2 toplu batarya; bizde tek tek gelen, farklı modelde araçlar
- Her araç: batarya, OBC sınırı, geliş/ayrılış saati, geliş ve hedef SOC

Görsel: tek hat şemasında istasyon bölümü (EM-1). Not: "Hazır örnekten farkımız ne?" sorusunun cevabı bu slayt.

## 2. Talep modeli

- Geliş ~ N(18:30; 1,5 sa), ayrılış ertesi sabah ~ N(07:30; 1 sa)
- Geliş SOC %20–60, hedef %80
- 5 modelli katalog: Zoe, Tesla Model 3, Togg T10X, Ioniq 5, e-208; filonun yarısı AC'de 11 kW ile sınırlı

Görsel: katalog tablosu. Not: dağılımlar config'te; aynı seed ile her çalıştırma aynı filoyu üretir.

## 3. CC-CV ve ünite yönetimi

- SOC %80'e kadar sabit güç, sonra doğrusal azalma
- Önce AC, AC dolunca DC; ünite yoksa sıra
- Nöbetleşe şarj: dolan araç, bekleyen varsa üniteyi bırakır

Görsel: `docs/rapor/ym2-cc-cv.png`, `docs/rapor/ym2-unite-dolulugu.png`.

## 4. Kontrolsüz şarjın etkisi

- 10 araçtan itibaren istasyon 150 kW, site 180 kW sınırını aşıyor
- Tepeyi ünite sayısı belirliyor: 15 araçtan sonra tepe pek artmıyor
- Tepe 19:30–20:00, puant tarifesinin ortasında

Görsel: `docs/raporlar/hafta5-ym2-tepe-yuk.png`.

## 5. Kullanıcı memnuniyeti ve V2G garantisi

- Kontrolsüz: herkes dolar ama tepe yüksek. Geceye yayan akıllı şarj: tepe düşer ama sıradakiler yetişemez
- V2G: SOC 0,3'ün altına inmez; verilen enerji ayrılışa kadar geri doldurulabilir olmalı
- Sonuç: deşarjdan sonra hedef her zaman yetişilebilir; EMS tam güçle geri şarj ederse araç sabah hedefinde

Görsel: memnuniyet tablosu (`docs/rapor/ym2-memnuniyet.md`), V2G koşulu formülü.

## 6. Kod: döngüde istasyon

```text
vehicles = station.requests(ctx)              # kim bağlı, en fazla ne çekebilir / verebilir
decision = ems.decide(...)                    # YM-3
applied  = station.apply(ctx, decision.ev_kw) # sınırlara kırp, SOC güncelle
```

Satır satır anlatılacak fonksiyonlar:
- `ChargingStation.requests` (`src/microgrid/station/charging_station.py`): ayrılış → geliş → nöbetleşe → atama
- `ChargingStation.apply`: kalan pay ve verimle kırpma
- `cc_cv_limit` ve `ElectricVehicle.max_discharge_kw` (`src/microgrid/station/vehicle.py`): CC-CV ve V2G garantisi
