# Senaryolar arası karşılaştırma (yıllık)

Bandırma, 24 temsili gün (4 mevsim × 2 gün tipi × 3 gökyüzü) → yıl; pandapower yük akışıyla. Üreten betik: `scripts/ym1_hafta8_senaryolar.py`.

| KPI | S1 Temel (araç yok) | S2 Kontrolsüz şarj | S3 Akıllı şarj (geçici) | S4 akıllı şarj + batarya | S5 optimizasyonlu EMS | S6 V2G |
| --- | --- | --- | --- | --- | --- | --- |
| Yıllık maliyet | 524.955 TL | 1.248.705 TL | 999.098 TL | bekleniyor | bekleniyor | bekleniyor |
| Yılın tepe alımı | 38 kW | 179 kW | 153 kW | bekleniyor | bekleniyor | bekleniyor |
| Puantta alım | 41.861 kWh | 115.296 kWh | 41.861 kWh | bekleniyor | bekleniyor | bekleniyor |
| Araç şarjının puant payı | — | %53 | %1 | bekleniyor | bekleniyor | bekleniyor |
| Yenilenebilir payı | %42 | %26 | %26 | bekleniyor | bekleniyor | bekleniyor |
| Öz tüketim | %63 | %68 | %68 | bekleniyor | bekleniyor | bekleniyor |
| Site sınırı (180 kW) aşımı | 0 kWh | 0 kWh | 0 kWh | bekleniyor | bekleniyor | bekleniyor |
| En düşük gerilim | 0,988 p.u. | 0,972 p.u. | 0,976 p.u. | bekleniyor | bekleniyor | bekleniyor |
| En yüksek kablo yüklenmesi | %28 | %80 | %68 | bekleniyor | bekleniyor | bekleniyor |
| En yüksek trafo yüklenmesi | %13 | %47 | %39 | bekleniyor | bekleniyor | bekleniyor |

- S1 Temel (araç yok): Karşılaştırma tabanı: istasyon boş, yalnızca PV + sabit yük + şebeke.
- S2 Kontrolsüz şarj: Araç geldiği an tam güçle şarj olur, batarya kullanılmaz. Sorunun görüldüğü senaryo. **Geçici:** sahte modülle çalışıyor.
- S3 Akıllı şarj (geçici): Gece tarifesine kaydırma + PV fazlası + sınırlara uyum. GEÇİCİ: YM-4'ün referans kuralı; YM-3'ün kural tabanlı EMS'i gelince onunla değiştirilecek.

"bekleniyor" sütunları YM-2 istasyon modeli ve YM-3 EMS'i senaryo listesine eklenince aynı betikle dolacak.
