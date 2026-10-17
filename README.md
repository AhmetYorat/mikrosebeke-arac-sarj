# Mikro-Şebeke + EV Şarj İstasyonu

Akıllı Şebekeler dersi dönem projesi. Elektrikli araç şarj istasyonu içeren bir mikro-şebekeyi
modelliyor ve şu soruya cevap arıyoruz:

> Şarj istasyonu bu mikro-şebekeye ne yük getiriyor ve akıllı yönetimle bu yük ne kadar azaltılabiliyor?

Proje iki katmandan oluşur:

- **Python (bu repo):** 24 saatlik zaman serisi simülasyonu, enerji yönetimi (EMS), pandapower ile yük akışı, Streamlit dashboard.
- **MATLAB/Simulink:** saniyeler mertebesinde dinamik analiz (frekans, gerilim). Çıktıları CSV olarak `simulink/outputs/` altına gelir ve dashboard'da gösterilir.

Kapsam kararı: [docs/kapsam.md](docs/kapsam.md) · Arayüz sözleşmesi: [docs/arayuz-sozlesmesi.md](docs/arayuz-sozlesmesi.md) · Çalışma düzeni ve Git kuralları: [docs/calisma-duzeni.md](docs/calisma-duzeni.md)

## Kurulum

Python 3.10 veya üstü gerekir (3.12 ile denendi).

```bash
git clone https://github.com/AhmetYorat/mikrosebeke-arac-sarj.git
cd mikrosebeke-arac-sarj
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Kurulumu doğrula:

```bash
pytest
streamlit run dashboard/app.py
```

`pytest` yeşil geçmeli, ikinci komut tarayıcıda dashboard'u açmalı.

Simülasyon döngüsünü sahte modüllerle denemek için: `python -m microgrid.sim` (sonuçlar `results/` altına yazılır).

## Klasör yapısı

| Yol | İçerik | Sorumlu |
| --- | --- | --- |
| `config/default.yaml` | Tüm senaryo parametreleri (istasyon, araçlar, PV, BESS, tarife) | Herkes (PR ile) |
| `src/microgrid/data/` | PVGIS, yük ve tarife verileri; PV ve yük modelleri | YM-1 |
| `src/microgrid/station/` | Şarj istasyonu: araç talebi, üniteler, CC-CV, şarj stratejileri | YM-2 |
| `src/microgrid/ems/` | EMS: batarya yönetimi, kural tabanlı akıllı şarj, MILP | YM-3 |
| `src/microgrid/grid/` | pandapower ağı ve yük akışı | YM-4 + EM-2 |
| `src/microgrid/sim/` | Simülasyon döngüsü | YM-4 |
| `src/microgrid/simulink_io/` | Simulink CSV'lerini içeri alma | YM-4 + EM-2 |
| `dashboard/` | Streamlit arayüzü | YM-4 |
| `simulink/` | Simulink modeli ve CSV çıktıları | EM-1, EM-2 |
| `data/` | Ham ve işlenmiş veri (repoya girmez) | YM-1 |
| `docs/` | Kapsam, arayüz dokümanı, haftalık raporlar | Herkes |
| `scripts/` | Rapor grafiklerini üreten tek seferlik scriptler | Herkes |
| `tests/` | Birim testleri | Herkes |

## Ortak kurallar

- Parametreler koda gömülmez, `config/default.yaml` içinden okunur (`microgrid.config.load_config`).
- Birimler: güç **kW**, enerji **kWh**, zaman **ondalık saat**, SOC **0–1**, gerilim **p.u.**
- `main`'e doğrudan push yok; her iş kendi branch'inde, Pull Request ile birleşir.
