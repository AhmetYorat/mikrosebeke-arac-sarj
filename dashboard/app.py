"""Streamlit dashboard (YM-4). Çalıştırma: streamlit run dashboard/app.py

Senaryo ve temsili gün seçilir, döngü çalışır, sonuçlar sekmelerde gösterilir.
Veri dosyaları yoksa (python -m microgrid.data çalıştırılmadıysa) sahte girdilerle çalışır ve bunu üstte yazar.
"""
import json
import time

import pandas as pd
import streamlit as st

import charts
import sema
from microgrid.config import load_config
from microgrid.grid import PandapowerGrid
from microgrid.sim.loop import SimResult, time_index
from microgrid.sim.scenarios import SCENARIOS, apply_overrides, simulate
from microgrid.sim.setup import SAHTE, TEMSILI_GUNLER, load_inputs, with_start
from microgrid.sim.sonuclar import SHOWN, fmt, kpi_row, kpi_table
from microgrid.simulink_io import critical_moment, list_outputs, outputs_dir, status_table, summarize

st.set_page_config(page_title="Mikro-Şebeke + EV Şarj İstasyonu", page_icon="⚡", layout="wide")
st.html(sema.CSS)
base = load_config()


@st.cache_data(show_spinner="Simülasyon çalışıyor…")
def run_cached(cfg_json: str, scenario_name: str, with_grid: bool):
    """Aynı ayarlar ikinci kez seçilince tekrar hesaplanmasın. Sonuç (SimResult) ve girdi kaynağı döner."""
    cfg = json.loads(cfg_json)
    inputs, source = load_inputs(cfg, time_index(cfg))
    grid = PandapowerGrid(cfg) if with_grid else None
    return simulate(cfg, SCENARIOS[scenario_name], inputs, grid), source


# ---- Kenar çubuğu: senaryo ve parametreler ----
with st.sidebar:
    st.markdown("### ⚡ Kontrol paneli")
    st.caption("Senaryoyu ve günü seçin; şema, kartlar ve grafikler birlikte değişir.")
    st.header("Senaryo")
    names = list(SCENARIOS)
    # ?senaryo=S6 ile doğrudan bir senaryoya açılır (demo bağlantıları için)
    wanted = st.query_params.get("senaryo", "S2")
    default = next((i for i, n in enumerate(names) if n.split()[0].lower() == wanted.lower()), names.index("S2 Kontrolsüz şarj"))
    scenario_name = st.selectbox("Senaryo", names, index=default)
    scenario = SCENARIOS[scenario_name]
    st.caption(scenario.description)
    day = st.radio("Temsili gün", list(TEMSILI_GUNLER), format_func=lambda d: sema.GUN_ADI.get(d, d.capitalize()), horizontal=True,
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
result, source = run_cached(cfg_json, scenario_name, with_grid)
steps, station, sessions = result.steps, result.station, result.sessions
BASELINE = "S2 Kontrolsüz şarj"   # akıllı senaryolar buna göre kıyaslanır

# ---- Başlık ----
st.html(sema.masthead(scenario_name, scenario.description, day, source != SAHTE))
if source == SAHTE:
    st.warning("Gerçek veri dosyaları bulunamadı; **sahte girdilerle** çalışılıyor. Bu sayılar raporda kullanılmamalı. "
               "Gerçek veri için bir kez: `python -m microgrid.data`", icon="⚠️")
if scenario.temporary:
    st.info("Bu senaryo henüz sahte istasyon modülüyle çalışıyor (CC-CV eğrisi yok); YM-2 istasyonu gelince sonuçlar değişecek.",
            icon="ℹ️")

# ---- KPI kartları: YM-1 (şebeke, maliyet) + YM-2 (kullanıcı memnuniyeti) + V2G; tanımlar sim/sonuclar.py ----
k = kpi_row(result, cfg)
ref = kpi_row(run_cached(cfg_json, BASELINE, with_grid)[0], cfg) if scenario_name != BASELINE else None
n_reached = int(sessions.reached_target.sum()) if len(sessions) else 0
st.html(sema.kpi_cards(k, ref, len(sessions), n_reached, cfg["grid"]["site_import_limit_kw"]))

# ---- Canlı şema: seçilen saatte güç akışları ve otopark ----
LABELS_T = [t.strftime("%H:%M") for t in steps.index]


@st.fragment
def canli_sema():
    """Saat kaydırıcısı + oynat: yalnızca bu bölüm yeniden çizilir, sayfanın geri kalanı beklemez."""
    owner = (scenario_name, day)
    if st.session_state.get("t_owner") != owner or st.session_state.get("t_lbl") not in LABELS_T:
        st.session_state["t_lbl"] = steps["grid_kw"].idxmax().strftime("%H:%M")   # açılışta günün tepe anı
        st.session_state["t_owner"] = owner
    head, play_col = st.columns([5, 1.2], vertical_alignment="bottom")
    with play_col:
        playing = st.toggle("▶ Oynat", key="play", help="Günü 15 dakikalık adımlarla oynatır.")
    if playing:
        i = LABELS_T.index(st.session_state["t_lbl"])
        st.session_state["t_lbl"] = LABELS_T[(i + 1) % len(LABELS_T)]
    with head:
        label = st.select_slider("Saat (öğlenden ertesi öğlene)", LABELS_T, key="t_lbl")
    t = steps.index[LABELS_T.index(label)]
    row = steps.loc[t]
    at_t = station[station["timestamp"] == t] if len(station) else station
    left, right = st.columns([1.4, 1], gap="medium")
    with left:
        st.html('<div class="mk-panel"><h4>Canlı tek hat şeması · ' + label + '</h4>'
                + sema.single_line(row, cfg, len(at_t)) + "</div>")
    with right:
        price = row["price_tl_per_kwh"]
        band = "puant" if price >= 6 else "gece" if price < 3.5 else "gündüz"
        st.html('<div class="mk-panel"><h4>Otopark · 10 ünite</h4>' + sema.parking(at_t, sessions, t, cfg)
                + f'<div class="mk-legend">Tarife: <b>{sema.tr(price, 2)} TL/kWh</b> ({band}) · '
                  f'Ünitede yazan güç o anki şarj gücü. Turuncu şarj, mavi V2G (araçtan şebekeye), yeşil bağlı ama şarj etmiyor.</div></div>')
    if playing:
        time.sleep(0.6)
        st.rerun(scope="fragment")


canli_sema()

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
        st.caption("Her satır bir şarj ünitesi; renk o adımda çekilen güç (V2G senaryosunda mavi: araçtan şebekeye). "
                   "Boş hücre: ünite boş ya da araç dolmuş.")
        st.plotly_chart(charts.charger_heatmap(station, cfg), width="stretch")
        st.subheader("Araçların doluluk oranı (SOC)")
        st.caption("Her çizgi bir araç, yalnızca şarj ihtiyacı olduğu sürece görünür.")
        st.plotly_chart(charts.vehicle_soc(station, cfg), width="stretch")
    if len(sessions):
        st.subheader("Araç oturumları")
        st.caption("Araç başına: ne zaman geldi, ünite için ne kadar bekledi, ne kadar enerji aldı, hedefe ulaştı mı (YM-2).")
        view = sessions.assign(
            varis=sessions.arrival.dt.strftime("%H:%M"), ayrilis=sessions.departure.dt.strftime("%H:%M"),
            bekleme_sa=sessions.waited_h.round(1), soc=lambda d: d.soc_arrival.map("{:.0%}".format) + " → "
            + d.soc_final.map("{:.0%}".format), enerji_kwh=sessions.energy_kwh.round(1),
            hedefe_ulasti=sessions.reached_target.map({True: "✓", False: "✗"}),
        )[["vehicle_id", "model", "varis", "ayrilis", "first_charger", "bekleme_sa", "soc", "enerji_kwh", "hedefe_ulasti"]]
        st.dataframe(view, hide_index=True, width="stretch")

with tab_grid:
    if steps["min_vm_pu"].notna().any():
        st.plotly_chart(charts.grid_quality(steps, cfg), width="stretch")
    else:
        st.write("Yük akışı kapalı. Kenar çubuğundan açın.")

with tab_cmp:
    st.caption("Aynı gün ve parametrelerle bütün senaryolar. Kontrolsüz şarjın akşam tepesi akıllı şarjla nereye gidiyor?")
    # Optimizasyon senaryoları (MILP) birkaç saniye sürer; karşılaştırma istenince çalışır, sonra önbellekten gelir.
    key = ("cmp", cfg_json, with_grid)
    if key not in st.session_state and st.button("Bütün senaryoları çalıştır", type="primary"):
        bar = st.progress(0.0)
        for i, name in enumerate(SCENARIOS):
            bar.progress(i / len(SCENARIOS), text=f"{name} çalışıyor…")
            run_cached(cfg_json, name, with_grid)
        bar.empty()
        st.session_state[key] = True
    if key in st.session_state:
        results = {name: run_cached(cfg_json, name, with_grid)[0] for name in SCENARIOS}
        st.markdown("##### Her senaryo kendi panelinde: şebekeden alım")
        st.caption("Kırmızı kesikli çizgi 180 kW site sınırı, turuncu bant puant (17–22), nokta günün tepesi.")
        st.plotly_chart(charts.scenario_small_multiples({n: r.steps for n, r in results.items()}, cfg), width="stretch")
        table = kpi_table(results, cfg)
        st.markdown("##### Puan kartı")
        st.caption("Çubuk boyu değerle orantılı; yeşil yazı o göstergede en iyi senaryo.")
        st.html(sema.scorecard(table))
        with st.expander("Bütün göstergeler (tablo)"):
            view = pd.DataFrame({title: [fmt(k_, table.at[k_, c]) for c in table.columns]
                                 for k_, title, _ in SHOWN if k_ in table.index}, index=table.columns).T
            st.dataframe(view, width="stretch", height=36 * (len(view) + 1) + 4)
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
