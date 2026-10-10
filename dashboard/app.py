"""Streamlit dashboard. Çalıştırma: streamlit run dashboard/app.py

Hafta 1: yalnızca iskelet. Config'i okuyup istasyon tanımını ve beklenen
araç geliş dağılımını gösterir; simülasyon sonuçları v0 ile (5 Kasım) gelecek.
"""
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
col1.metric("İstasyon tipi", station["type"])
col2.metric("Kurulu ünite gücü", f"{installed_kw} kW")
col3.metric("İstasyon limiti", f"{station['power_limit_kw']} kW")
col4.metric("Araç sayısı", vehicles["count"])

left, right = st.columns(2)

with left:
    st.subheader("Şarj üniteleri")
    st.dataframe(pd.DataFrame(station["chargers"]), hide_index=True, use_container_width=True)

with right:
    st.subheader("Beklenen araç gelişleri (saatlik)")
    # Normal dağılımı 24 saate sarıyoruz ki gece yarısını aşan kuyruk kaybolmasın.
    hours = np.arange(24)
    mean, std = vehicles["arrival_hour"]["mean"], vehicles["arrival_hour"]["std"]
    diff = (hours - mean + 12) % 24 - 12
    weights = np.exp(-0.5 * (diff / std) ** 2)
    expected = vehicles["count"] * weights / weights.sum()
    st.bar_chart(pd.DataFrame({"saat": hours, "araç": expected}), x="saat", y="araç")
