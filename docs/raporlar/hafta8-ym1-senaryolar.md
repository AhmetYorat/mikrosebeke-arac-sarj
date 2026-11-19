# Senaryolar arası karşılaştırma (yıllık)

Bandırma, 24 temsili gün (4 mevsim × 2 gün tipi × 3 gökyüzü) → yıl; pandapower yük akışıyla. Üreten betik: `scripts/ym1_hafta8_senaryolar.py`.

| KPI | S1 araç yok | S2 kontrolsüz | S3 akıllı şarj (kural tabanlı) | S4 akıllı şarj + batarya | S5 optimizasyonlu EMS | S6 V2G |
| --- | --- | --- | --- | --- | --- | --- |
| Yıllık maliyet | 524.955 TL | 1.248.705 TL | bekleniyor | bekleniyor | bekleniyor | bekleniyor |
| Yılın tepe alımı | 38 kW | 179 kW | bekleniyor | bekleniyor | bekleniyor | bekleniyor |
| Puantta alım | 41.861 kWh | 115.296 kWh | bekleniyor | bekleniyor | bekleniyor | bekleniyor |
| Araç şarjının puant payı | — | %53 | bekleniyor | bekleniyor | bekleniyor | bekleniyor |
| Yenilenebilir payı | %42 | %26 | bekleniyor | bekleniyor | bekleniyor | bekleniyor |
| Öz tüketim | %63 | %68 | bekleniyor | bekleniyor | bekleniyor | bekleniyor |
| Site sınırı (180 kW) aşımı | 0 kWh | 0 kWh | bekleniyor | bekleniyor | bekleniyor | bekleniyor |
| En düşük gerilim | 0,988 p,u, | 0,972 p,u, | bekleniyor | bekleniyor | bekleniyor | bekleniyor |
| En yüksek kablo yüklenmesi | %28 | %80 | bekleniyor | bekleniyor | bekleniyor | bekleniyor |
| En yüksek trafo yüklenmesi | %13 | %47 | bekleniyor | bekleniyor | bekleniyor | bekleniyor |

S1–S2 sahte istasyonla (20 araç, 10 ünite). S3–S6 YM-2 istasyon modeli ve YM-3 EMS'i ana koda girince aynı betikle doldurulacak.
