"""Dashboard'un özel görünümü (YM-4): tema, başlık, KPI kartları, canlı tek hat şeması, otopark ve puan kartı.

Hepsi saf HTML/SVG üreten fonksiyonlar; Streamlit'e st.html ile verilir. JavaScript yok, animasyonlar CSS ile.
Renkler sunumla aynı (lacivert + turuncu), böylece slayt ve demo tek bir görsel dil konuşur.
"""
from __future__ import annotations

import base64
import html
import math

import pandas as pd

INK, PAPER, SAND, LINE, SOFT = "#1C2A3A", "#FDFCF8", "#F6F3EC", "#DCD6C8", "#5B6573"
ACCENT, GOOD, BAD, BLUE, SUN = "#E0662F", "#2F8F5B", "#C2412D", "#2468C4", "#D99A00"

GUN_ADI = {"haziran": "Haziran", "aralik": "Aralık"}   # sözlük anahtarları ASCII, ekranda Türkçe

# Senaryo renkleri: sunumdaki grafiklerle aynı (S1 gri, S2 turuncu, S3 mavi, S4 yeşil, S5 mor, S6 altın)
SCENARIO_COLORS = {"S1": "#9AA0A8", "S2": "#F47230", "S3": "#257DE0", "S4": "#00A383", "S5": "#6A4CE2", "S6": "#C99700"}


def tr(x: float, digits: int = 0) -> str:
    """Türkçe sayı: binlik nokta, ondalık virgül (3.975 · 0,961)."""
    s = f"{x:,.{digits}f}"
    return s.replace(",", "\0").replace(".", ",").replace("\0", ".")


CSS = f"""
<style>
:root {{ --ink:{INK}; --paper:{PAPER}; --sand:{SAND}; --line:{LINE}; --soft:{SOFT}; --accent:{ACCENT}; }}
.stApp {{ background: var(--sand); }}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 1.2rem; max-width: 1500px; }}
h1, h2, h3 {{ font-family: Georgia, 'Times New Roman', serif !important; color: var(--ink); letter-spacing: -0.01em; }}
section[data-testid="stSidebar"] {{ background: var(--paper); border-right: 1px solid var(--line); }}
.stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 2px solid var(--line); }}
.stTabs [data-baseweb="tab"] {{ padding: 10px 16px; font-weight: 600; color: var(--soft); }}
.stTabs [aria-selected="true"] {{ color: var(--ink); }}
.mk-mast {{ background: var(--ink); color: #F2EEE4; border-radius: 18px; padding: 22px 28px; display:flex;
  justify-content: space-between; align-items: flex-end; gap: 24px; margin-bottom: 14px; }}
.mk-mast .eyebrow {{ font-size: 12px; letter-spacing: .18em; text-transform: uppercase; color: #F2A27E; font-weight: 700; }}
.mk-mast h1 {{ color: #F2EEE4 !important; font-size: 34px; margin: 4px 0 2px; padding: 0; }}
.mk-mast .sub {{ color: #B9C3CE; font-size: 15px; }}
.mk-chip {{ display:inline-block; padding: 5px 12px; border-radius: 999px; font-size: 13px; font-weight: 600;
  margin-left: 6px; border: 1px solid #3A4C60; color: #F2EEE4; white-space: nowrap; }}
.mk-chip.ok {{ background: #1F4D3A; border-color: #2F8F5B; }}
.mk-chip.warn {{ background: #5A2A1E; border-color: {BAD}; }}
.mk-kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 4px 0 8px; }}
.mk-kpi {{ background: var(--paper); border: 1px solid var(--line); border-radius: 16px; padding: 14px 18px 12px;
  position: relative; overflow: hidden; }}
.mk-kpi::before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:5px; background: var(--c, var(--line)); }}
.mk-kpi .lbl {{ font-size: 13px; color: var(--soft); font-weight: 600; }}
.mk-kpi .val {{ font-family: Georgia, serif; font-size: 36px; color: var(--ink); line-height: 1.1; margin-top: 4px; }}
.mk-kpi .val small {{ font-family: inherit; font-size: 16px; color: var(--soft); margin-left: 4px; }}
.mk-kpi .foot {{ font-size: 12.5px; color: var(--soft); margin-top: 4px; min-height: 18px; }}
.mk-pill {{ display:inline-block; padding: 1px 8px; border-radius: 999px; font-weight: 700; font-size: 12px; margin-right: 6px; }}
.mk-pill.up {{ background:#FBE3DC; color:{BAD}; }} .mk-pill.down {{ background:#DDF1E5; color:{GOOD}; }}
.mk-pill.flat {{ background:#ECE8DF; color:{SOFT}; }}
.mk-mini {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; margin-bottom: 6px; }}
.mk-mini div {{ background: transparent; border-top: 2px solid var(--line); padding: 6px 2px; font-size: 12.5px; color: var(--soft); }}
.mk-mini b {{ display:block; font-size: 18px; color: var(--ink); font-family: Georgia, serif; font-weight: 600; }}
.mk-panel {{ background: var(--paper); border: 1px solid var(--line); border-radius: 18px; padding: 14px 16px; }}
.mk-panel h4 {{ margin: 0 0 6px; font-size: 13px; letter-spacing:.12em; text-transform: uppercase; color: var(--soft); }}
@keyframes mk-flow {{ to {{ stroke-dashoffset: -28; }} }}
.mk-flow {{ stroke-dasharray: 10 18; animation: mk-flow linear infinite; }}
.mk-bays {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 6px; }}
.mk-bay {{ border: 1.5px dashed var(--line); border-radius: 12px; padding: 8px 8px 7px; min-height: 92px; background: var(--sand);
  display:flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--soft); min-width: 0; overflow: hidden; }}
.mk-bay.on {{ border: 1.5px solid var(--c); background: var(--paper); }}
.mk-bay .id {{ font-weight: 700; color: var(--ink); display:flex; justify-content: space-between; font-size: 11.5px; gap: 4px; flex-wrap: wrap; }}
.mk-bay .id span {{ color: var(--soft); font-weight: 600; }}
.mk-bay .car {{ font-size: 20px; line-height: 1.1; }} .mk-bay .car span {{ font-size: 15px; font-weight: 700; color: var(--ink); }}
.mk-bay .bar {{ height: 8px; border-radius: 4px; background: #E6E0D3; overflow: hidden; }}
.mk-bay .bar i {{ display:block; height: 100%; background: var(--c); }}
.mk-bay .kw {{ font-weight: 700; color: var(--c); font-size: 12px; line-height: 1.2; white-space: nowrap; }}
.mk-queue {{ margin-top: 10px; font-size: 13px; color: var(--soft); }}
.mk-queue span {{ display:inline-block; background: #FBE3DC; color: {BAD}; border-radius: 8px; padding: 2px 8px; margin: 2px 4px 0 0; font-weight: 600; }}
.mk-score {{ width: 100%; border-collapse: separate; border-spacing: 0 6px; font-size: 14px; }}
.mk-score th {{ text-align: left; font-size: 12px; color: var(--soft); font-weight: 700; padding: 0 10px; }}
.mk-score td {{ background: var(--paper); padding: 9px 10px; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }}
.mk-score td:first-child {{ border-left: 5px solid var(--c); border-radius: 10px 0 0 10px; font-weight: 700; color: var(--ink); }}
.mk-score td:last-child {{ border-right: 1px solid var(--line); border-radius: 0 10px 10px 0; }}
.mk-score .cell {{ display:flex; align-items:center; gap: 8px; white-space: nowrap; }}
.mk-score .cell i {{ display:block; height: 8px; border-radius: 4px; background: var(--c); opacity: .75; }}
.mk-score .best {{ color: {GOOD}; font-weight: 800; }}
.mk-note {{ background: #FFF6EE; border: 1px solid #F2C9A8; border-left: 5px solid var(--accent); border-radius: 14px;
  padding: 12px 18px 6px; margin: 10px 0 6px; }}
.mk-note-h {{ font-size: 12px; letter-spacing: .14em; text-transform: uppercase; font-weight: 800; color: #A9461A; margin-bottom: 4px; }}
.mk-note ul {{ margin: 0; padding-left: 0; list-style: none; }}
.mk-note li {{ font-size: 15px; line-height: 1.45; color: var(--ink); margin: 0 0 7px; }}
.mk-explain {{ background: var(--paper); border: 1px solid var(--line); border-radius: 18px; padding: 14px 18px 10px; margin: 0 0 12px; }}
.mk-ladder {{ display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 6px; margin-bottom: 12px; }}
.mk-step {{ border: 1.5px solid var(--line); border-radius: 10px; padding: 6px 8px; font-size: 12.5px; color: var(--soft);
  display:flex; gap: 6px; align-items: baseline; min-width: 0; white-space: nowrap; overflow: hidden; }}
.mk-step b {{ color: var(--c); }}
.mk-step.on {{ background: var(--c); border-color: var(--c); color: #fff; }} .mk-step.on b {{ color: #fff; }}
.mk-cols {{ display: grid; grid-template-columns: 1.15fr 1.15fr 0.9fr; gap: 18px; }}
.mk-cols h5 {{ margin: 0 0 6px; font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: var(--soft); font-family: inherit !important; }}
.mk-cols ol, .mk-cols ul {{ margin: 0; padding-left: 20px; }}
.mk-cols li {{ font-size: 14.5px; line-height: 1.45; color: var(--ink); margin-bottom: 5px; }}
.mk-cols .ders {{ background: var(--ink); color: #F2EEE4; border-radius: 12px; padding: 10px 14px; }}
.mk-cols .ders h5 {{ color: #F2A27E; }} .mk-cols .ders p {{ font-family: Georgia, serif; font-size: 17px; line-height: 1.4; margin: 0; }}
.mk-legend {{ font-size: 12.5px; color: var(--soft); margin-top: 6px; }}
.mk-legend b {{ color: var(--ink); }}
</style>
"""


def masthead(scenario_name: str, description: str, day: str, real_data: bool) -> str:
    code = scenario_name.split()[0]
    chip = ('<span class="mk-chip ok">● Gerçek veri</span>' if real_data
            else '<span class="mk-chip warn">● Sahte veri</span>')
    return f"""<div class="mk-mast">
<div><div class="eyebrow">Mikro-şebeke kontrol odası · Bandırma site otoparkı</div>
<h1>{html.escape(scenario_name)}</h1><div class="sub">{html.escape(description)}</div></div>
<div style="display:flex;gap:6px;justify-content:flex-end;flex-wrap:wrap;min-width:360px"><span class="mk-chip" style="background:{SCENARIO_COLORS.get(code, ACCENT)};border-color:transparent">{code}</span>
<span class="mk-chip">{html.escape(GUN_ADI.get(day, day.capitalize()))} temsili günü</span>{chip}</div></div>"""


def _delta(value, ref, unit, digits, lower_is_better=True) -> str:
    if ref is None or value != value or ref != ref:
        return ""
    d = value - ref
    if abs(d) < 10 ** -(digits + 1):
        return '<span class="mk-pill flat">S2 ile aynı</span>'
    good = (d < 0) == lower_is_better
    arrow = "▼" if d < 0 else "▲"
    return f'<span class="mk-pill {"down" if good else "up"}">{arrow} {tr(abs(d), digits)} {unit}</span>S2’ye göre'


def kpi_cards(k: pd.Series, ref: pd.Series | None, n_sessions: int, n_reached: int, limit_kw: float) -> str:
    """Dört ana kart + altı küçük gösterge. Kart rengi: sınır aşılıyorsa kırmızı, iyiyse yeşil."""
    g = lambda key: k.get(key, float("nan"))
    r = (lambda key: ref.get(key, float("nan"))) if ref is not None else (lambda key: None)
    peak = g("tepe_alim_kw")
    cards = [
        ("Şebeke tepe alımı", tr(peak), "kW", BAD if peak > limit_kw + 1e-6 else GOOD,
         f"tepe saati {k.get('tepe_alim_saati', '—')} &nbsp; {_delta(peak, r('tepe_alim_kw'), 'kW', 0)}"),
        ("Puant tepe alımı (17–22)", tr(g("puant_tepe_alim_kw")), "kW", ACCENT,
         _delta(g("puant_tepe_alim_kw"), r("puant_tepe_alim_kw"), "kW", 0)),
        ("Günlük maliyet", tr(g("maliyet_tl")), "TL", INK, _delta(g("maliyet_tl"), r("maliyet_tl"), "TL", 0)),
        ("Hedefe ulaşan araç", "—" if not n_sessions else f"%{g('hedefe_ulasma_orani') * 100:.0f}", "",
         GOOD if n_sessions and n_reached == n_sessions else ACCENT,
         f"{n_reached}/{n_sessions} araç sabah hedef dolulukta" if n_sessions else "bu senaryoda araç yok"),
    ]
    out = '<div class="mk-kpis">'
    for lbl, val, unit, color, foot in cards:
        out += (f'<div class="mk-kpi" style="--c:{color}"><div class="lbl">{lbl}</div>'
                f'<div class="val">{val}<small>{unit}</small></div><div class="foot">{foot}</div></div>')
    out += "</div>"
    nan = lambda v: v != v
    mini = [
        ("Araçlara verilen", f"{tr(g('arac_sarj_kwh'))} kWh"),
        ("Şarjın puant payı", "—" if nan(g("arac_sarj_puant_payi")) else f"%{g('arac_sarj_puant_payi') * 100:.0f}"),
        ("Ortalama ünite beklemesi", "—" if nan(g("ortalama_bekleme_saat")) else f"{tr(g('ortalama_bekleme_saat'), 1)} sa"),
        ("Site sınırı aşımı", f"{g('site_siniri_asim_adim'):.0f} adım"),
        ("En düşük gerilim", "—" if nan(g("min_gerilim_pu")) else f"{tr(g('min_gerilim_pu'), 3)} p.u."),
        ("V2G ile şebekeye", "—" if nan(g("v2g_veris_kwh")) else f"{tr(g('v2g_veris_kwh'))} kWh"),
    ]
    out += '<div class="mk-mini">' + "".join(f"<div>{a}<b>{b}</b></div>" for a, b in mini) + "</div>"
    return out


# ---------------------------------------------------------------- canlı tek hat şeması
def _branch(path: str, p_kw: float, scale: float, color: str, reverse: bool) -> str:
    """Bir güç akışı hattı: kalınlık güce, hız güce bağlı; yön işaretle. Akış yoksa ince gri."""
    base = f'<path d="{path}" stroke="{LINE}" stroke-width="6" fill="none" stroke-linecap="round"/>'
    mag = abs(p_kw)
    if mag < 0.5:
        return base
    width = 3 + 9 * min(mag / scale, 1.0)
    dur = max(0.35, 2.2 - 1.8 * min(mag / scale, 1.0))
    direction = "reverse" if reverse else "normal"
    return base + (f'<path class="mk-flow" d="{path}" stroke="{color}" stroke-width="{width:.1f}" fill="none" '
                   f'stroke-linecap="round" style="animation-duration:{dur:.2f}s;animation-direction:{direction}"/>')


def _node(x, y, w, h, title, value, color, sub="") -> str:
    return (f'<g><rect x="{x - w / 2}" y="{y}" width="{w}" height="{h}" rx="14" fill="{PAPER}" stroke="{color}" stroke-width="3"/>'
            f'<text x="{x}" y="{y + 27}" text-anchor="middle" font-size="19" font-weight="700" fill="{color}">{title}</text>'
            f'<text x="{x}" y="{y + 60}" text-anchor="middle" font-size="30" font-family="Georgia,serif" fill="{INK}">{value}</text>'
            + (f'<text x="{x}" y="{y + 84}" text-anchor="middle" font-size="15" fill="{SOFT}">{sub}</text>' if sub else "")
            + "</g>")


def single_line(row: pd.Series, cfg: dict, connected: int) -> str:
    """Seçilen adımın güç akışları tek hat şeması üzerinde. Pozitif yönler: şebeke→site, bara→yük/araç/batarya."""
    pv, load, ev, bess, grid = (float(row[c]) for c in ("pv_kw", "base_load_kw", "ev_kw", "bess_kw", "grid_kw"))
    site_kw = load - pv          # site kablosundan aşağı akan
    park_kw = ev + bess          # otopark kablosundan aşağı akan
    scale = float(cfg["grid"]["site_import_limit_kw"])
    lim = scale
    over = grid > lim + 1e-6
    loading = row.get("max_line_loading_pct", float("nan"))
    tload = row.get("trafo_loading_pct", float("nan"))
    vmin = row.get("min_vm_pu", float("nan"))
    # en yüklü kablo hangisi: akımı büyük olan (yük akışı yalnızca en büyüğünü veriyor)
    hot = "park" if abs(park_kw) >= abs(site_kw) else "site"
    def cable_color(which):
        if loading == loading and which == hot and loading > cfg["grid"]["max_loading_percent"]:
            return BAD
        return INK
    grid_col = BAD if over else INK
    svg = [f'<svg viewBox="0 0 1000 520" width="1000" height="520" xmlns="http://www.w3.org/2000/svg" '
           f'font-family="system-ui,-apple-system,Segoe UI,sans-serif">'
           '<style>@keyframes f{to{stroke-dashoffset:-28}}.mk-flow{stroke-dasharray:10 18;animation:f linear infinite}</style>']
    # şebeke ve trafo
    svg.append(_node(500, 2, 260, 70, "Şebeke · 20 kV", ("alım " if grid >= 0 else "veriş ") + f"{tr(abs(grid))} kW", grid_col))
    svg.append(_branch("M500 68 L500 150", grid, scale, grid_col, grid < 0))
    svg.append(f'<circle cx="500" cy="98" r="17" fill="{PAPER}" stroke="{INK}" stroke-width="2.5"/>'
               f'<circle cx="500" cy="120" r="17" fill="{PAPER}" stroke="{INK}" stroke-width="2.5"/>'
               f'<text x="530" y="104" font-size="17" font-weight="700" fill="{INK}">Trafo 400 kVA</text>'
               + (f'<text x="530" y="126" font-size="16" fill="{SOFT}">yüklenme %{tload:.0f}</text>' if tload == tload else ""))
    if over:
        svg.append(f'<text x="645" y="44" font-size="17" font-weight="700" fill="{BAD}">⚠ site sınırı {lim:.0f} kW aşıldı</text>')
    # ana pano
    svg.append(f'<line x1="150" y1="160" x2="850" y2="160" stroke="{INK}" stroke-width="7" stroke-linecap="round"/>'
               f'<text x="150" y="148" font-size="15" font-weight="700" fill="{SOFT}">ANA PANO · 0,4 kV</text>')
    # kablolar
    for x, kw, name, which in ((270, site_kw, "Site kablosu · 150 m", "site"), (730, park_kw, "Otopark kablosu · 100 m", "park")):
        col = cable_color(which)
        svg.append(_branch(f"M{x} 166 L{x} 268", kw, scale, col if col == BAD else (SUN if which == "site" and kw < 0 else ACCENT if which == "park" else INK), kw < 0))
        tag = f"{tr(abs(kw))} kW"
        if which == hot and loading == loading:
            tag += f" · %{loading:.0f}"
        svg.append(f'<text x="{x + 16}" y="204" font-size="15" fill="{SOFT}">{name}</text>'
                   f'<text x="{x + 16}" y="230" font-size="21" font-weight="700" fill="{col}">{tag}</text>')
    # baralar
    svg.append(f'<line x1="90" y1="276" x2="460" y2="276" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>'
               f'<text x="90" y="266" font-size="15" font-weight="700" fill="{SOFT}">SİTE BARASI</text>'
               f'<line x1="540" y1="276" x2="920" y2="276" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>'
               f'<text x="580" y="266" font-size="15" font-weight="700" fill="{SOFT}">OTOPARK BARASI</text>')
    if vmin == vmin:
        svg.append(f'<text x="500" y="330" text-anchor="middle" font-size="16" fill="{BAD if vmin < cfg["grid"]["voltage_min_pu"] else SOFT}">'
                   f'en düşük gerilim {tr(vmin, 3)} p.u.</text>')
    # uçlar: PV ve yük üretim/tüketim, batarya ve istasyon
    svg.append(_branch("M180 282 L180 372", -pv, scale, SUN, True))
    svg.append(_branch("M370 282 L370 372", load, scale, INK, False))
    svg.append(_branch("M630 282 L630 372", bess, scale, BLUE, bess < 0))
    svg.append(_branch("M830 282 L830 372", ev, scale, ACCENT if ev >= 0 else BLUE, ev < 0))
    svg.append(_node(180, 376, 190, 96, "Güneş (PV)", f"{tr(pv)} kW", SUN, "100 kWp çatı"))
    svg.append(_node(370, 376, 190, 96, "Site yükü", f"{tr(load)} kW", INK, "50 daire + ortak"))
    soc = row.get("bess_soc", float("nan"))
    svg.append(_node(630, 376, 190, 96, "Batarya", ("şarj " if bess > 0.5 else "deşarj " if bess < -0.5 else "") + f"{tr(abs(bess))} kW",
                     BLUE, f"doluluk %{soc * 100:.0f}" if soc == soc else "bu senaryoda yok"))
    svg.append(_node(830, 376, 200, 96, "Şarj istasyonu", ("V2G " if ev < -0.5 else "") + f"{tr(abs(ev))} kW",
                     ACCENT, f"{connected} araç bağlı"))
    svg.append(f'<text x="500" y="508" text-anchor="middle" font-size="15" fill="{SOFT}">Çizgi kalınlığı ve hızı güçle orantılı; '
               f'hareket yönü güç akışının yönü. Kırmızı: sınır aşımı.</text>')
    svg.append("</svg>")
    # <img> içinde SVG: Streamlit'in HTML temizleyicisi satır içi SVG'yi siliyor; resim olarak verince
    # içindeki CSS animasyonu yine çalışıyor.
    data = base64.b64encode("".join(svg).encode("utf-8")).decode("ascii")
    return f'<img src="data:image/svg+xml;base64,{data}" style="width:100%;height:auto;display:block" alt="Tek hat şeması">'


def parking(at_t: pd.DataFrame, sessions: pd.DataFrame, t: pd.Timestamp, cfg: dict) -> str:
    """Otopark: 10 ünite ve sıradaki araçlar, seçilen adımda."""
    chargers = [(f"{c['kind']}{i + 1}", c["kind"], c["power_kw"]) for c in cfg["station"]["chargers"] for i in range(c["count"])]
    by_id = {r.charger_id: r for r in at_t.itertuples()} if len(at_t) else {}
    out = '<div class="mk-bays">'
    for cid, kind, pmax in chargers:
        r = by_id.get(cid)
        if r is None:
            out += f'<div class="mk-bay"><div class="id">{cid}</div><div>{pmax} kW</div><div style="margin-top:10px">boş</div></div>'
            continue
        p = float(r.power_kw)
        c = BLUE if p < -1e-6 else ACCENT if p > 1e-6 else GOOD
        state = "V2G" if p < -1e-6 else "şarj" if p > 1e-6 else "bağlı"
        out += (f'<div class="mk-bay on" style="--c:{c}"><div class="id">{cid}<span>{html.escape(str(r.vehicle_id))}</span></div>'
                f'<div class="car">🚗 <span>%{r.soc * 100:.0f}</span></div>'
                f'<div class="bar"><i style="width:{max(0, min(1, r.soc)) * 100:.0f}%"></i></div>'
                f'<div class="kw">{"V2G " if state == "V2G" else ""}{tr(abs(p))} kW</div></div>')
    out += "</div>"
    if len(sessions):
        conn = sessions["connected_at"]
        waiting = sessions[(sessions.arrival <= t) & (sessions.departure > t) & (conn.isna() | (conn > t))]
        if len(waiting):
            out += ('<div class="mk-queue">Sırada bekleyen: '
                    + "".join(f"<span>{html.escape(str(v))}</span>" for v in waiting.vehicle_id) + "</div>")
        else:
            out += '<div class="mk-queue">Sırada bekleyen araç yok.</div>'
    return out


# ---------------------------------------------------------------- senaryo puan kartı
SCORE_COLS = [  # (anahtar, başlık, biçim, düşük mü iyi)
    ("tepe_alim_kw", "Tepe alım", "{:.0f} kW", True),
    ("puant_tepe_alim_kw", "Puant tepe", "{:.0f} kW", True),
    ("maliyet_tl", "Maliyet", "{:,.0f} TL", True),
    ("arac_sarj_kwh", "Araçlara verilen", "{:.0f} kWh", False),
    ("hedefe_ulasma_orani", "Hedefe ulaşan", "{:.0%}", False),
    ("ortalama_bekleme_saat", "Bekleme", "{:.1f} sa", True),
    ("site_siniri_asim_adim", "Sınır aşımı", "{:.0f} adım", True),
]


def scorecard(table: pd.DataFrame) -> str:
    """Senaryolar satırda, göstergeler sütunda; her hücrede orantılı çubuk, en iyi değer yeşil."""
    out = '<table class="mk-score"><tr><th></th>' + "".join(f"<th>{t}</th>" for _, t, _, _ in SCORE_COLS) + "</tr>"
    for name in table.columns:
        code = name.split()[0]
        out += f'<tr style="--c:{SCENARIO_COLORS.get(code, ACCENT)}"><td>{code} <span style="font-weight:400;color:{SOFT}">{html.escape(name[len(code) + 1:])}</span></td>'
        for key, _, f, low in SCORE_COLS:
            if key not in table.index:
                out += "<td>—</td>"; continue
            row = pd.to_numeric(table.loc[key], errors="coerce")
            v = row[name]
            if v != v:
                out += "<td>—</td>"; continue
            valid = row.dropna()
            # S1 araçsız taban: "en iyi" yarışına girmez (araç yokken tepe ve maliyet doğal olarak en düşük)
            valid = valid[[c for c in valid.index if not c.startswith("S1")]]
            best = (valid.min() if low else valid.max()) if len(valid) else v
            top = max(abs(valid).max(), 1e-9) if len(valid) else 1
            text = f.format(v).replace(",", ".") if "{:,.0f}" in f else f.format(v).replace(".", ",")
            if f == "{:.0%}":
                text = "%" + f"{v * 100:.0f}"
            cls = ' class="best"' if not code.startswith("S1") and math.isclose(v, best, rel_tol=1e-6, abs_tol=1e-6) and len(valid) > 1 else ""
            out += f'<td><div class="cell"><i style="width:{max(2, 46 * abs(v) / top):.0f}px"></i><span{cls}>{text}</span></div></td>'
        out += "</tr>"
    return out + "</table>"


# ---------------------------------------------------------------- senaryo anlatımı (sunum için sade dil)
# Sayı yok: sayılar gün ve kaydırıcılarla değişiyor, onları sunum notları (notlar.py) sonuçtan hesaplıyor.
SENARYO = {
    "S1": dict(
        kisa="Hiç araç yok: sitenin kendi tüketimi ve güneş paneli. Diğer senaryoları kıyaslamak için taban.",
        ekler="Taban",
        nasil=["Evler, ortak alan ve dükkânlar her zamanki gibi elektrik kullanıyor.",
               "Gündüz güneş paneli üretiyor; fazlası şebekeye veriliyor.",
               "Otoparkta araç yok, istasyon boş."],
        bak=["Gündüz eğrinin sıfırın altına inmesi: güneş fazlası şebekeye gidiyor.",
             "Akşam sitenin kendi küçük tepesi: araçsız gün bu kadar sakin."],
        ders="Araçların getirdiği her yük ve her maliyet bu tabana göre ölçülüyor."),
    "S2": dict(
        kisa="Bugünkü durum: araç takıldığı an tam güçle şarj olur. Kimse yönetmiyor, sınır gözetilmiyor.",
        ekler="Araçlar",
        nasil=["Araç akşam eve gelince boş bir üniteye bağlanıyor.",
               "Ünite ve aracın izin verdiği en yüksek güçle hemen şarj başlıyor.",
               "Üniteler doluysa araç sırada bekliyor; batarya kullanılmıyor."],
        bak=["Akşam 18–22 arası (puant) şebeke alımının fırlaması ve site sınırını aşması.",
             "Şebeke sekmesinde otopark kablosunun aşırı yüklenmesi.",
             "Şarjın büyük kısmının en pahalı saatlerde yapılması."],
        ders="Sorunun kendisi: araçlar güneşin bittiği ve elektriğin en pahalı olduğu saatte geliyor."),
    "S3": dict(
        kisa="Akıllı şarj: basit kurallarla şarjı gecenin ucuz saatlerine kaydırır. Yatırım gerektirmez.",
        ekler="+ Kurallar",
        nasil=["Her aracın ihtiyacı, sabah ayrılana kadarki en ucuz saatlere eşit dağıtılıyor.",
               "Bataryası %30’un altındaki araç beklemeden şarj ediliyor (güvenlik).",
               "Güneş fazlası varsa araçlara veriliyor; istasyon ve site sınırları hiç aşılmıyor."],
        bak=["Akşam tepesinin kaybolması, şarjın geceye yayılması.",
             "Sabah gece tarifesi bitmeden önce oluşan yeni, küçük tepe.",
             "Bedeli: araçlar üniteyi uzun tutuyor, bazıları sabah hedefe yetişemiyor."],
        ders="Sadece zamanlamayı değiştirmek bile şebekeyi büyük ölçüde rahatlatıyor."),
    "S4": dict(
        kisa="Akıllı şarj + 200 kWh’lik site bataryası: batarya ucuzken dolar, pahalı saatte boşalır.",
        ekler="+ Batarya",
        nasil=["Araçlar S3’teki kurallarla şarj ediliyor.",
               "Batarya gece ucuz tarifede ve gündüz güneş fazlasıyla doluyor.",
               "Akşam puantta boşalıp sitenin yükünü karşılıyor; sınır aşılacakken devreye giriyor."],
        bak=["Tek hat şemasında batarya kutusu: akşam deşarj, gece ve gündüz şarj.",
             "Puant saatlerinde şebekeden alımın sıfıra yakın olması.",
             "Maliyet farkı yazın büyük, kışın küçük: kışın güneş fazlası yok."],
        ders="Batarya özellikle yaz için değerli; kışın kazancı yalnızca gece–puant fiyat farkından."),
    "S5": dict(
        kisa="Optimizasyon: kurallar yerine her 15 dakikada en ucuz şarj planını matematikle hesaplar.",
        ekler="+ Optimizasyon",
        nasil=["Her adımda o an bağlı araçlar, batarya ve tarifeyle gün sonuna kadar en ucuz plan çözülüyor (MILP).",
               "Planın yalnızca ilk adımı uygulanıyor; sonra yeni bilgiyle tekrar çözülüyor.",
               "Sonradan gelecek araçlar bilinmiyor: gerçek hayattaki gibi."],
        bak=["Günün en düşük maliyeti.",
             "Tepe kayması: şarj gece tarifesinin bitişinden hemen önceye yığılıyor, site sınırına dayanıyor.",
             "Hedefe yetişemeyen araç sayısı S3’ten az."],
        ders="Maliyeti en aza indirmek ile tepeyi en aza indirmek aynı hedef değil."),
    "S6": dict(
        kisa="S5 + V2G: uygun araçlar gerektiğinde bataryasından şebekeye enerji geri verebilir.",
        ekler="+ V2G",
        nasil=["S5’teki optimizasyon, araçları gerektiğinde küçük bir batarya gibi de kullanabiliyor.",
               "Araç %30’un altına indirilmiyor; sabah hedef doluluğu garanti.",
               "Aynı anda hem şarj hem deşarj yok."],
        bak=["Aralık gününde otoparkta ve ısı haritasında mavi: araçtan şebekeye.",
             "Haziran’da V2G hiç kullanılmıyor.",
             "V2G’nin miktarı küçük: araçlar akşam az dolu geliyor, verecek enerjileri yok."],
        ders="Gece şarj eden konut otoparkında V2G’nin esnekliği az; ofis ya da filo otoparkında daha anlamlı olurdu."),
}


def scenario_explainer(code: str) -> str:
    """Senaryo merdiveni (S1→S6, her basamak ne ekliyor) + nasıl çalışıyor / ekranda neye bak / ne öğreniyoruz."""
    info = SENARYO.get(code)
    if info is None:
        return ""
    steps = ""
    for c, d in SENARYO.items():
        on = c == code
        col = SCENARIO_COLORS.get(c, ACCENT)
        steps += (f'<div class="mk-step{" on" if on else ""}" style="--c:{col}"><b>{c}</b><span>{d["ekler"]}</span></div>')
    li = lambda xs: "".join(f"<li>{html.escape(x)}</li>" for x in xs)
    return f"""<div class="mk-explain">
<div class="mk-ladder">{steps}</div>
<div class="mk-cols">
<div><h5>Nasıl çalışıyor?</h5><ol>{li(info["nasil"])}</ol></div>
<div><h5>Ekranda neye bakmalı?</h5><ul>{li(info["bak"])}</ul></div>
<div class="ders"><h5>Ne öğreniyoruz?</h5><p>{html.escape(info["ders"])}</p></div>
</div></div>"""
