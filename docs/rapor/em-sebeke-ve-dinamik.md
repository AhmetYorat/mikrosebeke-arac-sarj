# EM-1 / EM-2 Şebeke Modeli ve Dinamik Analiz Raporu

## 1. Onaylanan Şebeke Parametreleri
- **OG / AG Trafo:** 400 kVA, 20/0,4 kV
- **Site Kablosu:** NAYY 4x150 SE, 150 m (Site Barası: Sabit yük ~200 MWh/yıl + 100 kWp PV)
- **Otopark Kablosu:** NAYY 4x150 SE, 100 m, taşıma kapasitesi ~270 A (Otopark Barası: 200 kWh / 100 kW BESS, SOC %10–90 + 276 kW kurulu / 150 kW sınırlı şarj istasyonu)
- **Gerilim Sınırı:** 0,95–1,05 p.u.

## 2. Statik Yük Akışı Doğrulaması (pandapower — EM-2)
- **S2 (Kontrolsüz Şarj, 210 kW):** Otopark kablosu akımı ~315 A (%117 aşırı yüklenme), en düşük bara gerilimi 0,961 p.u. (sınır içinde).
- **Sınırlı Çalışma (150 kW istasyon sınırı):** Kablo yüklenmesi %80–84 aralığında güvenli bölgede kalır.

## 3. Dinamik Analiz Senaryoları (MATLAB/Simulink — EM-1)
Ortak CSV sütun formatı: `time_s, freq_pu, v_pcc_pu, p_grid_kw`

- **D1 (`D1_yuk_basamagi.csv`):** Eklenecek
- **D2 (`D2_toplu_baglanma.csv`):** Eklenecek
- **D3 (`D3_pv_dususu.csv`):** Eklenecek
- **D4 (`D4_ada_modu.csv`):** Eklenecek
