# EMS ve optimizasyon (YM-3)

Kod: `src/microgrid/ems/` · Parametreler: `config/default.yaml → bess:` ve `ems:` · Arayüz: [arayuz-sozlesmesi.md](arayuz-sozlesmesi.md) bölüm 3.

| Modül | Ne yapar | Senaryo |
| --- | --- | --- |
| `bess.py` | Batarya modeli: SOC, verim, güç ve SOC sınırları | S4–S6 |
| `pv_first.py` | EMS v0: kontrolsüz şarj, PV → (batarya) → şebeke | S2 |
| `rule_based.py` | Kural tabanlı akıllı şarj: SOC eşikleri + tarife; `use_bess=True` ile batarya kuralları | S3, S4 |
| `milp.py` | Kayan ufuklu MILP (PuLP): maliyet en aza, sınırlar ve hedef SOC kısıt | S5, S6 |

## Batarya (`bess.py`)

`BESS.apply(power_kw, dt_h)` gücü inverter gücüne ve SOC bandına kırpar, uygulanan gücü döndürür.
Verim şarjda ve deşarjda ayrı ayrı uygulanır (0.95 → gidiş-dönüş ≈ %90).

## Kural tabanlı akıllı şarj (`rule_based.py`)

Her adımda, bağlı her araç için:

1. **Pencere:** şimdiden ayrılışa kadarki adımların fiyatı (tarife önceden bilinir).
2. **En ucuz adımlar:** araç ihtiyacını karşılayana kadar en ucuz adımlar seçilir. Sınırdaki fiyat diliminin tamamı kümeye girer.
   Planlamada ünite gücünün yalnızca `ems.safety` (%80) kadarına güvenilir.
3. **Eşit yayma:** şu an kümedeyse araç ihtiyacını kümenin adımlarına eşit yayarak çeker, değilse bekler.
   Neden tam güç değil: tüm araçlar gece diliminin ilk adımında tam güçle başlarsa 22:00'de yeni bir tepe oluşur.
4. **SOC eşiği:** SOC `ems.soc_floor` (0.30) altındaki araç tarifeden bağımsız, hemen taban SOC'ye kadar şarj edilir.
5. **Pencereye sığmayan ihtiyaç** tam güçle şarj edilir.
6. **PV fazlası** (PV > sabit yük) ücretsizdir; hedefe ulaşmamış araçlara verilir.
7. **Sınırlar:** toplam `station_limit_kw` ve `site_limit_kw − sabit yük + PV` ile sınırlanır; yetmezse ayrılışa en yakın araç önce.

## Batarya kuralları (`RuleBasedEMS(cfg, use_bess=True)`, Senaryo 4)

Araç kararından sonra, kalan net yüke (sabit yük + araçlar − PV) bakarak, şu öncelik sırasıyla:

| | Kural | Neden |
| --- | --- | --- |
| a | Site sınırı: araçlar şebeke alımını `site_limit_kw`'ın üstüne çıkaracaksa batarya farkı verir (tarifeden bağımsız) | Sınır EMS'in görevi; batarya araç şarjını kısmak yerine devreye girer |
| b | PV fazlası bataryaya girer | Şebekeye satış ücretsiz; boşa gitmesin |
| c | Puantta net yükü batarya karşılar; enerji kalan puant adımlarına eşit paylaştırılır | İlk saatte boşalıp son saatte kalmasın; şebekeye veriş olmaz |
| d | Gece ucuz dilimde SOC `ems.bess_night_target_soc` (0.5) altındaysa şebekeden şarj, kalan ucuz adımlara eşit yayılır, site sınırı aşılmaz | Yeni tepe oluşmasın |

Gece hedefi başlangıç SOC'sine eşittir: temsili gün tekrar eden bir gün sayıldığı için batarya gün sonunda gün başındaki
seviyeye döner. Aksi hâlde gün sonunda depoda kalan enerji bedelsiz görünür ve senaryolar adil karşılaştırılamaz.
PV ile dolan enerji bu kapsamda değil: o enerji zaten bedelsiz (satış ücretsiz).

**Sınır:** kural açgözlüdür. Yükün gün içindeki değişimini ve yarının fiyatını bilmez; yalnızca tarifenin en ucuz ve
en pahalı dilimini kullanır. Orta dilimde (gündüz) arbitraj yapmaz. Bu boşluğu optimizasyon (Senaryo 5) kapatır.

## Optimizasyon (`milp.py`, Senaryo 5)

**Kayan ufuk.** Her adımda bağlı araçlarla, bu adımdan gün sonuna kadar bir MILP çözülür; yalnızca ilk adım uygulanır.
Şimdiki adım için gerçek değerler, sonrası için tahmin (`prepare`, YM-1 `data.forecast`) kullanılır. Gün başında tek çözüm
yapılamaz çünkü araçların geliş saati, SOC'si ve ayrılışı o an bilinmiyor.

| | |
| --- | --- |
| Değişkenler | araç şarj gücü `ch[v,t]` (ayrılışa kadar), batarya `bch/bdis[t]` + ikili `z[t]`, şebeke `imp/exp[t]`, batarya SOC |
| Kısıtlar | güç dengesi, istasyon ≤ 150 kW, site ≤ 180 kW (cezalı gevşeme), batarya dinamiği ve SOC bandı, gün sonu SOC ≥ gün başı, araç hedef SOC (cezalı gevşeme) |
| Amaç | Σ fiyat·alım·dt + 0.2 TL/kW·tepe alım + batarya aşınması + cezalar |

Tepe ağırlığı küçük: maliyet aynı olan çözümler arasında düz olanı seçtirir, projenin ana sorusu (istasyonun getirdiği yük) bu.
Gün sonu SOC kısıtı olmasa batarya günün sonunda boşalır ve maliyet olduğundan düşük görünürdü.

Eşit maliyetli seçeneklerde kayan ufuk "sonra yaparım" tuzağına düşer (her adımda şarjı bir sonraki adıma erteler). Bunu
engellemek için enerjiyi erken depolatan ve aracı erken şarj ettiren çok küçük ağırlıklar var (`milp_*_early_*`).

Çözücü hata verirse ya da zaman aşımı olursa o adım `RuleBasedEMS`'e düşer (`MilpEMS.fallbacks`). Tam gün (96 adım) ≈ 6–8 sn.

**PuLP sürümü:** `requirements.txt` PuLP'u `<4` ile sınırlıyor. PuLP 4 CBC'yi artık içermiyor (`pip install pulp[cbc]` ve ayrı çözücü
gerekiyor) ve `LpVariable(...)`, `LpStatus` gibi eski API'yi kaldırdı.

## V2G (Senaryo 6)

İstasyon `VehicleRequest.max_discharge_kw > 0` bildirdiği araçlar V2G'ye uygundur. EMS negatif `ev_kw` ile aracı deşarj ettirir.

**Kural tabanlı (`RuleBasedEMS(cfg, ..., v2g=True)`, kural e):** puantta (ya da site sınırı aşılacaksa tarifeden bağımsız) batarya
yetmeyen net yükü V2G'li araçlar paylaşır. Önce batarya, çünkü aşınması araç bataryasından ucuz. İki garanti:

| Garanti | Nasıl |
| --- | --- |
| Minimum SOC | Araç `ems.v2g_soc_floor` (0.30) altına indirilmez |
| Ayrılışta hedef SOC | Deşarjdan sonra kalan ucuz adımlarda (ünite gücünün %80'iyle) hedefe yeniden dolabilecek kadar deşarj edilir |

Deşarj kayıplıdır: şebekeye verilen enerji = araç bataryasından çekilen × `ems.v2g_efficiency` (0.95). Şarj ise `station.charge_efficiency`
varsa ona göre planlanır (YM-2).

**Test istasyonu:** gerçek istasyon (YM-2) main'e girene kadar `sim.mocks.V2GMockStation` kullanılır: araçların %40'ı V2G'ye uygun,
11 kW deşarj, taban SOC 0.30. `v2g_share=0` ile aynı istasyonda V2G'siz karşılaştırma yapılır.
