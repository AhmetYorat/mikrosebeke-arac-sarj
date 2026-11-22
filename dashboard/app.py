"""Streamlit dashboard (YM-4). Çalıştırma: streamlit run dashboard/app.py

Senaryo ve temsili gün seçilir, döngü çalışır, sonuçlar sekmelerde gösterilir.
Veri dosyaları yoksa (python -m microgrid.data çalıştırılmadıysa) sahte girdilerle çalışır ve bunu üstte yazar.
"""
import json

import streamlit as st

import charts
from microgrid.config import load_config
from microgrid.grid import PandapowerGrid
from microgrid.sim.loop import time_index
from microgrid.sim.scenarios import SCENARIOS, apply_overrides, simulate
from microgrid.sim.setup import SAHTE, TEMSILI_GUNLER, load_inputs, with_start

st.set_page_config(page_title="Mikro-Şebeke + EV Şarj İstasyonu", layout="wide")
base = load_config()


@st.cache_data(show_spinner="Simülasyon çalışıyor…")
def run_cached(cfg_json: str, scenario_name: str, with_grid: bool):
    """Aynı ayarlar ikinci kez seçilince tekrar hesaplanmasın. Sonuç tabloları ve girdi kaynağı döner."""
    cfg = json.loads(cfg_json)
    inputs, source = load_inputs(cfg, time_index(cfg))
    grid = PandapowerGrid(cfg) if with_grid else None
    result = simulate(cfg, SCENARIOS[scenario_name], inputs, grid)
    return result.steps, result.station, source


# ---- Kenar çubuğu: senaryo ve parametreler ----
with st.sidebar:
    st.header("Senaryo")
    names = list(SCENARIOS)
    scenario_name = st.selectbox("Senaryo", names, index=names.index("S2 Kontrolsüz şarj"))
    scenario = SCENARIOS[scenario_name]
    st.caption(scenario.description)
    day = st.radio("Temsili gün", list(TEMSILI_GUNLER), format_func=str.capitalize, horizontal=True,
                   help="Hafta içi ortalama gün; öğlen başlar, ertesi gün öğlen biter.")

    st.header("Parametreler")
    fixed = scenario.config   # senaryonun kendisi belirlediği parametreler kaydırıcıyla değiştirilemez
    overrides = {
        "vehicles.count": st.slider("Günlük araç sayısı", 0, 40, fixed.get("vehicles.count", base["vehicles"]["count"]),
                                    disabled="vehicles.count" in fixed,
                                    help="Bu senaryoda sabit." if "vehicles.count" in fixed else None),
        "pv.installed_kw": st.slider("PV kurulu gücü (kWp)", 0, 200, base["pv"]["installed_kw"], step=10),
        "bess.capacity_kwh": st.slider("Batarya kapasitesi (kWh)", 0, 400, base["bess"]["capacity_kwh"], step=20),
    }
    with_grid = st.toggle("Yük akışı (pandapower)", value=True, help="Kapalıyken daha hızlı; gerilim ve yüklenme boş kalır.")

overrides = {k: v for k, v in overrides.items() if k not in fixed}
cfg = apply_overrides(with_start(base, TEMSILI_GUNLER[day]), overrides)
steps, station, source = run_cached(json.dumps(cfg, sort_keys=True, default=str), scenario_name, with_grid)

# ---- Başlık ----
st.title("Mikro-Şebeke + EV Şarj İstasyonu")
if source == SAHTE:
    st.warning("Gerçek veri dosyaları bulunamadı; **sahte girdilerle** çalışılıyor. Bu sayılar raporda kullanılmamalı. "
               "Gerçek veri için bir kez: `python -m microgrid.data`", icon="⚠️")
if scenario.temporary:
    st.info("Bu senaryo henüz sahte istasyon/EMS modülüyle çalışıyor; YM-2/YM-3 modülleri gelince sonuçlar değişecek.",
            icon="ℹ️")

dt = cfg["simulation"]["step_minutes"] / 60
c = st.columns(4)
c[0].metric("Şebeke tepe alımı", f"{steps['grid_kw'].max():.0f} kW", help=f"{steps['grid_kw'].idxmax():%H:%M}")
c[1].metric("İstasyon tepe gücü", f"{steps['ev_kw'].max():.0f} kW")
c[2].metric("Araç şarjı", f"{steps['ev_kw'].clip(lower=0).sum() * dt:.0f} kWh")
c[3].metric("Günlük maliyet", f"{steps['cost_tl'].sum():,.0f} TL".replace(",", "."))

# ---- Sekmeler ----
tab_flow, tab_station, tab_grid, tab_data = st.tabs(["Güç akışları", "Şarj istasyonu", "Şebeke", "Veri"])

with tab_flow:
    st.plotly_chart(charts.power_flows(steps, cfg), width="stretch")

with tab_station:
    if station.empty:
        st.write("Bu senaryoda istasyona araç bağlanmıyor.")
    else:
        st.subheader("Ünite doluluğu")
        st.caption("Her satır bir şarj ünitesi; renk o adımda çekilen güç. Boş hücre: ünite boş ya da araç dolmuş.")
        st.plotly_chart(charts.charger_heatmap(station, cfg), width="stretch")
        st.subheader("Araçların doluluk oranı (SOC)")
        st.caption("Her çizgi bir araç, yalnızca şarj ihtiyacı olduğu sürece görünür.")
        st.plotly_chart(charts.vehicle_soc(station, cfg), width="stretch")

with tab_grid:
    if steps["min_vm_pu"].notna().any():
        st.plotly_chart(charts.grid_quality(steps, cfg), width="stretch")
    else:
        st.write("Yük akışı kapalı. Kenar çubuğundan açın.")

with tab_data:
    st.dataframe(steps, width="stretch")
    st.download_button("Adım tablosunu indir (CSV)", steps.to_csv().encode("utf-8"),
                       file_name=f"{scenario_name.split()[0]}_{day}_steps.csv")
