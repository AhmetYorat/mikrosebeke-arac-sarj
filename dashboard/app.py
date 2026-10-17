"""Streamlit dashboard. Çalıştırma: streamlit run dashboard/app.py

Hafta 1: yalnızca iskelet. Config'i okuyup istasyon tanımını ve beklenen
araç geliş dağılımını gösterir; simülasyon sonuçları v0 ile (5 Kasım) gelecek.
"""
import sys
from pathlib import Path

# src klasörünü modül arama yoluna ekle (microgrid paketinin doğrudan bulunabilmesi için)
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import numpy as np
import pandas as pd
import streamlit as st

from microgrid.config import load_config

st.set_page_config(page_title="Mikro-Şebeke + EV Şarj İstasyonu", layout="wide")
cfg = load_config()
station, vehicles = cfg["station"], cfg["vehicles"]

st.title("Mikro-Şebeke + EV Şarj İstasyonu")
st.caption("İskelet sürüm: henüz simülasyon sonucu yok, yalnızca senaryo tanımı gösteriliyor.")

installed_kw = sum(c["count"] * c["power_kw"] for c in station["chargers"])
col1, col2, col3, col4 = st.columns(4)
station_type_label = "Site Otoparkı" if station["type"] == "site_otoparki" else station["type"].replace("_", " ").title()
col1.metric("İstasyon tipi", station_type_label)
col2.metric("Kurulu ünite gücü", f"{installed_kw} kW")
col3.metric("İstasyon limiti", f"{station['power_limit_kw']} kW")
col4.metric("Araç sayısı", vehicles["count"])

left, right = st.columns(2)

with left:
    st.subheader("Şarj üniteleri")
    df_chargers = pd.DataFrame(station["chargers"]).rename(
        columns={"kind": "Tip", "count": "Adet", "power_kw": "Güç (kW)"}
    )
    try:
        st.dataframe(df_chargers, hide_index=True, use_container_width=True)
    except TypeError:
        st.dataframe(df_chargers)

with right:
    st.subheader("Beklenen araç gelişleri (saatlik)")
    # Normal dağılımı 24 saate sarıyoruz ki gece yarısını aşan kuyruk kaybolmasın.
    hours = np.arange(24)
    mean, std = vehicles["arrival_hour"]["mean"], vehicles["arrival_hour"]["std"]
    diff = (hours - mean + 12) % 24 - 12
    weights = np.exp(-0.5 * (diff / std) ** 2)
    expected = vehicles["count"] * weights / weights.sum()
    
    chart_df = pd.DataFrame({"Beklenen Araç Sayısı": expected}, index=hours)
    chart_df.index.name = "Saat"
    try:
        st.bar_chart(chart_df)
    except Exception:
        chart_df_reset = pd.DataFrame({"saat": hours, "araç": expected})
        st.bar_chart(chart_df_reset, x="saat", y="araç")
