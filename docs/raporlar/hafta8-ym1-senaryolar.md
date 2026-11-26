# Senaryolar arası karşılaştırma (yıllık)

Bandırma, 24 temsili gün (4 mevsim × 2 gün tipi × 3 gökyüzü) → yıl; pandapower yük akışıyla. Üreten betik: `scripts/ym1_hafta8_senaryolar.py`.

| KPI | S1 Temel (araç yok) | S2 Kontrolsüz şarj | S3 Akıllı şarj | S4 Akıllı şarj + batarya | S5 Optimizasyon (MILP) | S6 V2G (MILP) |
| --- | --- | --- | --- | --- | --- | --- |
| Yıllık maliyet | 524.955 TL | 1.774.527 TL | 1.146.916 TL | 983.224 TL | 910.695 TL | 910.327 TL |
| Yılın tepe alımı | 38 kW | 246 kW | 163 kW | 163 kW | 180 kW | 180 kW |
| Araçlara verilen enerji | 0 kWh | 215.384 kWh | 177.214 kWh | 177.214 kWh | 203.687 kWh | 206.087 kWh |
| Puantta alım | 41.861 kWh | 235.436 kWh | 46.737 kWh | 11.098 kWh | 545 kWh | 0 kWh |
| Araç şarjının puant payı | — | %90 | %3 | %3 | %2 | %2 |
| Yenilenebilir payı | %42 | %22 | %24 | %29 | %30 | %30 |
| Öz tüketim | %63 | %67 | %67 | %82 | %91 | %91 |
| Site sınırı (180 kW) aşımı | 0 kWh | 14.587 kWh | 0 kWh | 0 kWh | 0 kWh | 0 kWh |
| En düşük gerilim | 0,988 p.u. | 0,960 p.u. | 0,973 p.u. | 0,973 p.u. | 0,969 p.u. | 0,969 p.u. |
| En yüksek kablo yüklenmesi | %28 | %117 | %81 | %81 | %94 | %94 |
| En yüksek trafo yüklenmesi | %13 | %64 | %42 | %42 | %47 | %47 |

- S1 Temel (araç yok): Karşılaştırma tabanı: istasyon boş, yalnızca PV + sabit yük + şebeke.
- S2 Kontrolsüz şarj: Araç geldiği an tam güçle şarj olur, batarya kullanılmaz. Sorunun görüldüğü senaryo.
- S3 Akıllı şarj: Kural tabanlı EMS (YM-3): şarj ayrılışa kadar en ucuz tarife adımlarına eşit yayılır, SOC < 0.30 olan araç hemen taban SOC'ye çıkarılır, PV fazlası araçlara verilir, istasyon ve site sınırlarına uyulur. Batarya yok.
- S4 Akıllı şarj + batarya: S3'ün araç kuralı + 200 kWh / 100 kW batarya (YM-3): puantta yükü bataryadan karşılar, gece ucuz tarifede ve PV fazlasıyla dolar, site sınırını aşacak anda devreye girer.
- S5 Optimizasyon (MILP): Maliyeti en aza indiren kayan ufuklu MILP (YM-3, PuLP): her adımda bağlı araçlar, batarya, istasyon ve site sınırlarıyla gün sonuna kadar çözülür, ilk adım uygulanır. Tepe alımı küçük ağırlıkla bastırılır.
- S6 V2G (MILP): S5'e V2G eklenir (YM-3 EMS + YM-2 istasyonu): araç kataloğunda V2G'ye uygun araçlar şebekeye geri verebilir. Araç SOC'si vehicles.v2g_min_soc altına inmez, ayrılışta hedef SOC garanti. Karşılaştırma tabanı: S5.

**Okurken dikkat:** "Araçlara verilen enerji" senaryolar arasında farklı. Bir EMS araçlara daha az enerji veriyorsa maliyeti de düşük çıkar; maliyet karşılaştırması bu satırla birlikte okunmalı.
