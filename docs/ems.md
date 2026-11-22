# EMS ve optimizasyon (YM-3)

Kod: `src/microgrid/ems/` · Parametreler: `config/default.yaml → bess:` ve `ems:` · Arayüz: [arayuz-sozlesmesi.md](arayuz-sozlesmesi.md) bölüm 3.

| Modül | Ne yapar | Senaryo |
| --- | --- | --- |
| `bess.py` | Batarya modeli: SOC, verim, güç ve SOC sınırları | S4–S6 |
| `pv_first.py` | EMS v0: kontrolsüz şarj, PV → (batarya) → şebeke | S2 |
| `rule_based.py` | Kural tabanlı akıllı şarj: SOC eşikleri + tarife | S3 |

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
