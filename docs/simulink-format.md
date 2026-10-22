# Simulink → Python Veri Formatı

Durum: **taslak**. 22 Ekim Perşembe ders sonrası EM-1 + YM-4 konuşulacak.

## CSV Çıktı Formatı

Simulink'ten dışa aktarılan CSV dosyalarının formatı:

```csv
time,s,pv_power_kw,load_power_kw,grid_power_kw,bess_soc,bus_voltage_pu
0,1.000,0.000,45.231,0.000,0.987
60,1.017,12.345,46.123,1.234,0.988
120,1.033,24.567,47.890,2.456,0.989
...
```

### Sütun Tanımları

| Sütun | Birim | Açıklama |
| --- | --- | --- |
| `time` | s | Simülasyon süresi (0’dan başlayarak artar) |
| `pv_power_kw` | kW | PV üretimi (anlık) |
| `load_power_kw` | kW | Toplam yük (EV + sabit) |
| `grid_power_kw` | kW | Şebeke ile arasındaki güç akışı (+ = şebekeden alınan, - = şebeğe verilen) |
| `bess_soc` | - (0–1) | Batarya SOC |
| `bus_voltage_pu` | p.u. | PCC barası gerilimi (per-unit) |

## Zaman Senkronizasyonu

**Python tarafı:** 15 dk adım (96 dönem/gün)
**Simulink tarafı:** Saniye düzeyinde (örn. 60 saniyelik adımlar)

### Senkronizasyon Yöntemi

1. **Simulink çıktısı** → CSV olarak `simulink/outputs/sim_*.csv` kaydedilir
2. **Python tarafı** (`src/microgrid/simulink_io/`) CSV'yi okur
3. Python'un 15 dk’lık zaman noktalarına göre interpolasyon yapılır:
   - Her 15 dk aralığında (0, 900, 1800, ..., 86400 saniye)
   - Simulink verisi lineer interpolasyonla Bu noktalar için değerler hesaplanır

### Örnek Python Kodu

```python
import pandas as pd
import numpy as np

def load_simulink_csv(filepath):
    """Simulink CSV'ini oku."""
    df = pd.read_csv(filepath)
    # time saniye cinsinden, Python'da saat olarak tutmak için /3600
    df['time_hours'] = df['time_s'] / 3600
    return df

def align_to_python_grid(sim_df, python_times_hours):
    """
    Simulink verisini Python'un 15 dk adımına uygunlaşır.
    
    Args:
        sim_df: Simulink CSV'den okunan DataFrame
        python_times_hours: Python'un zaman noktaları (0, 0.25, 0.5, ..., 23.75)
    
    Returns:
        DataFrame: Python zamanlarına göre interpolasyonlu veri
    """
    aligned = pd.DataFrame({'time_hours': python_times_hours})
    
    for col in ['pv_power_kw', 'load_power_kw', 'grid_power_kw', 
                'bess_soc', 'bus_voltage_pu']:
        aligned[col] = np.interp(
            aligned['time_hours'],
            sim_df['time_hours'],
            sim_df[col]
        )
    
    return aligned
```

## Çıktı Dosya Konumu

```bash
simulink/
  outputs/
    sim_*.csv          # Simulink çıktıları (tarih_saat.csv)
  inputs/
    python_*.csv       # Python’un Simulink’e gönderdiği girdiler
```

## Validasyon Kontrolleri

Her CSV dosyası için:

```python
def validate_simulink_csv(df):
    """Simulink CSV doğrulama."""
    required_cols = ['time_s', 'pv_power_kw', 'load_power_kw', 
                     'grid_power_kw', 'bess_soc', 'bus_voltage_pu']
    
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Eksik sütun: {col}")
    
    # Değer aralığı kontrolü
    assert (df['bess_soc'] >= 0).all(), "BESS SOC negatif"
    assert (df['bess_soc'] <= 1).all(), "BESS SOC 1'den büyük"
    assert (df['bus_voltage_pu'] >= 0.9).all(), "Gerilim çok düşük"
    assert (df['bus_voltage_pu'] <= 1.1).all(), "Gerilim çok yüksek"
    
    # Zaman dizisi kontrolü
    assert (df['time_s'].diff() >= 0).all(), "Zaman geri gidiyor"
```

---

## Sonraki Adımlar

1. EM-1: Simulink modeli oluşturulduktan sonra CSV export bloğu eklenir
2.YM-4: Python tarafı `simulink_io` modülü yazılır
3. Hafta 4’te entegrasyon testi yapılır
