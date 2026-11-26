# YM-2 Şarj İstasyonu (Hafta 3–10) Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** YM-2'nin Hafta 3–10 görevlerini tamamlamak: sözleşmedeki `requests/apply` arayüzünü uygulayan gerçek şarj istasyonunu döngüye ve dashboard'a bağlamak (MockStation'ın yerine), ardından tepe yük analizi, akıllı şarj desteği, optimizasyon kısıtları, V2G, rapor ve sunum bölümleri.

**Architecture:** Sude'nin Hafta 2 sınıfları (`ElectricVehicle`, `ChargingUnit`, `ChargingStation`, `DemandModel`) adlarıyla korunur, içleri sözleşmeye göre yeniden yazılır. İstasyon `MockStation` ile aynı kurucuyu alır (`cfg, start, seed`), böylece `sim/scenarios.py` ve `sim/__main__.py`'de tek satırla takılır. Bütün parametreler `config/default.yaml`'dan okunur; analiz, strateji ve V2G ayrı küçük dosyalardadır.

**Tech Stack:** Python ≥ 3.10, numpy, pandas, pytest (yeni bağımlılık yok).

**Spec:** Bu planın dayandığı kaynaklar:
- Haftalık İş Planı (`Haftalik_Is_Plani.pdf`, `origin/ym3/ems-week1-2` branch'inde), YM-2 satırları:
  - H3: ChargingStation v1: araç üretimi, ünitelere atama, kontrolsüz şarj, CC-CV eğrisi · birim testleri
  - H4: İstasyonu döngüye bağla; istasyon toplam gücü ve ünite bazlı çıktılar
  - H5: Kontrolsüz şarjda araç sayısına göre tepe yük analizi · kritik anın tespiti → EM-1'e ilet
  - H6: Akıllı şarj desteği: ünite güç modülasyonu, ayrılış saatine göre önceliklendirme · kullanıcı memnuniyeti KPI'ı (hedef SOC'ye ulaşma oranı)
  - H7: İstasyon kısıtlarını optimizasyona aktar: ünite güç limiti, ayrılış zamanı, hedef SOC
  - H8: V2G: araç deşarj kuralı, minimum SOC garantisi, ayrılışta hedef SOC
  - H9: Şarj istasyonu rapor bölümü (model ayrıntıları + sonuçlar) · 9 Aralık kod dondurma
  - H10: Rapor: şarj istasyonu; sunumun istasyon slaytları
- `docs/arayuz-sozlesmesi.md` bölüm 2 ve "YM-2: Şarj istasyonu" (bağlayıcı arayüz) ve `src/microgrid/interfaces.py`.
- Sude'nin 22.11.2026 kararları: (1) H2 sınıfları yeniden düzenlenir, adları korunur; (2) geliş/gidiş/SOC dağılımları config'ten, araç kataloğu (Zoe, Tesla, Togg, Ioniq 5, e-208) config'e eklenir; (3) ünite bulamayan araç FIFO sıraya girer, hedefe ulaşan araç sıra varsa üniteyi bırakır (nöbetleşe şarj, config'ten kapatılabilir).

Not: Yüklenen `YMM4142_P8_*.pdf` dosyaları başka bir dersin (Optimizasyon Teorisi, eşikleme) planıdır; bu planda kullanılmadı.

## Global Constraints

- Birimler: güç kW, enerji kWh, süre ondalık saat, SOC 0–1, fiyat TL/kWh. Zaman noktaları `Europe/Istanbul` saat dilimli `pd.Timestamp`.
- İşaret: `ev_kw > 0` araç şarj oluyor, `< 0` araç şebekeye veriyor (V2G). İstasyondaki tüm güçler **şebeke tarafı** güçtür; bataryaya giren enerji `p · dt · η`, V2G'de bataryadan çıkan `p · dt / η` (η = `station.charge_efficiency`).
- `charger_id` biçimi: `AC1`…`AC8`, `DC1`, `DC2` (config'teki `station.chargers` sırasıyla, her tip kendi içinde 1'den numaralanır).
- Parametreler koda gömülmez; `config/default.yaml`'dan okunur. Rastgelelik `np.random.default_rng(seed)`.
- Arayüz: `requests(ctx) -> list[VehicleRequest]`, `apply(ctx, ev_kw: dict[str, float]) -> dict[str, float]` (uygulanan güç). Bu imzalar ve `VehicleRequest` alanları değişmez.
- Kod, docstring ve yorumlar Türkçe; repodaki üslupla. `pytest` her commit'te yeşil.
- Git: yalnız `claude/funny-lamport-02vprw` branch'ine commit/push. Commit'ler Sude adına atılır (yazar: Sude'nin önceki commit'lerindeki ad/e-posta, `git log origin/ym2/hafta-1-2`). Commit mesajı biçimi: `YM-2 Hafta N: ...`.
- 9 Aralık kod dondurma: Task 1–8 kodu bu tarihten önce birleşmiş olmalı.

## Review Focus

1. **Bilinmeyen veya boş üniteye güç gelmesi:** EMS `ev_kw`'de araç bağlı olmayan ya da var olmayan bir `charger_id` gönderirse istasyon hata vermeden yok sayar, o üniteye 0 uygular (Task 2 testi).
2. **Kayan nokta ile hedefe "neredeyse" ulaşma:** SOC 0.7999999 iken hedef 0.8 sayılmalı; aksi hâlde nöbetleşe şarj hiç tetiklenmez, araç sonsuza dek 1e-7 kWh ister. Tek tolerans sabiti `SOC_TOL = 1e-6` her yerde kullanılır (Task 3 testi).
3. **Dağılım kuyrukları:** Normal dağılımdan çok erken/geç geliş veya ayrılıştan önce geliş; araç hiçbir zaman negatif süre kalmamalı, simülasyon penceresinin dışına taşmamalı (Task 1 testi).
4. **Mevcut S3 testi gerçek istasyonla:** `tests/test_scenarios.py::test_s3_moves_charging_out_of_puant_without_new_peak` MockStation'a göre yazıldı; OBC 11 kW sınırı ve nöbetleşe şarj sonucu değiştirebilir. Kırılırsa assertion sessizce gevşetilmez; sebep raporlanır ve YM-4'e iletilecek not PR açıklamasına yazılır (Task 4).
5. **Araç sayısı uçları:** `vehicles.count: 0` (S1) ve ünite sayısından çok araç (ör. 40) döngüyü çökertmemeli; 0'da istasyon tablosu boş, 40'ta sırada bekleyenler `sessions()`'da görünür (Task 3 ve Task 5 testleri).

---

## Dosya Yapısı

| Dosya | Sorumluluk |
| --- | --- |
| `config/default.yaml` | `station:` altına `charge_efficiency`, `cv_threshold_soc`, `cv_min_fraction`, `rotate_when_full`, `v2g_enabled`; `vehicles:` altına `fleet` kataloğu, `v2g_min_soc` |
| `src/microgrid/station/vehicle.py` | `ElectricVehicle` (durum + fizik), `cc_cv_limit` |
| `src/microgrid/station/demand_model.py` | `DemandModel`: config'ten araç filosu üretimi |
| `src/microgrid/station/charging_unit.py` | `ChargingUnit`: tek ünite, bağlı araç, güç sınırları |
| `src/microgrid/station/charging_station.py` | `ChargingStation`: `requests/apply`, FIFO sıra, nöbetleşe şarj, `sessions()`, `planned_sessions()` |
| `src/microgrid/station/strategies.py` | `uncontrolled`, `by_departure` (EMS'in çağırabileceği güç dağıtım yardımcıları), `satisfaction` KPI'ı |
| `src/microgrid/station/analysis.py` | `peak_vs_vehicle_count`, `critical_station_snapshot` |
| `src/microgrid/station/__init__.py` | Dışa açılan adlar |
| `src/microgrid/sim/scenarios.py`, `sim/loop.py`, `sim/__main__.py` | Varsayılan istasyonu değiştirme, `SimResult.sessions` |
| `tests/test_station_vehicle.py`, `test_station_demand.py`, `test_station.py`, `test_station_strategies.py`, `test_station_analysis.py`, `test_station_v2g.py` | Birim testleri |
| `scripts/ym2_hafta5_tepe_yuk.py` | H5 grafiği ve kritik an tablosu |
| `docs/arayuz-sozlesmesi.md`, `docs/SINIF_DIYAGRAMI.md`, `docs/PARAMETRE_TABLOSU_VE_ARAYUZ.md` | Sözleşme ve tasarım belgelerinin güncellenmesi |
| `docs/raporlar/hafta3-7-ym2-raporu.md`, `hafta8-ym2-raporu.md`, `hafta9-ym2-raporu.md` | Haftalık raporlar |
| `docs/rapor/sarj-istasyonu.md`, `docs/sunum/ym2-istasyon-slaytlari.md` | Final rapor bölümü ve slayt içeriği |

---

### Task 0: Hafta 1–2 çalışmasını branch'e almak

**Files:**
- Merge: `origin/ym2/hafta-1-2` → `claude/funny-lamport-02vprw`
- Delete: `.vscode/settings.json`, `docs/mermaid-diagram-2026-10-16-140115.png` (aynı içerik `docs/raporlar/sinif-diyagrami.png` olarak duruyor), `docs/diagram_preview.html`

Neden merge (cherry-pick değil): Sude'nin 16–17 Ekim commit'leri geçmişte kalsın; "17 Ekim'den beri commit yok" eleştirisine karşı H1–H2 emeği görünür olur.

- [ ] **Step 1:** `git merge --no-ff origin/ym2/hafta-1-2`. Çakışmalarda `dashboard/app.py`, `docs/kapsam.md`, `docs/hocaya-sorular.md` için `main` tarafı alınır (`git checkout --ours <dosya>`); bu üç dosyadaki H2 değişiklikleri zaten main'de daha güncel hâliyle var.
- [ ] **Step 2:** Yukarıdaki üç fazla dosyayı sil; `.vscode/` satırını `.gitignore`'a ekle.
- [ ] **Step 3:** `pytest -q` → Expected: tümü PASS (eski `tests/test_station.py` eski API'yi test ettiği için de geçer).
- [ ] **Step 4:** Commit: `YM-2 Hafta 1-2: tasarım çalışmasını güncel main ile birleştir`.

---

### Task 1 (H3): Araç modeli, CC-CV ve talep modeli

**Files:**
- Modify: `config/default.yaml` (`station:`, `vehicles:`)
- Rewrite: `src/microgrid/station/vehicle.py`, `src/microgrid/station/demand_model.py`
- Test: `tests/test_station_vehicle.py`, `tests/test_station_demand.py`
- Delete: `tests/test_station.py` (eski API testi; Task 2'de yeni hâliyle yazılır)

**Interfaces:**
- Produces:
  - `SOC_TOL: float = 1e-6` (vehicle.py)
  - `cc_cv_limit(soc: float, p_nom_kw: float, threshold: float, min_fraction: float) -> float` — `soc < threshold` ise `p_nom_kw`; değilse `p_nom_kw · max(min_fraction, (1 − soc) / (1 − threshold))`.
  - `@dataclass ElectricVehicle`: `vehicle_id: str, model_name: str, battery_kwh: float, soc_arrival: float, target_soc: float, arrival: pd.Timestamp, departure: pd.Timestamp, max_ac_kw: float, max_dc_kw: float, v2g_capable: bool`; durum alanları `soc: float` (= `soc_arrival`), `charger_id: str | None = None`, `ever_connected: bool = False`, `energy_in_kwh: float = 0.0` (şebeke tarafı, şarj), `energy_out_kwh: float = 0.0` (şebeke tarafı, V2G).
    - `energy_needed_kwh -> float` (property, batarya tarafı, ≥ 0)
    - `reached_target -> bool` (property, `soc >= target_soc − SOC_TOL`)
    - `max_charge_kw(kind: str, unit_kw: float, threshold: float, min_fraction: float) -> float` — AC: `min(max_ac_kw, unit_kw)`, DC: `min(max_dc_kw, unit_kw)`, sonra `cc_cv_limit`; hedefe ulaşmışsa 0.
    - `charge(p_kw: float, dt_h: float, eff: float) -> float` — `p ≥ 0` kabul eder, `soc += p·dt·eff/B`, `energy_in_kwh += p·dt`, uygulanan `p`'yi döndürür (sınırlama burada değil, istasyonda yapılır).
  - `DemandModel(cfg: dict, seed: int = 0)`, `.generate_fleet(start: pd.Timestamp) -> list[ElectricVehicle]` (gelişe göre sıralı, kimlikler `EV01`, `EV02`…).
- Config eklemeleri (değerler aynen):
  ```yaml
  station:
    charge_efficiency: 0.95      # şebeke → batarya (H2 parametre tablosu)
    cv_threshold_soc: 0.8        # CC → CV geçişi
    cv_min_fraction: 0.15        # CV fazında gücün inebileceği en düşük oran
    rotate_when_full: true       # hedefe ulaşan araç, sırada bekleyen varsa üniteyi bırakır (nöbetleşe şarj)
    v2g_enabled: false           # Senaryo 6 true yapar
  vehicles:
    v2g_min_soc: 0.3             # V2G'de araç bu SOC'nin altına indirilmez
    fleet:                       # H2 araç kataloğu; share toplamı 1. Yoksa tüm araçlar battery_kwh, AC 22 / DC 50 kW, V2G yok
      - {model: "Renault Zoe E-Tech",    battery_kwh: 52.0, max_ac_kw: 22, max_dc_kw: 50,  v2g: false, share: 0.25}
      - {model: "Tesla Model 3 SR+",     battery_kwh: 60.0, max_ac_kw: 11, max_dc_kw: 170, v2g: true,  share: 0.30}
      - {model: "Togg T10X Uzun Menzil", battery_kwh: 88.5, max_ac_kw: 22, max_dc_kw: 150, v2g: false, share: 0.25}
      - {model: "Hyundai Ioniq 5",       battery_kwh: 77.4, max_ac_kw: 11, max_dc_kw: 220, v2g: true,  share: 0.10}
      - {model: "Peugeot e-208",         battery_kwh: 50.0, max_ac_kw: 11, max_dc_kw: 100, v2g: false, share: 0.10}
  ```
  `vehicles.battery_kwh: 60` kalır (MockStation ve katalogsuz durum kullanır).
- Talep modeli kuralları: `day = start.normalize()`; geliş = `day + N(arrival_hour)` saat, `[start, start + 12 h)` aralığına kırpılır; ayrılış = `day + 24 h + N(departure_hour)` saat, `[geliş + 1 h, start + horizon_hours]` aralığına kırpılır; `soc_arrival ~ U(arrival_soc.min, arrival_soc.max)`; `target_soc = vehicles.target_soc`; model `rng.choice(fleet, p=shares)`.

- [ ] **Step 1: Failing testleri yaz**

```python
# tests/test_station_vehicle.py
def test_cc_cv_full_power_below_threshold():      assert cc_cv_limit(0.5, 22, 0.8, 0.15) == 22
def test_cc_cv_tapers_linearly():                 assert cc_cv_limit(0.9, 22, 0.8, 0.15) == pytest.approx(11.0)
def test_cc_cv_floor():                           assert cc_cv_limit(0.99, 22, 0.8, 0.15) == pytest.approx(3.3)
def test_obc_limits_ac_unit():                    # max_ac_kw=11 araç, 22 kW AC ünite -> 11
def test_dc_uses_vehicle_dc_limit():              # max_dc_kw=170 araç, 50 kW DC ünite -> 50
def test_full_vehicle_requests_nothing():         # soc = target - 1e-9 -> reached_target True, max_charge_kw == 0
def test_charge_updates_soc_with_efficiency():    # B=60, p=22, dt=0.25, eff=0.95 -> soc artışı 22*0.25*0.95/60
```

```python
# tests/test_station_demand.py
def test_fleet_size_and_ids(cfg):                 # len == cfg vehicles.count; ids EV01..EV20; gelişe göre sıralı
def test_times_inside_window(cfg):                # 2000 araç: start <= arrival < start+12h; arrival+1h <= departure <= start+24h
def test_soc_ranges_and_target(cfg):              # soc_arrival in [0.2, 0.6]; target_soc == 0.8
def test_fleet_shares(cfg):                       # 2000 araçta model oranları share ± 0.03
def test_without_fleet_key_uses_battery_kwh(cfg): # fleet silinince hepsi 60 kWh, max_ac 22, v2g False
def test_same_seed_same_fleet(cfg):               # iki üretim aynı; farklı seed farklı
def test_zero_vehicles(cfg):                      # vehicles.count=0 -> []
```
(`cfg` fixture'ı `load_config()`; 2000 araçlık testlerde `apply_overrides(cfg, {"vehicles.count": 2000})`.)

- [ ] **Step 2:** `pytest tests/test_station_vehicle.py tests/test_station_demand.py -q` → Expected: FAIL (`ImportError: cc_cv_limit`).
- [ ] **Step 3:** Config'i ve iki dosyayı yukarıdaki imzalarla yaz. Eski `ElectricVehicle` alanları (`current_soc`, float saatler, `discharge`) kaldırılır; `discharge` Task 8'de geri gelir.
- [ ] **Step 4:** Aynı komut → PASS. Ardından `pytest -q` (eski `tests/test_station.py` bu noktada kırılır; Task 2'de yeniden yazılacağı için bu task'ta silinir).
- [ ] **Step 5:** Commit: `YM-2 Hafta 3: araç modeli, CC-CV eğrisi, config'ten talep modeli ve araç kataloğu`.

---

### Task 2 (H3): Ünite ve istasyon: `requests/apply`, atama, kontrolsüz şarj

**Files:**
- Rewrite: `src/microgrid/station/charging_unit.py`, `src/microgrid/station/charging_station.py`, `src/microgrid/station/__init__.py`
- Rewrite: `tests/test_station.py`
- Delete: `scripts/ym2_istasyon_demo.py` (eski API'yi kullanıyor; yerine Task 5 betiği gelir)

**Interfaces:**
- Consumes: Task 1'deki `ElectricVehicle`, `DemandModel`, `SOC_TOL`.
- Produces:
  - `ChargingUnit(charger_id: str, kind: str, power_kw: float)`; `vehicle: ElectricVehicle | None`; `connect(v)`, `disconnect() -> ElectricVehicle`, `max_charge_kw(threshold, min_fraction) -> float` (boşsa 0).
  - `ChargingStation(cfg: dict, start: pd.Timestamp, seed: int = 0)` — `MockStation` ile aynı kurucu.
    - `units: dict[str, ChargingUnit]` (sıra: config sırası), `vehicles: list[ElectricVehicle]`, `queue: list[ElectricVehicle]` (FIFO)
    - `requests(ctx: StepContext) -> list[VehicleRequest]`
    - `apply(ctx: StepContext, ev_kw: dict[str, float]) -> dict[str, float]`
- `requests` sırası (her adım): (1) `departure <= ts` olan bağlı araçlar üniteden ayrılır, bekleyenler sıradan düşer; (2) `arrival <= ts < departure` olup henüz gelmemiş sayılan araçlar sıranın sonuna eklenir; (3) sıranın başındaki araçlar boş ünitelere bağlanır: önce boş AC, AC kalmadıysa boş DC; (4) bağlı ve hedefe ulaşmamış araçlar için `VehicleRequest` döner (`max_discharge_kw` şimdilik 0). `departure` alanı aracın ayrılış zamanıdır.
- `apply`: istek listesindeki her ünite için `p = ev_kw.get(id, 0)`; `p > 0` ise `min(p, ünite.max_charge_kw, (target − soc)·B/(dt·η))`; `p ≤ 0` ise 0 (V2G Task 8'de). Bağlı her ünite için uygulanan güç döner; bilinmeyen anahtarlar yok sayılır.

- [ ] **Step 1: Failing testleri yaz** (`tests/test_station.py`; araçlar elle kurulmuş küçük filolarla — `station.vehicles`'ı test içinde kendi `ElectricVehicle` listesiyle değiştiren bir `make_station(cfg, vehicles)` yardımcısı)

```python
def test_charger_ids(cfg):                        # list(station.units) == ["AC1",...,"AC8","DC1","DC2"]
def test_vehicle_visible_only_while_parked(cfg):  # geliş öncesi 0 istek, geliş adımında 1, ayrılış adımında 0
def test_ac_filled_before_dc(cfg):                # aynı anda gelen 9 araç -> AC1..AC8 ve DC1
def test_queue_when_full(cfg):                    # aynı anda 11 araç -> 10 bağlı, len(queue) == 1
def test_apply_clips_to_obc_and_room(cfg):        # 11 kW'lık araca 22 istenince 11; hedefe 2 kWh kalmışsa 2/(0.25*0.95)
def test_apply_ignores_unknown_and_empty_units(cfg):   # {"AC7": 22, "XX9": 5} (AC7 boş) -> hata yok, toplamda 0
def test_negative_power_rejected_without_v2g(cfg):     # {"AC1": -10} -> 0, soc değişmez
def test_energy_conservation_over_a_day(cfg):     # mock_inputs + UncontrolledEMS ile run(): Σ ev_kw·dt·η == Σ (soc_son − soc_ilk)·B
def test_runs_in_loop_and_respects_unit_power(cfg):    # run(...) STATION_COLUMNS; power_kw <= ünite gücü
```

- [ ] **Step 2:** `pytest tests/test_station.py -q` → FAIL.
- [ ] **Step 3:** İki sınıfı ve `__init__.py`'yi yaz (`ChargingStation, ChargingUnit, ElectricVehicle, DemandModel, cc_cv_limit, SOC_TOL` dışa açılır). Eski `bagli_araclar`, `apply_power_allocations`, `get_total_power_kw`, `get_dashboard_state`, `UnitStatus`, `min_power_kw` kaldırılır (toplam güç ve ünite görünümü döngünün `SimResult.station` tablosundan gelir).
- [ ] **Step 4:** `pytest -q` → PASS.
- [ ] **Step 5:** Commit: `YM-2 Hafta 3: ChargingStation v1 sözleşmedeki requests/apply arayüzüyle`.

---

### Task 3 (H3/H6): FIFO sıra, nöbetleşe şarj ve oturum tablosu

**Files:**
- Modify: `src/microgrid/station/charging_station.py`
- Test: `tests/test_station.py`

**Interfaces:**
- Produces:
  - `requests` adım (1)'den sonra: `rotate_when_full` açıksa ve sıra boş değilse, `reached_target` olan bağlı araçlar üniteden çıkarılır (`charger_id = None`, araç otoparkta kalır, sıraya dönmez).
  - `ChargingStation.sessions() -> pd.DataFrame` — araç başına bir satır, sütunlar tam olarak:
    `vehicle_id, model, battery_kwh, arrival, departure, first_charger, connected_at, soc_arrival, soc_final, target_soc, energy_kwh, reached_target, waited_h`
    (`first_charger`/`connected_at` hiç bağlanmadıysa `None`/`NaT`; `energy_kwh` = `energy_in_kwh − energy_out_kwh`, şebeke tarafı; `waited_h` = `(connected_at − arrival)` saat, bağlanmadıysa `(departure − arrival)`).

- [ ] **Step 1: Failing testler**

```python
def test_full_vehicle_frees_unit_for_queue(cfg):        # 11 araç, biri hedefe çok yakın; birkaç adım sonra sıradaki onun ünitesine bağlanır
def test_no_rotation_when_disabled(cfg):                # station.rotate_when_full=false -> dolu araç ayrılışa kadar ünitede
def test_no_rotation_when_queue_empty(cfg):             # sıra boşken dolu araç ünitede kalır
def test_almost_full_counts_as_reached(cfg):            # soc = target − 1e-9 -> rotasyon tetiklenir (Review Focus 2)
def test_sessions_columns_and_rows(cfg):                # run() sonrası len == vehicles.count, sütunlar yukarıdaki liste
def test_never_connected_vehicle_in_sessions(cfg):      # vehicles.count=40 -> bağlanamayanlar first_charger None, energy_kwh 0, reached_target False
def test_default_day_serves_everyone(cfg):              # varsayılan config + UncontrolledEMS: tüm araçlar bağlanmış (connected_at notna)
```

- [ ] **Step 2:** `pytest tests/test_station.py -q` → yeni testler FAIL.
- [ ] **Step 3:** Rotasyonu ve `sessions()`'ı yaz.
- [ ] **Step 4:** `pytest -q` → PASS. `test_default_day_serves_everyone` FAIL ederse sebep (ör. akşam geç gelen aracın sırası sabaha kalıyor) incelenir; rotasyon kuralı değiştirilmez, test beklentisi gerçek davranışa göre ve gerekçesi yorumla yazılır.
- [ ] **Step 5:** Commit: `YM-2 Hafta 3: sıra, nöbetleşe şarj ve oturum tablosu`.

---

### Task 4 (H4): İstasyonu döngüye, senaryolara ve dashboard'a bağlamak

**Files:**
- Modify: `src/microgrid/sim/loop.py` (`SimResult`'a `sessions: pd.DataFrame = field(default_factory=pd.DataFrame)`)
- Modify: `src/microgrid/sim/scenarios.py` (varsayılan `station = lambda cfg, start: ChargingStation(cfg, start)`; S2 `temporary=False`; `simulate` istasyonu değişkende tutar ve `result.sessions = station.sessions()` atar; modül docstring'i güncellenir)
- Modify: `src/microgrid/sim/__main__.py` (`MockStation` → `ChargingStation`; özet çıktısına "hedefe ulaşan araç: x/y" satırı)
- Modify: `README.md` ("istasyon ve EMS henüz sahte" cümlesi → "EMS henüz sahte"), `docs/arayuz-sozlesmesi.md` (YM-2 bölümüne: AC-önce atama, sıra/nöbetleşe kuralı, `SimResult.sessions` sütunları, şebeke tarafı güç ve η notu)
- Test: `tests/test_scenarios.py`

**Interfaces:**
- Consumes: Task 2–3'teki `ChargingStation(cfg, start)` ve `sessions()`.
- Produces: `SimResult.sessions` (Task 3 sütunları; S1'de boş tablo). `MockStation` silinmez (`test_loop.py`, `test_v0.py` kullanıyor).

- [ ] **Step 1: Failing testler** (`tests/test_scenarios.py`)

```python
def test_default_station_is_real(cfg):        # SCENARIOS["S2 Kontrolsüz şarj"].station(cfg, start) isinstance ChargingStation
def test_s2_not_temporary():                  # SCENARIOS["S2 Kontrolsüz şarj"].temporary is False
def test_s2_has_sessions(cfg):                # simulate(...).sessions satır sayısı == vehicles.count
def test_s1_sessions_empty(cfg):              # S1'de sessions boş, ev_kw hep 0 (Review Focus 5)
```

- [ ] **Step 2:** `pytest tests/test_scenarios.py -q` → FAIL.
- [ ] **Step 3:** Dosyaları değiştir.
- [ ] **Step 4:** `pytest -q` → PASS. Özellikle `test_s3_moves_charging_out_of_puant_without_new_peak` ve `tests/test_dashboard.py` (Review Focus 4). S3 testi kırılırsa: hangi assertion, hangi sayı, neden (OBC sınırı / rotasyon) not edilir; test değiştirilmez, Sude'ye ve PR açıklamasına "YM-4'e not" olarak yazılır.
- [ ] **Step 5:** `python -m microgrid.sim --mock` → istasyon tepe ve "hedefe ulaşan araç" satırı basılır; `streamlit run dashboard/app.py` başsız açılır (`tests/test_dashboard.py` yeterli kanıt).
- [ ] **Step 6:** Commit: `YM-2 Hafta 4: gerçek istasyon döngüde, S2 artık sahte değil`.

---

### Task 5 (H5): Araç sayısına göre tepe yük ve kritik an

**Files:**
- Create: `src/microgrid/station/analysis.py`, `scripts/ym2_hafta5_tepe_yuk.py`
- Test: `tests/test_station_analysis.py`
- Output: `docs/raporlar/hafta5-ym2-tepe-yuk.png`

**Interfaces:**
- Consumes: `scenarios.simulate`, `scenarios.SCENARIOS["S2 Kontrolsüz şarj"]`, `apply_overrides`.
- Produces:
  - `peak_vs_vehicle_count(cfg: dict, inputs: pd.DataFrame, counts: list[int]) -> pd.DataFrame` — S2 ile her sayı için bir satır; sütunlar: `arac_sayisi, istasyon_tepe_kw, istasyon_tepe_saati, sebeke_tepe_kw, site_siniri_asim_adim, hedefe_ulasma_orani`.
  - `critical_station_snapshot(result: SimResult, cfg: dict) -> dict` — `ev_kw`'nin en yüksek olduğu adım için: `zaman` (`"%d.%m %H:%M"`), `istasyon_kw`, `sarj_olan_ac`, `sarj_olan_dc`, `bagli_arac`, `ortalama_soc` (o adımda bağlı araçların SOC ortalaması). Bu, H2 parametre belgesindeki "EM-1/EM-2'ye iletilecek kritik an" (bölüm D) maddesidir; YM-4'ün `simulink_io.critical_moment`'ı şebeke alımına bakar, bu istasyona bakar.
- Betik: Haziran ve Aralık için `counts = [0, 5, 10, 15, 20, 30, 40]`; `load_inputs` (veri yoksa sahte girdi ve grafikte "SAHTE GİRDİ" uyarısı); iki panelli PNG (araç sayısı → istasyon tepe ve şebeke tepe, 150 kW istasyon ve 180 kW site sınırı yatay çizgi) ve kritik an tablosunu konsola Markdown olarak basar.

- [ ] **Step 1: Failing testler** (girdi: `mock_inputs`)

```python
def test_zero_vehicles_zero_peak(cfg):        # counts=[0] -> istasyon_tepe_kw == 0
def test_more_vehicles_higher_peak(cfg):      # counts=[5, 20] -> tepe(20) > tepe(5)
def test_many_vehicles_do_not_crash(cfg):     # counts=[40] -> satır var, hedefe_ulasma_orani in [0, 1]
def test_snapshot_matches_steps(cfg):         # snapshot istasyon_kw == steps.ev_kw.max(); sarj_olan_ac + sarj_olan_dc <= bagli_arac
```

- [ ] **Step 2:** `pytest tests/test_station_analysis.py -q` → FAIL.
- [ ] **Step 3:** `analysis.py` ve betiği yaz.
- [ ] **Step 4:** `pytest -q` → PASS; `python scripts/ym2_hafta5_tepe_yuk.py` → PNG oluşur, tablo basılır.
- [ ] **Step 5:** Commit: `YM-2 Hafta 5: araç sayısına göre tepe yük ve istasyon kritik anı`.

---

### Task 6 (H6): Akıllı şarj desteği ve kullanıcı memnuniyeti KPI'ı

**Files:**
- Create: `src/microgrid/station/strategies.py`
- Test: `tests/test_station_strategies.py`

**Interfaces:**
- Produces (YM-3'ün EMS'i ve YM-1'in KPI tablosu çağırır):
  - `uncontrolled(vehicles: list[VehicleRequest], dt_h: float) -> dict[str, float]` — her araca `min(max_charge_kw, energy_needed_kwh / dt_h)`.
  - `by_departure(vehicles: list[VehicleRequest], budget_kw: float, dt_h: float) -> dict[str, float]` — ayrılışı en yakın araçtan başlayarak her birine `min(max_charge_kw, energy_needed_kwh / dt_h, kalan bütçe)`; eşit ayrılışta daha çok enerji isteyen önce. Bütçe 0 veya negatifse herkese 0. ("Ünite güç modülasyonu": `apply` 0 ile üst sınır arasındaki her değeri kabul eder; bu fonksiyon modülasyonun kuralını verir.)
  - `satisfaction(sessions: pd.DataFrame) -> pd.Series` — anahtarlar ve birimler: `arac_sayisi` (adet), `hedefe_ulasma_orani` (0–1), `hizmet_alamayan` (adet, hiç bağlanamayan), `ortalama_eksik_kwh` (kWh, `max(0, target − soc_final)·B` ortalaması), `ortalama_bekleme_saat` (saat). Boş tabloda oranlar `nan`, sayılar 0.

- [ ] **Step 1: Failing testler**

```python
def test_uncontrolled_gives_full_power():         # 2 araç, ihtiyaç bol -> max_charge_kw
def test_by_departure_prioritizes_earliest():     # bütçe 22, ikisi 22 kW isteyebiliyor -> erken ayrılan 22, diğeri 0
def test_by_departure_never_exceeds_budget():     # rastgele 10 araç, Σ <= bütçe + 1e-9; her biri <= max_charge_kw
def test_by_departure_large_budget_equals_uncontrolled()
def test_by_departure_zero_budget():              # bütçe 0 ve -5 -> hepsi 0
def test_satisfaction_known_values():             # elle 4 satırlık sessions -> oran 0.5, hizmet_alamayan 1, eksik ve bekleme beklenen değer
def test_satisfaction_empty():                    # boş tablo -> arac_sayisi 0, oran nan
```

- [ ] **Step 2:** `pytest tests/test_station_strategies.py -q` → FAIL.
- [ ] **Step 3:** `strategies.py`'yi yaz; `__init__.py`'ye ekle.
- [ ] **Step 4:** `pytest -q` → PASS.
- [ ] **Step 5:** Commit: `YM-2 Hafta 6: ayrılışa göre güç dağıtımı ve kullanıcı memnuniyeti KPI'ı`.

---

### Task 7 (H7): İstasyon kısıtlarını optimizasyona aktarmak + H3–H7 raporu

**Files:**
- Modify: `src/microgrid/station/charging_station.py`
- Modify: `docs/arayuz-sozlesmesi.md` (YM-2 bölümüne "İstasyon → optimizasyon (Senaryo 5)" alt başlığı)
- Test: `tests/test_station.py`
- Create: `docs/raporlar/hafta3-7-ym2-raporu.md`

**Interfaces:**
- Produces:
  - `ChargingStation.planned_sessions() -> pd.DataFrame` — gün başında bilinen filo (kusursuz geliş bilgisi varsayımı; raporda belirtilir). Araç başına bir satır, sütunlar: `vehicle_id, arrival, departure, battery_kwh, soc_arrival, target_soc, energy_needed_kwh, max_charge_kw, max_discharge_kw, charge_efficiency`. `max_charge_kw` = aracın AC ünitedeki CC fazı gücü (`min(max_ac_kw, AC ünite gücü)`); `max_discharge_kw` = V2G kapalıysa 0.
  - `ChargingStation.n_chargers -> int` (property; MILP'te "aynı anda en fazla n araç" kısıtı).
  - Sözleşme notu: MILP planı `vehicle_id` ile tutar; `decide` adımında `VehicleRequest.vehicle_id → charger_id` eşlemesiyle `Decision.ev_kw`'ye çevirir. Hedef SOC kısıtı: `Σ p·dt·η ≥ energy_needed_kwh` (geliş–ayrılış penceresinde).

- [ ] **Step 1: Failing testler**

```python
def test_planned_sessions_columns_and_rows(cfg):   # sütunlar tam liste, satır == vehicles.count, departure > arrival
def test_planned_matches_live_vehicles(cfg):       # her satırın arrival/departure/soc_arrival'ı station.vehicles ile aynı
def test_plan_following_ems_reaches_targets(cfg):  # vehicles.count=10; testteki PlanEMS her araca ihtiyacını pencereye
                                                   # eşit yayarak (energy/(η·(departure−arrival))) güç verir; run() sonrası
                                                   # satisfaction(...)["hedefe_ulasma_orani"] == 1
```

- [ ] **Step 2:** `pytest tests/test_station.py -q` → FAIL.
- [ ] **Step 3:** `planned_sessions`, `n_chargers` ve sözleşme notunu yaz.
- [ ] **Step 4:** `pytest -q` → PASS.
- [ ] **Step 5:** Raporu yaz (`docs/calisma-duzeni.md` formatı, 1–2 sayfa): H3–H7'de yapılanlar (kişi: YM-2), kanıt olarak Task 5 PNG'si ve S2 için `satisfaction` tablosu (`python -m microgrid.sim --gun ikisi` çıktısından), sorunlar (geç birleşme ve sebebi tek cümle; S3 testi notu varsa), hocaya soru yok ise yazılmaz, Hafta 8 planı (V2G).
- [ ] **Step 6:** Commit: `YM-2 Hafta 7: optimizasyon için istasyon kısıtları ve H3-H7 raporu`.

---

### Task 8 (H8): V2G: deşarj kuralı, minimum SOC ve ayrılışta hedef SOC garantisi

**Files:**
- Modify: `src/microgrid/station/vehicle.py` (`discharge`), `charging_unit.py`, `charging_station.py` (`requests` içinde `max_discharge_kw`, `apply`'da negatif güç, `planned_sessions`'ta `max_discharge_kw`)
- Test: `tests/test_station_v2g.py`
- Create: `docs/raporlar/hafta8-ym2-raporu.md`

**Interfaces:**
- Produces:
  - `ElectricVehicle.discharge(p_kw: float, dt_h: float, eff: float) -> float` — `p ≥ 0` (şebeke tarafı) alır, `soc −= p·dt/(eff·B)`, `energy_out_kwh += p·dt`, `p` döndürür.
  - `ElectricVehicle.max_discharge_kw(ts: pd.Timestamp, dt_h: float, unit_kw: float, p_charge_kw: float, min_soc: float, eff: float) -> float`:
    ```text
    Araç v2g_capable değilse 0. (station.v2g_enabled false ise istasyon bu metodu hiç çağırmaz, 0 kullanır.)
    t_after  = (departure − ts) saat − dt_h            # bu adımdan sonra kalan süre
    e_floor  = (soc − min_soc) · B                     # min SOC'nin üstündeki batarya enerjisi
    e_slack  = t_after · p_charge_kw · eff − max(0, target − soc) · B   # hedefe yine yetişmek için ayrılabilecek pay
    e_out    = max(0, min(e_floor, e_slack))           # bu adımda bataryadan çıkabilecek en fazla enerji
    sonuç    = min(unit_kw, e_out · eff / dt_h)
    ```
    (`e_slack`'te deşarj sonrası ihtiyaç artışı da hesaba katılmalı: deşarj edilen enerji yeniden şarj edilecek. Doğru koşul `t_after·p_charge·eff ≥ (target − soc)·B + e_out`; yukarıdaki `e_slack` tam olarak bu koşuldan `e_out` için çözülmüş hâlidir.)
  - `requests`: V2G açık ve araç uygunsa `VehicleRequest.max_discharge_kw` bu değer; hedefe ulaşmış ama deşarj edebilecek araç da listeye girer.
  - `apply`: `p < 0` ise `−min(−p, max_discharge_kw)` uygulanır; V2G kapalıysa 0.

- [ ] **Step 1: Failing testler**

```python
def test_v2g_off_by_default(cfg):                   # v2g_capable araç, station.v2g_enabled false -> max_discharge_kw 0
def test_non_capable_vehicle_never_discharges(cfg)
def test_discharge_limited_by_unit_and_floor(cfg):  # soc 0.31, min 0.3, B 60 -> en fazla 0.01*60*η/dt
def test_no_discharge_near_departure(cfg):          # ayrılışa 1 adım kala, hedefe ihtiyaç var -> 0
def test_soc_never_below_min(cfg):                  # V2G açık, her adım -1000 kW isteyen EMS -> soc >= v2g_min_soc − 1e-9
def test_target_still_reached_after_v2g(cfg):       # V2G açık; EMS 17–22 arası mümkün olan en fazla deşarjı, sonra tam şarjı ister;
                                                    # vehicles.count=10 -> satisfaction hedefe_ulasma_orani == 1
def test_energy_conservation_with_v2g(cfg):         # Σ (şarj·η − deşarj/η)·dt == Σ (soc_son − soc_ilk)·B
```

- [ ] **Step 2:** `pytest tests/test_station_v2g.py -q` → FAIL.
- [ ] **Step 3:** V2G'yi yaz.
- [ ] **Step 4:** `pytest -q` → PASS.
- [ ] **Step 5:** Hafta 8 raporu: kural, formül, iki testin sonucu (deşarj edilen toplam kWh, hedefe ulaşma oranı), YM-3'e not: Senaryo 6 `{"station.v2g_enabled": True}` override'ı ve kendi V2G EMS'iyle eklenir.
- [ ] **Step 6:** Commit: `YM-2 Hafta 8: V2G deşarj kuralı, minimum SOC ve ayrılışta hedef SOC garantisi`.

---

### Task 9 (H9): Şarj istasyonu rapor bölümü ve tasarım belgelerinin son hâli

**Files:**
- Create: `docs/rapor/sarj-istasyonu.md`, `scripts/ym2_rapor_grafikleri.py`
- Modify: `docs/SINIF_DIYAGRAMI.md` (yeni alan ve metotlar; Mermaid diyagramı), `docs/PARAMETRE_TABLOSU_VE_ARAYUZ.md` (bölüm 3'teki eski `bagli_araclar/apply_power_allocations` imzaları → `requests/apply`; parametre tablosu config değerleriyle aynı)
- Create: `docs/raporlar/hafta9-ym2-raporu.md`

İçerik (rapor bölümü başlıkları): 1. İstasyon tanımı ve parametreler (config tablosu) · 2. Talep modeli (dağılımlar, katalog, kırpma kuralları) · 3. Ünite ataması, sıra ve nöbetleşe şarj · 4. CC-CV modeli (formül + `cc_cv_limit` eğrisi grafiği) · 5. Döngüdeki yeri (`requests/apply`, şebeke tarafı güç ve η) · 6. V2G kuralı ve garanti koşulunun türetilmesi · 7. Sonuçlar: S1/S2 (ve varsa S3–S6) için istasyon tepe, `satisfaction` tablosu, araç sayısı grafiği, Haziran–Aralık farkı · 8. Sınırlamalar (kusursuz geliş bilgisi, tek tip AC planı, OBC'nin sabit kabulü).

- [ ] **Step 1:** `scripts/ym2_rapor_grafikleri.py` yaz: CC-CV eğrisi, ünite doluluk zaman çizelgesi (S2, Haziran), `satisfaction` karşılaştırma tablosu (mevcut tüm senaryolar) → `docs/rapor/` altına PNG ve Markdown tablo. Veri yoksa sahte girdi ve başlıkta "SAHTE GİRDİ".
- [ ] **Step 2:** Betiği çalıştır; çıktıların oluştuğunu `ls docs/rapor/` ile doğrula.
- [ ] **Step 3:** Rapor bölümünü ve iki tasarım belgesini yaz; rapordaki her sayı betik çıktısından kopyalanır.
- [ ] **Step 4:** `pytest -q` → PASS.
- [ ] **Step 5:** Hafta 9 raporu, commit: `YM-2 Hafta 9: şarj istasyonu rapor bölümü ve tasarım belgelerinin son hâli`. 9 Aralık kod dondurma öncesi son kod commit'i.

---

### Task 10 (H10): Sunumun istasyon slaytları

**Files:**
- Create: `docs/sunum/ym2-istasyon-slaytlari.md`

- [ ] **Step 1:** 5–6 slaytlık içerik: her slayt için başlık, 3–4 madde, kullanılacak görsel (Task 5/9 PNG'leri) ve konuşmacı notu. Slaytlar: (1) İstasyonun tanımı ve referans örnekten farkımız (MathWorks örneğinde 2 toplu batarya, bizde tek tek gelen araçlar), (2) Talep modeli, (3) CC-CV ve ünite ataması, (4) Kontrolsüz şarjın etkisi: araç sayısı–tepe yük, (5) Kullanıcı memnuniyeti ve V2G garantisi, (6) Kod anlatımı: `requests/apply` döngü akışı (sunumda satır satır anlatılacak fonksiyonlar listelenir).
- [ ] **Step 2:** YM-4'ün sunum şablonu geldiyse içerik ona aktarılır (ayrı iş; bu planın dışında).
- [ ] **Step 3:** Commit: `YM-2 Hafta 10: istasyon slaytlarının içeriği`.
