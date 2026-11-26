"""Dashboard grafikleri (YM-4). Yalnızca döngünün sonuç tablolarını okur (docs/arayuz-sozlesmesi.md, bölüm 4).

Grafik fonksiyonları Streamlit'ten bağımsız: aynı figürler rapor ve sunum için de kullanılabilir.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

# Seriler her grafikte aynı renkte olsun (rapor ve sunumda da)
COLORS = {
    "pv_kw": "#E0A100",          # güneş
    "base_load_kw": "#7A8793",   # sabit yük
    "ev_kw": "#D1495B",          # şarj istasyonu: projenin odağı, en belirgin renk
    "bess_kw": "#2E86AB",        # batarya
    "grid_kw": "#2A2A2A",        # şebeke
}
LABELS = {
    "pv_kw": "PV üretimi",
    "base_load_kw": "Sabit yük (site)",
    "ev_kw": "Şarj istasyonu (+ şarj / − V2G)",
    "bess_kw": "Batarya (+ şarj / − deşarj)",
    "grid_kw": "Şebekeden alım (+) / veriş (−)",
}
PUANT = (17, 22)   # EPDK puant dilimi; grafiklerde gölgelenir


def _puant_bands(fig: go.Figure, index: pd.DatetimeIndex) -> None:
    """Puant saatlerini (17-22) gölgeler: tepe yükün pahalı saate denk geldiği görünsün."""
    for day in pd.Series(index.normalize().unique()):
        x0, x1 = day + pd.Timedelta(hours=PUANT[0]), day + pd.Timedelta(hours=PUANT[1])
        if x1 < index[0] or x0 > index[-1]:
            continue
        fig.add_vrect(x0=max(x0, index[0]), x1=min(x1, index[-1]), fillcolor="#D1495B", opacity=0.07,
                      line_width=0, annotation_text="puant", annotation_position="top left")


def power_flows(steps: pd.DataFrame, cfg: dict) -> go.Figure:
    fig = go.Figure()
    for col in ["pv_kw", "base_load_kw", "ev_kw", "bess_kw", "grid_kw"]:
        fig.add_trace(go.Scatter(
            x=steps.index, y=steps[col], name=LABELS[col], mode="lines",
            line=dict(color=COLORS[col], width=3.2 if col in ("ev_kw", "grid_kw") else 1.8,
                      dash="dot" if col == "bess_kw" else None),
            hovertemplate="%{y:.1f} kW",
        ))
    fig.add_hline(y=cfg["grid"]["site_import_limit_kw"], line_dash="dash", line_color="#2A2A2A",
                  annotation_text=f"site sınırı {cfg['grid']['site_import_limit_kw']} kW", annotation_position="top right")
    fig.add_hline(y=cfg["station"]["power_limit_kw"], line_dash="dot", line_color=COLORS["ev_kw"],
                  annotation_text=f"istasyon sınırı {cfg['station']['power_limit_kw']} kW",
                  annotation_position="bottom right")
    _puant_bands(fig, steps.index)
    fig.update_layout(yaxis_title="kW", hovermode="x unified", height=440, margin=dict(t=30, b=10),
                      legend=dict(orientation="h", y=-0.18))
    return fig


def charger_heatmap(station: pd.DataFrame, cfg: dict) -> go.Figure:
    """Ünite × zaman: her hücre o ünitenin o adımda çektiği güç. Boş hücre = ünite boş."""
    chargers = [f"{c['kind']}{i + 1}" for c in cfg["station"]["chargers"] for i in range(c["count"])]
    if station.empty:
        pivot = pd.DataFrame(index=chargers)
    else:
        pivot = station.pivot_table(index="charger_id", columns="timestamp", values="power_kw", aggfunc="sum")
        pivot = pivot.reindex(chargers)
    z = pivot.to_numpy()
    v2g = bool((pivot.fillna(0) < -1e-9).to_numpy().any())
    if v2g:   # V2G: deşarj (−) mavi, şarj (+) kırmızı, 0 beyaz
        lim = float(abs(pivot).max().max())
        scale = dict(colorscale="RdBu_r", zmin=-lim, zmax=lim, zmid=0)
    else:
        scale = dict(colorscale="Reds", zmin=0)
    fig = go.Figure(go.Heatmap(
        z=z, x=pivot.columns, y=pivot.index, **scale,
        colorbar=dict(title="kW (− V2G)" if v2g else "kW"), hovertemplate="%{y} %{x|%H:%M}: %{z:.1f} kW<extra></extra>",
    ))
    fig.update_layout(height=60 + 28 * len(chargers), margin=dict(t=10, b=10),
                      yaxis=dict(autorange="reversed", title="ünite"))
    return fig


def vehicle_soc(station: pd.DataFrame, cfg: dict) -> go.Figure:
    """Her aracın SOC'si bağlı kaldığı süre boyunca; kesikli çizgi hedef SOC."""
    fig = go.Figure()
    for vid, g in station.groupby("vehicle_id"):
        fig.add_trace(go.Scatter(x=g["timestamp"], y=g["soc"], name=vid, mode="lines",
                                 line=dict(width=1.4), hovertemplate=f"{vid}: %{{y:.0%}}<extra></extra>"))
    fig.add_hline(y=cfg["vehicles"]["target_soc"], line_dash="dash", annotation_text="hedef SOC")
    fig.update_layout(yaxis=dict(title="SOC", tickformat=".0%", range=[0, 1]), height=320,
                      margin=dict(t=10, b=10), showlegend=False)
    return fig


def grid_quality(steps: pd.DataFrame, cfg: dict) -> go.Figure:
    """Yük akışı sonuçları: en düşük gerilim ve kablo/trafo yüklenmesi (iki eksen)."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=steps.index, y=steps["min_vm_pu"], name="En düşük gerilim (p.u.)",
                             line=dict(color="#2E86AB", width=2.4)))
    fig.add_hline(y=cfg["grid"]["voltage_min_pu"], line_dash="dash", line_color="#2E86AB",
                  annotation_text=f"alt sınır {cfg['grid']['voltage_min_pu']} p.u.")
    fig.add_trace(go.Scatter(x=steps.index, y=steps["max_line_loading_pct"], name="En yüklü kablo (%)",
                             yaxis="y2", line=dict(color="#D1495B")))
    fig.add_trace(go.Scatter(x=steps.index, y=steps["trafo_loading_pct"], name="Trafo (%)",
                             yaxis="y2", line=dict(color="#7A8793", dash="dot")))
    _puant_bands(fig, steps.index)
    fig.update_layout(
        yaxis=dict(title="gerilim (p.u.)"),
        yaxis2=dict(title="yüklenme (%)", overlaying="y", side="right", rangemode="tozero"),
        height=380, hovermode="x unified", margin=dict(t=30, b=10), legend=dict(orientation="h", y=-0.2),
    )
    return fig


SCENARIO_COLORS = ["#7A8793", "#D1495B", "#2E86AB", "#3B8C4A", "#E0A100", "#6C4AB6"]


def scenario_comparison(results: dict, cfg: dict) -> go.Figure:
    """Senaryoların şebeke alımı (üst) ve istasyon gücü (alt) üst üste. results: {senaryo adı: adım tablosu}."""
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=("Şebekeden alım (kW)", "Şarj istasyonu gücü (kW)"))
    for i, (name, steps) in enumerate(results.items()):
        color = SCENARIO_COLORS[i % len(SCENARIO_COLORS)]
        for row, col in ((1, "grid_kw"), (2, "ev_kw")):
            fig.add_trace(go.Scatter(x=steps.index, y=steps[col], name=name, legendgroup=name, showlegend=row == 1,
                                     line=dict(color=color, width=2.6), hovertemplate=f"{name}: %{{y:.1f}} kW"),
                          row=row, col=1)
    fig.add_hline(y=cfg["grid"]["site_import_limit_kw"], line_dash="dash", row=1, col=1,
                  annotation_text="site sınırı", annotation_position="top right")
    first = next(iter(results.values()))
    _puant_bands(fig, first.index)
    fig.update_layout(height=560, hovermode="x unified", margin=dict(t=40, b=10), legend=dict(orientation="h", y=-0.1))
    return fig


def simulink_dynamics(df: pd.DataFrame, band: tuple[float, float]) -> go.Figure:
    """Simulink çıktısı: frekans (bant ile), PCC gerilimi ve güçler; x ekseni saniye."""
    from plotly.subplots import make_subplots

    power_cols = {"p_grid_kw": ("Şebeke", COLORS["grid_kw"]), "p_ev_ac_kw": ("İstasyon AC", COLORS["ev_kw"]),
                  "p_ev_dc_kw": ("İstasyon DC", "#8E2C3A"), "p_bess_kw": ("Batarya", COLORS["bess_kw"]),
                  "p_pv_kw": ("PV", COLORS["pv_kw"]), "p_load_kw": ("Sabit yük", COLORS["base_load_kw"])}
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        subplot_titles=("Frekans (Hz)", "PCC gerilimi (p.u.)", "Güçler (kW)"))
    t = df.index
    fig.add_trace(go.Scatter(x=t, y=df["freq_pu"] * 50, name="Frekans", line=dict(color="#2A2A2A", width=2),
                             hovertemplate="%{y:.3f} Hz"), row=1, col=1)
    fig.add_hrect(y0=band[0] * 50, y1=band[1] * 50, fillcolor="#3B8C4A", opacity=0.12, line_width=0, row=1, col=1,
                  annotation_text=f"bant {band[0] * 50:.2f}–{band[1] * 50:.2f} Hz", annotation_position="top left")
    fig.add_trace(go.Scatter(x=t, y=df["v_pcc_pu"], name="PCC gerilimi", line=dict(color="#2E86AB", width=2),
                             hovertemplate="%{y:.3f} p.u."), row=2, col=1)
    for col, (label, color) in power_cols.items():
        if col in df.columns:
            fig.add_trace(go.Scatter(x=t, y=df[col], name=label, line=dict(color=color, width=1.8),
                                     hovertemplate="%{y:.1f} kW"), row=3, col=1)
    fig.update_xaxes(title_text="zaman (s)", row=3, col=1)
    fig.update_layout(height=720, hovermode="x unified", margin=dict(t=40, b=10), legend=dict(orientation="h", y=-0.08))
    return fig
