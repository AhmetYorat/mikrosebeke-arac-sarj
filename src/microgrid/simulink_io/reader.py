"""Simulink CSV çıktılarını okur ve biçimini doğrular (YM-4 + EM-2).

Biçim tanımı: docs/arayuz-sozlesmesi.md, "Simulink CSV formatı".
Birim hataları (Hz yerine p.u., % yerine 0-1, W yerine kW) en sık yapılan hata olduğu için
değer aralıkları da kontrol edilir; hata mesajı neyin yanlış olduğunu söyler.
"""
from pathlib import Path

import pandas as pd

REQUIRED = ["time_s", "freq_pu", "v_pcc_pu", "p_grid_kw"]
OPTIONAL = ["p_pv_kw", "p_bess_kw", "soc_bess", "p_ev_ac_kw", "p_ev_dc_kw", "p_load_kw"]

# (sütun, alt, üst, ipucu)
RANGES = [
    ("freq_pu", 0.9, 1.1, "frekans p.u. olmalı (50 Hz = 1.0); Hz ise 50'ye bölün"),
    ("v_pcc_pu", 0.5, 1.5, "gerilim p.u. olmalı; V ise nominal gerilime bölün"),
    ("soc_bess", 0.0, 1.0, "SOC 0-1 olmalı; % ise 100'e bölün"),
]


def load_simulink_csv(path) -> pd.DataFrame:
    path = Path(path)
    df = pd.read_csv(path)
    problems = []

    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        problems.append(f"eksik zorunlu sütun: {missing}")
    unknown = [c for c in df.columns if c not in REQUIRED + OPTIONAL]
    if unknown:
        problems.append(f"tanımsız sütun: {unknown} (gerekiyorsa sözleşmeye eklensin)")

    if "time_s" in df.columns and not df["time_s"].is_monotonic_increasing:
        problems.append("time_s artan sırada değil")
    for col, lo, hi, hint in RANGES:
        if col in df.columns and not df[col].between(lo, hi).all():
            problems.append(f"{col} [{lo}, {hi}] dışında (min {df[col].min():g}, max {df[col].max():g}): {hint}")
    power_cols = [c for c in df.columns if c.startswith("p_")]
    for col in power_cols:
        if df[col].abs().max() > 1e5:
            problems.append(f"{col} 100 MW'ı aşıyor: değerler W cinsinden olabilir, 1000'e bölün")

    if problems:
        raise ValueError(f"{path.name} sözleşmeye uymuyor:\n- " + "\n- ".join(problems))
    return df.set_index("time_s")
