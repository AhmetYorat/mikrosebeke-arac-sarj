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

### macOS'ta tek tıkla (önerilen)

1. Repoyu indirin: `git clone https://github.com/AhmetYorat/mikrosebeke-arac-sarj.git`
   (ya da GitHub'da **Code → Download ZIP**, sonra ZIP'i açın).
2. Klasördeki **`kurulum.command`** dosyasına çift tıklayın. Terminal açılır ve sırayla:
   - Python 3.10+ bulur; yoksa Homebrew ile Python 3.12 kurar,
   - `.venv` sanal ortamını oluşturur ve paketleri kurar,
   - veri yoksa PVGIS güneş verisini bir kez indirir ve yük profillerini üretir (`python -m microgrid.data`),
   - dashboard'u açar: http://localhost:8501
3. Kapatmak için Terminal'de **Ctrl + C**. Sonraki açılışlarda da aynı dosyaya çift tıklamanız yeterli.

Sık karşılaşılanlar:

| Sorun | Çözüm |
| --- | --- |
| "Geliştiricisi doğrulanamadığı için açılamıyor" | Dosyaya **sağ tık → Aç → Aç**. Bir kez yapmak yeterli. |
| "İzniniz yok" / dosya açılmıyor (çoğunlukla ZIP ile indirince) | Terminal'de klasöre girip `chmod +x kurulum.command` |
| Streamlit e-posta soruyor | Betik bunu kendisi atlar; elle kurulumda Enter'a basmanız yeterli. |
| `pip` "editable install" hatası | Python 3.9 veya eski pip kullanılıyor; `kurulum.command` doğru Python'u kendisi bulur. |

### Windows'ta tek tıkla

1. Repoyu indirin (`git clone …` ya da GitHub'da **Code → Download ZIP**, sonra ZIP'i açın).
2. Klasördeki **`kurulum.bat`** dosyasına çift tıklayın. Komut penceresi açılır ve sırayla:
   - Python 3.10+ bulur; yoksa `winget` ile Python 3.12 kurar (yönetici izni gerekmez),
   - `.venv` sanal ortamını oluşturur ve paketleri kurar,
   - veri yoksa PVGIS güneş verisini bir kez indirir (`python -m microgrid.data`),
   - dashboard'u açar: http://localhost:8501
3. Kapatmak için pencerede **Ctrl + C**. Sonraki açılışlarda da aynı dosyaya çift tıklamanız yeterli.

| Sorun | Çözüm |
| --- | --- |
| "Windows bilgisayarınızı korudu" (SmartScreen) | **Ek bilgi → Yine de çalıştır**. |
| "Python bulunamadı" ve tarayıcıda python.org açıldı | Python 3.12'yi kurarken **"Add python.exe to PATH"** kutusunu işaretleyin, sonra `kurulum.bat`'a tekrar çift tıklayın. |
| Python'u yeni kurdunuz ama yine bulunamıyor | Pencereyi kapatıp `kurulum.bat`'ı yeniden açın (PATH yeni pencerede güncellenir). |

### Elle kurulum (Linux, ya da betik çalışmazsa)

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

`requirements.txt` PuLP'u 4'ün altına sabitler: PuLP 4 CBC çözücüsünü içermiyor ve MILP (S5, S6) çalışmaz.
Daha önce PuLP 4 kurulduysa `pip install -r requirements.txt` ile 3.x'e dönülür.

## Çalıştırma

Önce veriyi bir kez hazırla (PVGIS'ten güneş verisini indirir, yük profillerini üretir; `data/processed/`):

```bash
python -m microgrid.data
```

Sonra:

| Ne | Komut |
| --- | --- |
| Dashboard (canlı demo) | `streamlit run dashboard/app.py` |
| Tek senaryo, iki temsili gün | `python -m microgrid.sim --senaryo S3 --gun ikisi` |
| **Bütün senaryolar, rapor tabloları ve grafikleri** | `python -m microgrid.sim.sonuclar` → `results/sonuclar/` |
| Tek seferlik yük akışı | `python -m microgrid.grid` (bkz. [docs/sebeke-modeli.md](docs/sebeke-modeli.md)) |

Veri hazırlanmamışsa döngü ve dashboard **sahte girdilerle** çalışır ve bunu açıkça yazar; bu sayılar raporda kullanılmaz.

**Rapordaki sayılar** GitHub'da üretilir: *Actions → sonuclar → Run workflow*. İş bitince sayfanın altındaki
`sonuclar` dosyası indirilir (KPI tabloları, `ozet.md`, karşılaştırma grafikleri). Böylece herkes aynı sürümlerle
aynı sayıları görür; `main`'e kod değiştiğinde de kendiliğinden çalışır.

## Senaryolar

İstasyon hepsinde YM-2'nin modelidir (araç kataloğu, CC-CV, sıra ve nöbetleşe şarj); 20 araç, 8 × AC 22 kW + 2 × DC 50 kW,
istasyon sınırı 150 kW, site şebeke sınırı 180 kW. Tanımlar: `src/microgrid/sim/scenarios.py`.

| | Senaryo | EMS (YM-3) |
| --- | --- | --- |
| S1 | Temel (araç yok) | Karşılaştırma tabanı |
| S2 | Kontrolsüz şarj | Araç geldiği an tam güç |
| S3 | Akıllı şarj | Kural tabanlı: ucuz tarifeye yayma, SOC tabanı, PV fazlası, sınırlar |
| S4 | Akıllı şarj + batarya | S3 + 200 kWh / 100 kW batarya |
| S5 | Optimizasyon | Kayan ufuklu MILP (PuLP): en düşük maliyet |
| S6 | V2G | S5 + araçtan şebekeye deşarj |

Dinamik senaryolar (Simulink, EM-1/EM-2): D1 yük basamağı + V2G, D2 toplu araç bağlanması, D3 PV ani düşüşü,
D4 ada modu. CSV'ler `simulink/outputs/` altına geldikçe dashboard'un *Dinamik* sekmesinde görünür.

## Klasör yapısı

| Yol | İçerik | Sorumlu |
| --- | --- | --- |
| `config/default.yaml` | Tüm senaryo parametreleri (istasyon, araçlar, PV, BESS, tarife) | Herkes (PR ile) |
| `src/microgrid/data/` | PVGIS, yük ve tarife verileri; PV ve yük modelleri | YM-1 |
| `src/microgrid/kpi.py` | Performans göstergeleri (tepe, maliyet, öz tüketim, sınır aşımı) | YM-1 |
| `src/microgrid/station/` | Şarj istasyonu: araç talebi, üniteler, CC-CV, şarj stratejileri | YM-2 |
| `src/microgrid/ems/` | EMS: batarya yönetimi, kural tabanlı akıllı şarj, MILP | YM-3 |
| `src/microgrid/grid/` | pandapower ağı ve yük akışı | YM-4 + EM-2 |
| `src/microgrid/sim/` | Simülasyon döngüsü, senaryolar, sonuç üretimi | YM-4 |
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
