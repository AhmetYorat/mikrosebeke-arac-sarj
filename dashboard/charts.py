"""Dashboard grafikleri (YM-4). Yalnızca döngünün sonuç tablolarını okur (docs/arayuz-sozlesmesi.md, bölüm 4).

Grafik fonksiyonları Streamlit'ten bağımsız: aynı figürler rapor ve sunum için de kullanılabilir.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

# Ortak görünüm: sunum ve dashboard aynı dili konuşsun (krem zemin, lacivert yazı, ince ızgara)
pio.templates["mikro"] = go.layout.Template(layout=dict(
    font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color="#C7D4EA", size=13),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(11,18,32,0.85)",
    xaxis=dict(gridcolor="#16233A", linecolor="#1E2D47", zeroline=False),
    yaxis=dict(gridcolor="#16233A", linecolor="#1E2D47", zerolinecolor="#2A3E63"),
    hoverlabel=dict(bgcolor="#0E1626", font_color="#F1F6FF", bordercolor="#22D3EE",
                    font_family="ui-monospace, SF Mono, Menlo, Consolas, monospace"),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
))
pio.templates.default = "plotly_dark+mikro"

# Seriler her grafikte aynı renkte olsun (rapor ve sunumda da)
COLORS = {
    "pv_kw": "#FBBF24",          # güneş
    "base_load_kw": "#8FA6C8",   # sabit yük
    "ev_kw": "#FB923C",          # şarj istasyonu: projenin odağı, en belirgin renk
    "bess_kw": "#60A5FA",        # batarya
    "grid_kw": "#22D3EE",        # şebeke
}
LABELS = {
    "pv_kw": "PV üretimi",
    "base_load_kw": "Sabit yük (site)",
    "ev_kw": "Şarj istasyonu (+ şarj / − V2G)",
    "bess_kw": "Batarya (+ şarj / − deşarj)",
    "grid_kw": "Şebekeden alım (+) / veriş (−)",
}
PUANT = (17, 22)   # EPDK puant dilimi; grafiklerde gölgelenir


def _puant_bands(fig: go.Figure, index: pd.DatetimeIndex, **where) -> None:
    """Puant saatlerini (17-22) gölgeler: tepe yükün pahalı saate denk geldiği görünsün."""
    for day in pd.Series(index.normalize().unique()):
        x0, x1 = day + pd.Timedelta(hours=PUANT[0]), day + pd.Timedelta(hours=PUANT[1])
        if x1 < index[0] or x0 > index[-1]:
            continue
        fig.add_vrect(x0=max(x0, index[0]), x1=min(x1, index[-1]), fillcolor="#FBBF24", opacity=0.07,
                      line_width=0, **({"annotation_text": "puant", "annotation_position": "top left"} if not where else {}),
                      **where)


def power_flows(steps: pd.DataFrame, cfg: dict) -> go.Figure:
    fig = go.Figure()
    for col in ["pv_kw", "base_load_kw", "ev_kw", "bess_kw", "grid_kw"]:
        fig.add_trace(go.Scatter(
            x=steps.index, y=steps[col], name=LABELS[col], mode="lines",
            line=dict(color=COLORS[col], width=3.2 if col in ("ev_kw", "grid_kw") else 1.8,
                      dash="dot" if col == "bess_kw" else None),
            hovertemplate="%{y:.1f} kW",
        ))
    fig.add_hline(y=cfg["grid"]["site_import_limit_kw"], line_dash="dash", line_color="#F87171",
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
        scale = dict(colorscale=[[0, "#93C5FD"], [0.25, "#2563EB"], [0.5, "#13203A"], [0.75, "#C2410C"], [1, "#FDBA74"]], zmin=-lim, zmax=lim, zmid=0)
    else:
        scale = dict(colorscale=[[0, "#13203A"], [0.5, "#C2410C"], [1, "#FDBA74"]], zmin=0)
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
                             line=dict(color="#60A5FA", width=2.4)))
    fig.add_hline(y=cfg["grid"]["voltage_min_pu"], line_dash="dash", line_color="#60A5FA",
                  annotation_text=f"alt sınır {cfg['grid']['voltage_min_pu']} p.u.")
    fig.add_trace(go.Scatter(x=steps.index, y=steps["max_line_loading_pct"], name="En yüklü kablo (%)",
                             yaxis="y2", line=dict(color="#F87171")))
    fig.add_trace(go.Scatter(x=steps.index, y=steps["trafo_loading_pct"], name="Trafo (%)",
                             yaxis="y2", line=dict(color="#8FA6C8", dash="dot")))
    _puant_bands(fig, steps.index)
    fig.update_layout(
        yaxis=dict(title="gerilim (p.u.)"),
        yaxis2=dict(title="yüklenme (%)", overlaying="y", side="right", rangemode="tozero"),
        height=380, hovermode="x unified", margin=dict(t=30, b=10), legend=dict(orientation="h", y=-0.2),
    )
    return fig


SCENARIO_COLORS = ["#7D8FB3", "#EA6A12", "#3B82F6", "#10B981", "#8B5CF6", "#B88A00"]   # koyu zeminde doğrulandı; S1 nötr taban


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
                  "p_ev_dc_kw": ("İstasyon DC", "#F97316"), "p_bess_kw": ("Batarya", COLORS["bess_kw"]),
                  "p_pv_kw": ("PV", COLORS["pv_kw"]), "p_load_kw": ("Sabit yük", COLORS["base_load_kw"])}
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        subplot_titles=("Frekans (Hz)", "PCC gerilimi (p.u.)", "Güçler (kW)"))
    t = df.index
    fig.add_trace(go.Scatter(x=t, y=df["freq_pu"] * 50, name="Frekans", line=dict(color="#22D3EE", width=2),
                             hovertemplate="%{y:.3f} Hz"), row=1, col=1)
    fig.add_hrect(y0=band[0] * 50, y1=band[1] * 50, fillcolor="#34D399", opacity=0.12, line_width=0, row=1, col=1,
                  annotation_text=f"bant {band[0] * 50:.2f}–{band[1] * 50:.2f} Hz", annotation_position="top left")
    fig.add_trace(go.Scatter(x=t, y=df["v_pcc_pu"], name="PCC gerilimi", line=dict(color="#60A5FA", width=2),
                             hovertemplate="%{y:.3f} p.u."), row=2, col=1)
    for col, (label, color) in power_cols.items():
        if col in df.columns:
            fig.add_trace(go.Scatter(x=t, y=df[col], name=label, line=dict(color=color, width=1.8),
                                     hovertemplate="%{y:.1f} kW"), row=3, col=1)
    fig.update_xaxes(title_text="zaman (s)", row=3, col=1)
    fig.update_layout(height=720, hovermode="x unified", margin=dict(t=40, b=10), legend=dict(orientation="h", y=-0.08))
    return fig


def scenario_small_multiples(results: dict, cfg: dict, marker=None) -> go.Figure:
    """Her senaryo kendi panelinde: şebeke alımı alan grafiği, site sınırı ve tepe noktası. Üst üste binen
    çizgiler yerine yan yana küçük paneller: hangi senaryonun nerede sınıra dayandığı bir bakışta görünür."""
    from plotly.subplots import make_subplots

    names = list(results)
    cols = 3
    rows = -(-len(names) // cols)
    fig = make_subplots(rows=rows, cols=cols, shared_xaxes=True, shared_yaxes=True,
                        horizontal_spacing=0.03, vertical_spacing=0.12, subplot_titles=names)
    lim = cfg["grid"]["site_import_limit_kw"]
    for i, name in enumerate(names):
        s = results[name]
        r, c = i // cols + 1, i % cols + 1
        color = SCENARIO_COLORS[i % len(SCENARIO_COLORS)]
        fig.add_trace(go.Scatter(x=s.index, y=s["grid_kw"], mode="lines", line=dict(color=color, width=2.4),
                                 fill="tozeroy", fillcolor=_rgba(color, 0.18), name=name, showlegend=False,
                                 hovertemplate=f"{name.split()[0]} %{{x|%H:%M}}: %{{y:.0f}} kW<extra></extra>"), row=r, col=c)
        peak_t = s["grid_kw"].idxmax()
        fig.add_trace(go.Scatter(x=[peak_t], y=[s["grid_kw"].max()], mode="markers+text",
                                 marker=dict(color=color, size=9, line=dict(color="#070B14", width=2)),
                                 text=[f"{s['grid_kw'].max():.0f} kW · {peak_t:%H:%M}"], textposition="top center",
                                 textfont=dict(size=11, color="#F1F6FF", family="ui-monospace, Menlo, monospace"), showlegend=False, hoverinfo="skip"), row=r, col=c)
        fig.add_hline(y=lim, line_dash="dash", line_color="#F87171", line_width=1.2, row=r, col=c)
        if marker is not None:
            fig.add_vline(x=marker, line_color="#C7D4EA", line_width=1, opacity=0.35, row=r, col=c)
    _puant_bands(fig, next(iter(results.values())).index, row="all", col="all")
    fig.update_annotations(font=dict(size=13, color="#C7D4EA"))
    fig.update_xaxes(tickformat="%H:%M", dtick=6 * 3600 * 1000)
    fig.update_yaxes(range=[min(-60, min(s["grid_kw"].min() for s in results.values()) - 10),
                            max(lim, max(s["grid_kw"].max() for s in results.values())) + 45])
    fig.update_layout(height=250 * rows + 40, margin=dict(t=40, b=10, l=10, r=10))
    return fig


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"
