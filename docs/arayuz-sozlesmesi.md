# Arayüz sözleşmesi

Durum: **taslak (Hafta 2)**. 22 Ekim toplantısında herkes kendi bölümünü onaylar; sonrasında değişiklik PR ile yapılır.

Bu doküman modüllerin birbirine **ne verip ne aldığını** tanımlar. İçini nasıl yazdığınız size kalmış; sınırdaki
fonksiyon imzası, sütun adı ve birim sabit. Böylece herkes ayrı çalışıp 5 Kasım'da (v0) parçaları takınca çalışır.

Kodda karşılığı: [src/microgrid/interfaces.py](../src/microgrid/interfaces.py) (tipler) ve
[src/microgrid/sim/loop.py](../src/microgrid/sim/loop.py) (döngü). Sahte modüllerle çalışan örnek:

```bash
python -m microgrid.sim
```

## 1. Ortak kurallar

### Birimler

| Büyüklük | Birim | Not |
| --- | --- | --- |
| Güç | kW | W veya MW kullanılmaz |
| Enerji | kWh | |
| Süre | saat (ondalık) | 15 dk = 0.25 |
| Zaman noktası | pandas `Timestamp`, `Europe/Istanbul` | "18.5" gibi ondalık saat yalnızca config'teki dağılımlarda |
| SOC | 0–1 | % kullanılmaz |
| Fiyat | TL/kWh | |
| Gerilim | p.u. | |
| Frekans | p.u. (50 Hz = 1.0) | yalnızca Simulink tarafı |

### İşaret kuralı

| Değişken | Pozitif | Negatif |
| --- | --- | --- |
| `pv_kw` | üretim | — |
| `base_load_kw` | tüketim | — |
| `ev_kw` | araç şarj oluyor | araç şebekeye veriyor (V2G) |
| `bess_kw` | batarya şarj oluyor | batarya deşarj |
| `grid_kw` | şebekeden alım | şebekeye veriş |

Güç dengesi: **`grid_kw = base_load_kw + ev_kw + bess_kw − pv_kw`**

Neden tek kural: Simulink'te, pandapower'da ve Python'da işaretler farklı olursa grafikler ters çıkar ve kimse fark
etmez. "Tüketen pozitif" kuralı her yerde aynı.

Neden şebeke gücünü EMS hesaplamıyor: Şebeke gücü bir karar değil, diğer güçlerin sonucudur. Döngü dengeden
hesaplar; böylece iki modülün farklı şebeke değeri üretmesi imkânsız olur.

### Zaman

- Adım: `simulation.step_minutes` (15 dk). Ufuk: `horizon_hours` (24 saat).
- **Temsili gün öğlen başlar** (`simulation.start: 2023-06-21 12:00`) ve ertesi gün öğlen biter. Site otoparkında
  araçlar akşam gelip sabah ayrılıyor; gece yarısında başlayan bir gün akşam gelen aracın şarjını ikiye bölerdi.
- Temsili günler: **Haziran ve Aralık'ın hafta içi ortalama günleri** (YM-1, `loads.average_day`). Simülasyon her biri
  için ayrı çalışır. Site sınırı (180 kW) yalnızca Aralık'ta aşıldığı için iki gün de gerekli. Config'teki tarih yalnızca saat
  ekseni içindir; `build_inputs` ortalama günün saatlerini bu eksene (12:00 → ertesi gün 12:00) yerleştirir.

## 2. Döngü (YM-4)

Her adımda sıra:

```text
başta bir kez:  ems.prepare(inputs)                 # tüm günün PV/yük/fiyat tahmini
her adımda:
  1. vehicles = station.requests(ctx)               # YM-2: bağlı araçlar ve sınırları
  2. decision = ems.decide(EmsInputs(...))          # YM-3: araç güçleri + batarya gücü
  3. ev      = station.apply(ctx, decision.ev_kw)   # YM-2: SOC güncelle, gerçek gücü döndür
  4. bess_kw = battery.apply(decision.bess_kw, dt)  # YM-3: sınırlara göre kırp
  5. grid_kw = denge                                 # YM-4
  6. grid.run(ctx, injections)                      # YM-4 + EM-2: yük akışı (Hafta 3'ten itibaren)
  7. kaydet
```

`apply` fonksiyonları **gerçekte uygulanan** gücü döndürür. EMS 22 kW istese bile araç dolduysa 5 kW uygulanır;
kayda geçen her zaman uygulanan değerdir.

## 3. Modül arayüzleri

### YM-1: Girdi serileri

Döngüye tek bir tablo verir: indeks `time_index(cfg)`, sütunlar:

| Sütun | Birim | Açıklama |
| --- | --- | --- |
| `pv_kw` | kW | Kurulu güce ölçeklenmiş PV üretimi |
| `base_load_kw` | kW | İstasyon dışı sabit yük (site binaları) |
| `price_tl_per_kwh` | TL/kWh | O adımın tarife fiyatı |

Beklenen fonksiyon: `build_inputs(cfg, index) -> DataFrame`.

**15 dakikaya çevirme veri katmanında yapılır** (YM-1 ile kararlaştırıldı). Döngü her zaman `step_minutes`
çözünürlüğünde tablo bekler, saatlik veriyi kendisi çevirmez.

- Güç (kW) bir **anlık değerdir**, enerji değildir: saatlik 40 kW, 15 dakikalık adımda da ~40 kW'tır.
  4'e bölmek yanlış olur; 4'e bölünen şey enerjidir (kWh).
- Ara değerleme doğrusal (`interpolate`) olsun; tekrar etmek (`ffill`) PV eğrisinde saat başı basamaklar yaratır.

**YM-1'in kendi dosyaları** (`data/processed/`, Türkiye saati): `pv_kw_per_kwp` (kW/kWp), `residential_kw`,
`commercial_kw`, `total_kw` (kW). Bu sütunlar veri katmanının içindedir; döngüye `build_inputs` şöyle çevirerek verir:

| Döngüye giden | Hesap |
| --- | --- |
| `pv_kw` | `pv_kw_per_kwp × pv.installed_kw` |
| `base_load_kw` | `total_kw` (daireler + ortak alan + dükkânlar; EM-1 kararı) |
| `price_tl_per_kwh` | config'teki tarife dilimleri |

Neden döngü dosya sütunlarını doğrudan okumuyor: veri katmanı ileride yeni bir profil eklerse ya da sütun adını
değiştirirse döngü, EMS ve dashboard etkilenmesin. Sınırda yalnızca üç sütun var; içerisi YM-1'in.

### YM-2: Şarj istasyonu (`ChargingStation`)

```python
requests(ctx) -> list[VehicleRequest]
apply(ctx, ev_kw: dict[charger_id, kW]) -> dict[charger_id, kW]
```

`VehicleRequest` alanları: `charger_id`, `vehicle_id`, `soc`, `battery_kwh`, `target_soc`, `departure`,
`max_charge_kw`, `max_discharge_kw` (V2G yoksa 0).

- Geliş/gidiş, ünite ataması ve SOC takibi istasyonun içindedir; EMS araçların listesini görür ama SOC'yi değiştirmez.
- **CC-CV eğrisi `max_charge_kw` içinde uygulanır.** SOC %80'i geçen araç için istasyon daha düşük üst sınır bildirir.
  Böylece EMS'in şarj fiziğini bilmesi gerekmez.
- `charger_id` biçimi: `AC1`…`AC8`, `DC1`, `DC2`.

### YM-3: EMS (`EMS`) ve batarya (`Battery`)

```python
prepare(forecast: DataFrame) -> None      # sütunlar: pv_kw, base_load_kw, price_tl_per_kwh
decide(inp: EmsInputs) -> Decision        # Decision(ev_kw: dict, bess_kw: float)

battery.soc: float
battery.apply(power_kw, dt_h) -> float    # uygulanan güç
```

- `EmsInputs`: `ctx`, `pv_kw`, `base_load_kw`, `price_tl_per_kwh`, `vehicles`, `bess_soc`, `station_limit_kw`, `site_limit_kw`.
- Kural tabanlı EMS `prepare`'i boş bırakır. MILP (Senaryo 5) tüm günü `prepare`'de çözer, `decide`'da o adımın
  planını okur. İki EMS de aynı arayüzle döngüye takılır; senaryo değiştirmek tek satırdır.
- İki sınır var ve ikisine uymak EMS'in işidir (EM-1 kararı):

  | Sınır | Değer | Neyi sınırlar |
  | --- | --- | --- |
  | `station_limit_kw` | 150 kW | `ev_kw`: istasyonun toplam çekişi |
  | `site_limit_kw` | 180 kW | `grid_kw`: tüm sitenin şebekeden alımı |
  | `grid.transformer_kva` | 400 kVA | fiziksel trafo; pandapower'da yüklenme % olarak görünür |

  Hangi sınırın bağlayıcı olduğu mevsime göre değişir (YM-1'in BDEW profilleri, hafta içi ortalama gün, 17–22):

  | | Sabit yük | Sabit yük + 150 kW istasyon | Bağlayıcı sınır |
  | --- | --- | --- | --- |
  | Haziran | ~24 kW | ~174 kW | istasyon (150 kW) |
  | Aralık | ~34 kW (18:00'de 38 kW) | ~188 kW | site (180 kW) |

  EMS istasyona her adımda `min(station_limit_kw, site_limit_kw − base_load_kw + pv_kw)` kadar alan bırakabilir.
- Döngü sınırları zorlamaz, çünkü Senaryo 2 (kontrolsüz) aşımı göstermek için var. Aşım KPI'da raporlanır.

### YM-4 + EM-2: Şebeke modeli (`GridModel`)

```python
run(ctx, GridInjections(pv_kw, base_load_kw, ev_kw, bess_kw)) -> GridResult
```

`GridResult`: `converged`, `min_vm_pu`, `max_vm_pu`, `max_line_loading_pct`, `trafo_loading_pct`.

Hangi gücün hangi baraya bağlandığı ağ modelinin içindedir (EM-2 ile Hafta 3). Şebeke modeli verilmezse döngü
çalışmaya devam eder, bu sütunlar boş kalır.

## 4. Çıktılar

### Adım tablosu (`SimResult.steps`)

İndeks `timestamp`, adım başına bir satır. Dashboard ve KPI modülü yalnızca bu sütunları okur.

| Sütun | Birim | Kaynak |
| --- | --- | --- |
| `pv_kw`, `base_load_kw`, `price_tl_per_kwh` | kW, kW, TL/kWh | girdi |
| `ev_kw` | kW | istasyonun uyguladığı toplam |
| `bess_kw`, `bess_soc` | kW, 0–1 | batarya |
| `grid_kw` | kW | güç dengesi |
| `cost_tl` | TL | `max(grid_kw, 0) × fiyat × dt` |
| `n_vehicles` | adet | şarj/deşarj edilebilir bağlı araç |
| `grid_converged`, `min_vm_pu`, `max_vm_pu`, `max_line_loading_pct`, `trafo_loading_pct` | —, p.u., p.u., %, % | yük akışı |

### İstasyon tablosu (`SimResult.station`)

Adım × bağlı araç başına bir satır: `timestamp`, `charger_id`, `vehicle_id`, `soc` (adım başı), `power_kw`.
Dashboard'daki istasyon görünümü (hangi ünite dolu, araçların SOC'si) buradan çizilir.

## 5. Simulink CSV formatı (EM-2 ile)

Durum: **öneri, EM-2 onayı bekleniyor.**

Dosya: `simulink/outputs/<senaryo>_<kısa_ad>.csv`, ör. `D1_yuk_basamagi.csv`, `D3_pv_dususu.csv`.

| Sütun | Zorunlu | Birim | Not |
| --- | --- | --- | --- |
| `time_s` | evet | s | artan sırada |
| `freq_pu` | evet | p.u. | 50 Hz = 1.0; örnekteki bant 0.999–1.001 |
| `v_pcc_pu` | evet | p.u. | şebeke bağlantı noktası (PCC) gerilimi |
| `p_grid_kw` | evet | kW | işaret kuralına göre: alım pozitif |
| `p_pv_kw` | hayır | kW | |
| `p_bess_kw` | hayır | kW | şarj pozitif |
| `soc_bess` | hayır | 0–1 | |
| `p_ev_ac_kw`, `p_ev_dc_kw` | hayır | kW | AC ve DC şarj dalları; V2G'de negatif |
| `p_load_kw` | hayır | kW | sabit yük |

Kurallar:

- Ayırıcı virgül, ondalık **nokta**, ilk satır başlık, UTF-8. Türkçe Excel'de açıp kaydetmeyin; ondalığı virgüle çevirir.
- Örnekleme: dosya başına en fazla ~10.000 satır. Simulink ms mertebesinde örnekliyorsa `To Workspace` bloğunda
  decimation ile seyreltin; grafikte fark görünmez, dosya küçük kalır.
- Simulink'te SOC % ve güç W çıkıyorsa dışa aktarırken çevirin. `load_simulink_csv` birim hatalarını yakalayıp
  ne yapılacağını söyler (ör. "frekans Hz görünüyor, 50'ye bölün").

MATLAB'de dışa aktarma örneği (`To Workspace` blokları "Timeseries" biçiminde):

```matlab
% f: frekans (Hz), v: PCC gerilimi (p.u.), p_grid: şebeke gücü (W). Modelinizdeki birime göre bölenleri değiştirin.
T = table(f.Time, f.Data / 50, v.Data, p_grid.Data / 1e3, ...
    'VariableNames', {'time_s', 'freq_pu', 'v_pcc_pu', 'p_grid_kw'});
writetable(T, 'simulink/outputs/D1_yuk_basamagi.csv');
```

Python tarafında okuma: `from microgrid.simulink_io import load_simulink_csv`.

## 6. Açık sorular

1. **Temsili gün:** Hangi tarih(ler)? (YM-1, herkes)
2. **Şebekeye satış:** PV fazlası şebekeye satılıyor mu, hangi fiyattan? Şimdilik maliyete yalnızca alım giriyor. (YM-1, YM-3)
3. **Simulink sütunları:** EM-2 modelde bu sinyalleri ölçebiliyor mu, eksik ya da fazla olan var mı? (EM-2)
4. **Bara yerleşimi:** PV, BESS ve istasyon aynı barada mı, ayrı barada mı? Gerilim düşümü sonucunu doğrudan
   etkiler. (EM-1, EM-2)
5. ~~**Sabit yük:** konut mu, toplam mı?~~ Karar (EM-1): `total_kw`. Site 50 daire (120 MWh/yıl) + ortak alan ve
   dükkânlar (80 MWh/yıl) = 200 MWh/yıl, araç şarjı hariç. Ölçek config'te `loads:` altında (YM-1).
