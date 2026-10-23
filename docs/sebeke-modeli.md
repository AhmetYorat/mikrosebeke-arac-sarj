# Şebeke modeli (pandapower)

Durum: **taslak (Hafta 3)**. Topoloji ve kablo/trafo değerleri pandapower standart tiplerinden alındı; EM-2 doğrulayacak.

Kod: [src/microgrid/grid/network.py](../src/microgrid/grid/network.py) · Parametreler: `config/default.yaml → grid.network`

```bash
python -m microgrid.grid   # tipik anlar için tek seferlik yük akışı
python -m microgrid.sim    # 24 saatlik döngü, her adımda yük akışı
```

## Ağ

```text
Şebeke (OG, 20 kV) ── Trafo 400 kVA ── AG ana pano (PCC, 0,4 kV) ─┬─ kablo "site" (150 m) ──── sabit yük, PV
                                                                  └─ kablo "station" (100 m) ─ şarj istasyonu, BESS
```

| Eleman | Değer | Kaynak |
| --- | --- | --- |
| Trafo | 0,4 MVA 20/0,4 kV, uk %6 | pandapower standart tipi |
| Kablolar | NAYY 4×150 (alüminyum), en fazla 270 A ≈ 187 kVA | pandapower standart tipi |
| Kablo boyları | site 150 m, otopark 100 m | varsayım |
| Sabit yük güç faktörü | cos φ = 0,95 | varsayım |
| EV, PV, BESS | cos φ = 1 | varsayım |
| OG gerilimi | 1,0 p.u. sabit | varsayım |

## Sonuçlar nasıl okunur

Yük akışı, verilen güçlerde her baradaki gerilimi ve her elemandaki akımı hesaplar. Bize üç sayı dönüyor:

- **Gerilim (p.u.)**: Baranın gerilimi, nominal gerilime (400 V) oranlanmış hâli. 1,00 = 400 V, 0,95 = 380 V.
  Yük çektikçe kablo ve trafodaki direnç yüzünden gerilim düşer; kablonun ucundaki bara en düşük olandır.
  Sınır: 0,95–1,05 (EN 50160). PV fazlası şebekeye geri akarken gerilim 1'in üstüne çıkabilir.
- **Kablo yüklenmesi (%)**: Kablodan geçen akımın taşıyabileceği en yüksek akıma oranı. %100 üstü kablo ısınır,
  sürekli çalışmada kabul edilmez.
- **Trafo yüklenmesi (%)**: Trafodan geçen görünür gücün (kVA) anma gücüne (400 kVA) oranı.

## İlk sonuçlar

`python -m microgrid.grid` çıktısı (sabit yükler YM-1'in BDEW profillerinden):

| Durum | En düşük gerilim | Otopark kablosu | Trafo |
| --- | --- | --- | --- |
| Haziran 13:00, PV fazlası (71 kW PV, 31 kW yük) | 1,000 (site ucu 1,007) | %0 | %10 |
| Aralık 18:00, istasyon 150 kW | 0,971 | %83 | %49 |
| Aralık 18:00, istasyon 150 kW + BESS 100 kW deşarj | 0,986 | %27 | %23 |
| Tüm üniteler aynı anda (276 kW), sınır yok | **0,947** | **%156** | %83 |

Çıkarımlar:

1. **İstasyon sınırını (150 kW) koruyan şey kablo.** Sınır kaldırılırsa otopark kablosu %156 yüklenir ve gerilim 0,95'in
   altına düşer. Kontrolsüz şarjın "sorun yarattığını" göstermenin en net yolu bu.
2. **Trafo hiçbir durumda sorun değil.** 400 kVA, sitenin 180 kW sınırının iki katından fazla. Senaryolar trafoyu değil,
   kabloyu ve gerilimi zorluyor.
3. **BESS'in istasyonun yanında olması önemli.** Deşarj eden batarya, istasyonun gücünü kabloya yüklemeden karşılıyor:
   kablo %83'ten %27'ye iniyor. Batarya ana panoda olsaydı kablo rahatlamazdı. (Yerleşim kararı EM-1/EM-2'de.)

## EM-2'ye sorular

1. OG gerilimi 20 kV mı, 34,5 kV mı? Trafo tipi ve uk değeri doğru mu?
2. Kablo kesiti ve boyları gerçekçi mi? Otopark kablosu için 4×150 yeterli mi, daha kalın mı seçilmeli?
3. BESS ve PV hangi baraya bağlanacak? (Şu an: PV site ucunda, BESS otoparkta.)
4. Sabit yük için cos φ = 0,95 uygun mu? EV şarj cihazları için cos φ = 1 kabulü yeterli mi?
5. Gerilim sınırı olarak 0,95 mi, Türkiye dağıtım yönetmeliğindeki değer mi kullanılmalı?
