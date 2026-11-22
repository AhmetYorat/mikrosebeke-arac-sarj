"""Simulink çıktılarının kataloğu ve özetleri (YM-4 + EM-2). Dashboard'un "Dinamik (Simulink)" sekmesi bunu kullanır.

- list_outputs: simulink/outputs/ altındaki CSV'leri bulur, her birini sözleşmeye göre okur. Hatalı dosya
  dashboard'u çökertmez; hata mesajı (ör. "frekans Hz görünüyor, 50'ye bölün") dosyanın yanında gösterilir.
- summarize: frekans/gerilim özeti (en düşük nokta, banttan çıkış süresi, toparlanma).
- critical_moment: Python simülasyonunun en zorlayıcı adımı. EM ekibi D2 gibi senaryoların başlangıç
  koşulunu buradan alır (plan: "Python kritik anı bulur, Simulink o anı dinamik inceler").
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from microgrid.config import REPO_ROOT
from microgrid.simulink_io.reader import load_simulink_csv

# Plandaki dinamik senaryolar (Mikro-Şebeke Proje Planı v2, bölüm 5)
EXPECTED = {
    "D1": "Yük basamağı + V2G desteği",
    "D2": "Toplu araç bağlanması",
    "D3": "PV ani düşüşü (bulut geçişi)",
    "D4": "Ada modu (şebeke kesintisi)",
}
_NAME = re.compile(r"^(D\d+)_(.+)\.csv$", re.IGNORECASE)


@dataclass
class SimulinkRun:
    path: Path
    code: str            # "D1"; dosya adı kurala uymuyorsa ""
    title: str           # dosya adının kısa kısmı ("yuk_basamagi")
    data: pd.DataFrame | None
    error: str | None    # okunamadıysa neden


def outputs_dir(cfg: dict) -> Path:
    return REPO_ROOT / cfg["simulink"]["outputs_dir"]


def list_outputs(directory: Path) -> list[SimulinkRun]:
    runs = []
    for path in sorted(Path(directory).glob("*.csv")):
        m = _NAME.match(path.name)
        code, title = (m.group(1).upper(), m.group(2)) if m else ("", path.stem)
        try:
            data, error = load_simulink_csv(path), None
        except (ValueError, pd.errors.ParserError) as e:
            data, error = None, str(e)
        if not m and error is None:
            error = f"{path.name}: dosya adı '<senaryo>_<kısa_ad>.csv' kuralına uymuyor (ör. D1_yuk_basamagi.csv)"
        runs.append(SimulinkRun(path, code, title, data, error))
    return runs


def status_table(runs: list[SimulinkRun]) -> pd.DataFrame:
    """Plandaki D1–D4 için durum: hazır / hatalı / gelmedi. Perşembe raporundaki EM satırı buradan okunur."""
    rows = []
    for code, name in EXPECTED.items():
        mine = [r for r in runs if r.code == code]
        if not mine:
            status, files = "gelmedi", ""
        elif all(r.error is None for r in mine):
            status, files = "hazır", ", ".join(r.path.name for r in mine)
        else:
            status, files = "hatalı", ", ".join(r.path.name for r in mine)
        rows.append({"senaryo": code, "açıklama": name, "durum": status, "dosya": files})
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame, band: tuple[float, float]) -> dict:
    """Frekans ve gerilim özeti. df: load_simulink_csv çıktısı (indeks time_s)."""
    t = df.index.to_numpy(dtype=float)
    f = df["freq_pu"].to_numpy(dtype=float)
    lo, hi = band
    outside = (f < lo) | (f > hi)
    # Banttan çıkış süresi: örnekler arası süreleri topla (örnekleme düzensiz olabilir)
    dts = np.diff(t, append=t[-1])
    i_min = int(np.argmin(f))
    last_out = t[outside].max() if outside.any() else None
    return {
        "f_min_pu": float(f.min()),
        "f_min_hz": float(f.min() * 50),
        "f_min_t_s": float(t[i_min]),
        "f_max_pu": float(f.max()),
        "bant_disi_s": float(dts[outside].sum()),
        "banda_donus_t_s": float(last_out) if last_out is not None else None,
        "v_min_pu": float(df["v_pcc_pu"].min()),
        "p_grid_max_kw": float(df["p_grid_kw"].max()),
        "sure_s": float(t[-1] - t[0]),
    }


def critical_moment(steps: pd.DataFrame, cfg: dict) -> dict:
    """Günün şebekeyi en çok zorlayan adımı (en yüksek şebeke alımı) ve o anın güçleri.

    EM ekibi Simulink'te D2 (toplu araç bağlanması) gibi senaryoları bu değerlerle başlatır; böylece iki katman
    aynı anı anlatır.
    """
    ts = steps["grid_kw"].idxmax()
    row = steps.loc[ts]
    out = {
        "zaman": f"{ts:%d.%m %H:%M}",
        "sebeke_alim_kw": round(float(row.grid_kw), 1),
        "istasyon_kw": round(float(row.ev_kw), 1),
        "sabit_yuk_kw": round(float(row.base_load_kw), 1),
        "pv_kw": round(float(row.pv_kw), 1),
        "batarya_kw": round(float(row.bess_kw), 1),
        "bagli_arac": int(row.n_vehicles),
        "site_siniri_kw": cfg["grid"]["site_import_limit_kw"],
    }
    if pd.notna(row.min_vm_pu):
        out["min_gerilim_pu"] = float(row.min_vm_pu)
    return out
