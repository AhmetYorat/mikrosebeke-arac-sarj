"""Streamlit dashboard (YM-4). Çalıştırma: streamlit run dashboard/app.py

Senaryo ve temsili gün seçilir, döngü çalışır, sonuçlar sekmelerde gösterilir.
Veri dosyaları yoksa (python -m microgrid.data çalıştırılmadıysa) sahte girdilerle çalışır ve bunu üstte yazar.
"""
import json

import pandas as pd
import streamlit as st

import charts
from microgrid.config import load_config
from microgrid.grid import PandapowerGrid
from microgrid.kpi import compare, compute
from microgrid.sim.loop import time_index
from microgrid.sim.scenarios import SCENARIOS, apply_overrides, simulate
from microgrid.sim.setup import SAHTE, TEMSILI_GUNLER, load_inputs, with_start
from microgrid.simulink_io import critical_moment, list_outputs, outputs_dir, status_table, summarize

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
cfg_json = json.dumps(cfg, sort_keys=True, default=str)
steps, station, source = run_cached(cfg_json, scenario_name, with_grid)
BASELINE = "S2 Kontrolsüz şarj"   # akıllı senaryolar buna göre kıyaslanır

# ---- Başlık ----
st.title("Mikro-Şebeke + EV Şarj İstasyonu")
if source == SAHTE:
    st.warning("Gerçek veri dosyaları bulunamadı; **sahte girdilerle** çalışılıyor. Bu sayılar raporda kullanılmamalı. "
               "Gerçek veri için bir kez: `python -m microgrid.data`", icon="⚠️")
if scenario.temporary:
    st.info("Bu senaryo henüz sahte istasyon/EMS modülüyle çalışıyor; YM-2/YM-3 modülleri gelince sonuçlar değişecek.",
            icon="ℹ️")

# ---- KPI kartları (YM-1'in KPI modülü; tanımlar src/microgrid/kpi.py) ----
k = compute(steps, cfg)
ref = compute(run_cached(cfg_json, BASELINE, with_grid)[0], cfg) if scenario_name != BASELINE else None


def card(col, label, key, fmt, unit="", inverse=True, help=None):
    """inverse=True: düşmesi iyi olan göstergeler (tepe, maliyet) yeşil görünür."""
    value = k[key]
    delta = None
    if ref is not None and value == value and ref[key] == ref[key]:   # NaN değilse
        delta = f"{value - ref[key]:+{fmt}} {unit}".strip() + f" ({BASELINE.split()[0]}'ye göre)"
    tr = lambda t: t.replace(",", ".")   # Türkçe binlik ayırıcı: 3.975 TL
    col.metric(label, tr(f"{value:{fmt}} {unit}".strip()) if value == value else "—", delta and tr(delta),
               delta_color="inverse" if inverse else "normal", help=help)


row1 = st.columns(4)
card(row1[0], "Şebeke tepe alımı", "tepe_alim_kw", ".0f", "kW", help=f"Saat: {k['tepe_alim_saati']}")
card(row1[1], "Puant tepe alımı (17–22)", "puant_tepe_alim_kw", ".0f", "kW")
card(row1[2], "Günlük maliyet", "maliyet_tl", ",.0f", "TL")
card(row1[3], "Araç şarjının puanttaki payı", "arac_sarj_puant_payi", ".0%")
row2 = st.columns(4)
card(row2[0], "Araç şarjı", "arac_sarj_kwh", ".0f", "kWh", inverse=False)
card(row2[1], "PV öz tüketim oranı", "oz_tuketim_orani", ".0%", inverse=False)
card(row2[2], "Site sınırı aşımı", "site_siniri_asim_adim", ".0f", "adım")
card(row2[3], "En düşük gerilim", "min_gerilim_pu", ".3f", "p.u.", inverse=False)

# ---- Sekmeler ----
tab_flow, tab_station, tab_grid, tab_cmp, tab_dyn, tab_data = st.tabs(
    ["Güç akışları", "Şarj istasyonu", "Şebeke", "Senaryo karşılaştırması", "Dinamik (Simulink)", "Veri"])

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

with tab_cmp:
    st.caption("Aynı gün ve parametrelerle bütün senaryolar. Kontrolsüz şarjın akşam tepesi akıllı şarjla nereye gidiyor?")
    results = {name: run_cached(cfg_json, name, with_grid)[0] for name in SCENARIOS}
    st.plotly_chart(charts.scenario_comparison(results, cfg), width="stretch")
    table = compare(results, cfg)
    shown = ["tepe_alim_kw", "tepe_alim_saati", "puant_tepe_alim_kw", "maliyet_tl", "arac_sarj_kwh",
             "arac_sarj_puant_payi", "alim_puant_kwh", "alim_gece_kwh", "oz_tuketim_orani", "site_siniri_asim_adim",
             "min_gerilim_pu", "max_kablo_yuklenme_pct", "max_trafo_yuklenme_pct"]
    st.dataframe(table.loc[shown].map(lambda v: f"{v:.2f}" if isinstance(v, float) else v), width="stretch")
    st.download_button("KPI tablosunu indir (CSV)", table.to_csv().encode("utf-8"), file_name=f"kpi_{day}.csv")

with tab_dyn:
    band = tuple(cfg["simulink"]["freq_band_pu"])
    runs = list_outputs(outputs_dir(cfg))

    st.subheader("Simülasyon → Simulink: günün kritik anı")
    st.caption("Seçili senaryoda şebekeyi en çok zorlayan adım. EM ekibi D2 (toplu araç bağlanması) gibi "
               "dinamik senaryoları bu değerlerle başlatır; böylece iki katman aynı anı anlatır.")
    cm = critical_moment(steps, cfg)
    st.dataframe(pd.DataFrame([cm]).round(3), hide_index=True, width="stretch")

    st.subheader("Dinamik senaryolar (EM-1, EM-2)")
    st.dataframe(status_table(runs), hide_index=True, width="stretch")
    for r in runs:
        if r.error:
            st.error(r.error, icon="🚫")

    ok = [r for r in runs if r.error is None]
    if not ok:
        st.info(f"`{cfg['simulink']['outputs_dir']}/` altında henüz CSV yok. Biçim: docs/arayuz-sozlesmesi.md, bölüm 5. "
                "Dosya adı örneği: `D1_yuk_basamagi.csv`. GitHub'a web arayüzünden yükleme adımları: docs/calisma-duzeni.md.")
    else:
        i = st.selectbox("Dosya", range(len(ok)), format_func=lambda j: f"{ok[j].code} · {ok[j].title}")
        choice = ok[i]
        sm = summarize(choice.data, band)
        c = st.columns(4)
        c[0].metric("En düşük frekans", f"{sm['f_min_hz']:.3f} Hz", help=f"t = {sm['f_min_t_s']:.2f} s")
        c[1].metric("Bant dışında kalma", f"{sm['bant_disi_s']:.2f} s",
                    help="Banda son dönüş: " + (f"{sm['banda_donus_t_s']:.2f} s" if sm["banda_donus_t_s"] else "hiç çıkmadı"))
        c[2].metric("En düşük PCC gerilimi", f"{sm['v_min_pu']:.3f} p.u.")
        c[3].metric("En yüksek şebeke gücü", f"{sm['p_grid_max_kw']:.0f} kW")
        st.plotly_chart(charts.simulink_dynamics(choice.data, band), width="stretch")

with tab_data:
    st.dataframe(steps, width="stretch")
    st.download_button("Adım tablosunu indir (CSV)", steps.to_csv().encode("utf-8"),
                       file_name=f"{scenario_name.split()[0]}_{day}_steps.csv")
