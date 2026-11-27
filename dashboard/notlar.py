"""Sunum notları (YM-4): her sekmenin altında "burada neye dikkat edilmeli" kutuları.

Notlar elle yazılmış sabit cümleler değil; o anki simülasyon sonucundan hesaplanır. Kenar çubuğundan araç sayısı,
PV ya da batarya değişince notlar da değişir ve yanlış bir sayı söyletmez. Her fonksiyon (tür, metin) listesi döner:
tür "dikkat" (sorun), "iyi" (iyileşme), "bilgi" (okuma ipucu). Metin küçük HTML içerebilir (<b>).
"""
from __future__ import annotations

import html

import pandas as pd

from sema import BAD, BLUE, GOOD, tr

PUANT = (17, 22)


def _code(scenario_name: str) -> str:
    return scenario_name.split()[0]


def _hhmm(t) -> str:
    return pd.Timestamp(t).strftime("%H:%M")


def _in_puant(index: pd.DatetimeIndex) -> pd.Series:
    return pd.Series((index.hour >= PUANT[0]) & (index.hour < PUANT[1]), index=index)


def _ranges(mask: pd.Series) -> str:
    """Ardışık True adımlarını "18:00–19:30" gibi aralıklara çevirir (en fazla üç aralık)."""
    out, start, prev = [], None, None
    step = mask.index[1] - mask.index[0] if len(mask) > 1 else pd.Timedelta(minutes=15)
    for t, v in mask.items():
        if v and start is None:
            start = t
        if not v and start is not None:
            out.append(f"{_hhmm(start)}–{_hhmm(prev + step)}"); start = None
        prev = t
    if start is not None:
        out.append(f"{_hhmm(start)}–{_hhmm(prev + step)}")
    return ", ".join(out[:3]) + (" …" if len(out) > 3 else "")


def box(notes: list[tuple[str, str]], title: str = "Sunum notu") -> str:
    """Notları tek kutuda gösterir. Boş listede boş metin."""
    if not notes:
        return ""
    icon = {"dikkat": ("⚠", BAD), "iyi": ("✓", GOOD), "bilgi": ("ℹ", BLUE)}
    items = "".join(f'<li><span style="color:{icon[k][1]};font-weight:800;margin-right:6px">{icon[k][0]}</span>{t}</li>'
                    for k, t in notes)
    return (f'<div class="mk-note"><div class="mk-note-h">🎤 {html.escape(title)}</div><ul>{items}</ul></div>')


# ------------------------------------------------------------------ canlı şema: seçilen an
def moment(row: pd.Series, n_connected: int, n_waiting: int, cfg: dict) -> list[tuple[str, str]]:
    lim, st_lim = cfg["grid"]["site_import_limit_kw"], cfg["station"]["power_limit_kw"]
    notes = []
    grid, ev, pv, load = row["grid_kw"], row["ev_kw"], row["pv_kw"], row["base_load_kw"]
    if grid > lim + 1e-6:
        notes.append(("dikkat", f"Bu anda şebekeden <b>{tr(grid)} kW</b> çekiliyor: site sınırı ({lim:.0f} kW) "
                                f"<b>{tr(grid - lim)} kW</b> aşılmış."))
    if ev > st_lim + 1e-6:
        notes.append(("dikkat", f"İstasyon <b>{tr(ev)} kW</b> çekiyor, kendi sınırı {st_lim:.0f} kW: kontrolsüz şarjda "
                                "bu sınırı uygulayan bir yönetici yok."))
    loading = row.get("max_line_loading_pct", float("nan"))
    if loading == loading and loading > cfg["grid"]["max_loading_percent"]:
        notes.append(("dikkat", f"En yüklü kablo <b>%{loading:.0f}</b>: taşıyabileceğinden fazla akım geçiyor "
                                "(otopark kablosu; istasyonun bütün akımı buradan geçer)."))
    if ev < -0.5:
        notes.append(("iyi", f"Araçlar şebekeye <b>{tr(-ev)} kW</b> veriyor (V2G)."))
    if grid < -0.5:
        notes.append(("bilgi", f"Güneş ({tr(pv)} kW) sitenin tüketimini aşıyor; fazlası <b>{tr(-grid)} kW</b> şebekeye veriliyor."))
    if n_waiting:
        notes.append(("dikkat", f"<b>{n_waiting} araç</b> ünite boşalmasını bekliyor."))
    price = row["price_tl_per_kwh"]
    if price >= 6 and ev > 0.5:
        notes.append(("bilgi", f"Puant tarifesi ({tr(price, 2)} TL/kWh): bu anda yapılan şarj günün en pahalı şarjı."))
    elif price < 3.5 and ev > 0.5:
        notes.append(("iyi", f"Gece tarifesi ({tr(price, 2)} TL/kWh): şarj için en ucuz saatler."))
    if not notes:
        notes.append(("bilgi", f"Sakin bir an: şebekeden {tr(grid)} kW, {n_connected} araç bağlı, sınırlar içinde."))
    return notes


# ------------------------------------------------------------------ güç akışları
def power(scenario_name: str, steps: pd.DataFrame, k: pd.Series, cfg: dict) -> list[tuple[str, str]]:
    code = _code(scenario_name)
    lim = cfg["grid"]["site_import_limit_kw"]
    st_lim = cfg["station"]["power_limit_kw"]
    puant = _in_puant(steps.index)
    peak_t = steps["grid_kw"].idxmax()
    peak = steps["grid_kw"].max()
    over = steps["grid_kw"] > lim + 1e-6
    notes = []
    if code == "S1":
        notes.append(("bilgi", f"Araçsız gün: karşılaştırma tabanı. Sitenin kendi tepesi <b>{tr(peak)} kW</b> ({_hhmm(peak_t)}); "
                               "diğer senaryolardaki fark tamamen araçlardan geliyor."))
    if over.any():
        notes.append(("dikkat", f"Site sınırı {lim:.0f} kW <b>{int(over.sum())} adım</b> aşılıyor ({_ranges(over)}); "
                                f"en kötüsü <b>{tr(peak)} kW</b> (saat {_hhmm(peak_t)})."))
    elif steps["ev_kw"].abs().sum() > 0:
        notes.append(("iyi", f"Site sınırı ({lim:.0f} kW) hiçbir adımda aşılmıyor; günün tepesi {tr(peak)} kW ({_hhmm(peak_t)})."))
    st_over = steps["ev_kw"] > st_lim + 1e-6
    if st_over.any():
        notes.append(("dikkat", f"İstasyon kendi {st_lim:.0f} kW sınırını <b>{int(st_over.sum())} adım</b> geçiyor "
                                f"(en fazla {tr(steps['ev_kw'].max())} kW): kontrolsüz şarjda sınırı uygulayan yok."))
    share = k.get("arac_sarj_puant_payi", float("nan"))
    if share == share and steps["ev_kw"].clip(lower=0).sum() > 0:
        kind = "dikkat" if share > 0.5 else "iyi"
        notes.append((kind, f"Araç şarjının puant saatlerinde (17–22) yapılan payı: <b>%{share * 100:.0f}</b>."
                            + (" Akşam herkes aynı anda takıyor." if share > 0.5 else " Şarj ucuz saatlere kaymış.")))
    if not puant[peak_t] and code not in ("S1",) and steps["ev_kw"].abs().sum() > 0 and peak > 0.8 * lim:
        notes.append(("dikkat", f"Tepe puantta değil, <b>saat {_hhmm(peak_t)}</b>: yönetim akşam tepesini kaldırıp "
                                "şarjı gece tarifesinin bitişine yığıyor (tepe kayması). Maliyeti en aza indirmek ile "
                                "tepeyi en aza indirmek aynı hedef değil."))
    if (steps["grid_kw"] < -0.5).any():
        notes.append(("bilgi", "Sıfırın altındaki değerler: güneş sitenin tüketimini aşıyor, fazlası şebekeye veriliyor "
                               f"({_ranges(steps['grid_kw'] < -0.5)})."))
    if (steps["bess_kw"].abs() > 0.5).any():
        dis = steps["bess_kw"].clip(upper=0)[puant].sum() * cfg["simulation"]["step_minutes"] / 60
        if dis < -0.5:
            notes.append(("iyi", f"Batarya puantta <b>{tr(-dis)} kWh</b> veriyor; gece ve güneş fazlasıyla doluyor."))
    return notes


# ------------------------------------------------------------------ şarj istasyonu
def station(scenario_name: str, steps: pd.DataFrame, sessions: pd.DataFrame, k: pd.Series, cfg: dict) -> list[tuple[str, str]]:
    if not len(sessions):
        return [("bilgi", "Bu senaryoda araç yok.")]
    notes = []
    n = len(sessions)
    reached = int(sessions.reached_target.sum())
    wait = k.get("ortalama_bekleme_saat", float("nan"))
    if reached == n:
        notes.append(("iyi", f"<b>{n} aracın hepsi</b> sabah hedef dolulukta (%{cfg['vehicles']['target_soc'] * 100:.0f}) ayrılıyor."))
    else:
        missed = sessions[~sessions.reached_target]
        notes.append(("dikkat", f"<b>{n - reached} araç</b> sabah hedefe yetişemiyor ("
                                + ", ".join(html.escape(str(v)) for v in missed.vehicle_id[:6])
                                + ("…" if len(missed) > 6 else "") + "). Tablodaki ✗ satırlar."))
    if wait == wait:
        kind = "dikkat" if wait > 2 else "iyi"
        notes.append((kind, f"Ortalama ünite beklemesi <b>{tr(wait, 1)} saat</b>."
                            + (" Şarj geceye yayılınca araçlar üniteyi sabaha kadar tutuyor, sıradaki geç bağlanıyor."
                               if wait > 2 else " Araçlar hızlı dolup üniteyi bırakıyor.")))
    never = int(k.get("hizmet_alamayan", 0) or 0)
    if never:
        notes.append(("dikkat", f"<b>{never} araç</b> hiç ünite bulamadan ayrılıyor."))
    v2g = k.get("v2g_veris_kwh", 0)
    if v2g == v2g and v2g > 0.5:
        notes.append(("iyi", f"V2G: araçlar günde <b>{tr(v2g)} kWh</b> şebekeye veriyor (ısı haritasında mavi hücreler); "
                             f"araç doluluğu %{cfg['vehicles'].get('v2g_min_soc', 0.3) * 100:.0f} sınırının altına inmiyor."))
    elif _code(scenario_name) == "S6":
        notes.append(("bilgi", "V2G açık ama kullanılmıyor: araçlar akşam az dolu geliyor ve sabah hedefle ayrılmak zorunda; "
                               "verecek enerjileri yok. Aralık gününe geçince küçük bir V2G görünür."))
    notes.append(("bilgi", "Isı haritasında her satır bir ünite; boş hücre ünitenin boş ya da aracın dolmuş olduğunu gösterir."))
    return notes


# ------------------------------------------------------------------ şebeke
def grid(steps: pd.DataFrame, cfg: dict) -> list[tuple[str, str]]:
    if not steps["min_vm_pu"].notna().any():
        return []
    notes = []
    vmin_t = steps["min_vm_pu"].idxmin()
    vmin = steps["min_vm_pu"].min()
    vlim = cfg["grid"]["voltage_min_pu"]
    notes.append(("dikkat" if vmin < vlim else "iyi",
                  f"En düşük gerilim <b>{tr(vmin, 3)} p.u.</b> ({_hhmm(vmin_t)}), yani nominal gerilimin %{tr(vmin * 100, 1)} kadarı; "
                  f"alt sınır {tr(vlim, 2)}" + (" — <b>sınırın altında</b>." if vmin < vlim else ", sınırın içinde.")))
    ll = steps["max_line_loading_pct"]
    over = ll > cfg["grid"]["max_loading_percent"]
    if over.any():
        notes.append(("dikkat", f"En yüklü kablonun yüklenmesi <b>%{ll.max():.0f}</b>; <b>{int(over.sum())} adım</b> "
                                f"({int(over.sum()) * cfg['simulation']['step_minutes']} dakika) taşıyabileceğinden fazla akım geçiyor "
                                f"({_ranges(over)}). Bu sitede asıl sınırlayıcı gerilim değil, otopark kablosu."))
    else:
        notes.append(("iyi", f"Kablolar en fazla %{ll.max():.0f} yüklü; aşırı yük yok."))
    notes.append(("bilgi", f"Trafo en fazla %{steps['trafo_loading_pct'].max():.0f} dolu (400 kVA): trafo darboğaz değil."))
    return notes


# ------------------------------------------------------------------ senaryo karşılaştırması
def comparison(table: pd.DataFrame, results: dict) -> list[tuple[str, str]]:
    def val(key, name):
        try:
            return float(table.at[key, name])
        except (KeyError, ValueError, TypeError):
            return float("nan")

    names = [n for n in table.columns if not n.startswith("S1")]
    base = next((n for n in table.columns if n.startswith("S1")), None)
    s2 = next((n for n in names if n.startswith("S2")), None)
    notes = []
    if s2:
        smart = [n for n in names if n != s2]
        best_puant = min(smart, key=lambda n: val("puant_tepe_alim_kw", n)) if smart else None
        if best_puant:
            notes.append(("iyi", f"Puant tepesi: kontrolsüzde <b>{tr(val('puant_tepe_alim_kw', s2))} kW</b>, "
                                 f"akıllı senaryolarda {tr(min(val('puant_tepe_alim_kw', n) for n in smart))}–"
                                 f"{tr(max(val('puant_tepe_alim_kw', n) for n in smart))} kW."))
    cheap = min(names, key=lambda n: val("maliyet_tl", n)) if names else None
    if cheap and base:
        e = val("arac_sarj_kwh", cheap)
        per = (val("maliyet_tl", cheap) - val("maliyet_tl", base)) / e if e > 0 else float("nan")
        notes.append(("bilgi", f"En ucuz: <b>{html.escape(cheap)}</b> ({tr(val('maliyet_tl', cheap))} TL). Ama senaryolar "
                               "araçlara aynı enerjiyi vermiyor; adil kıyas kWh başına ek maliyet"
                               + (f" (burada {tr(per, 2)} TL/kWh)." if per == per else ".")))
    shifted = [n for n in names if n in results and not _in_puant(results[n].index)[results[n]["grid_kw"].idxmax()]
               and not n.startswith("S2")]
    if shifted:
        notes.append(("dikkat", "Tepe kayması: " + ", ".join(
            f"<b>{_code(n)}</b> {tr(results[n]['grid_kw'].max())} kW (saat {_hhmm(results[n]['grid_kw'].idxmax())})"
            for n in shifted) + ". Akşam tepesi kalkıyor, sabaha yeni bir tepe oluşuyor."))
    missed = [n for n in names if val("hedefe_ulasma_orani", n) == val("hedefe_ulasma_orani", n)
              and val("hedefe_ulasma_orani", n) < 0.999]
    if missed:
        notes.append(("dikkat", "Bedeli: " + ", ".join(f"{_code(n)} %{val('hedefe_ulasma_orani', n) * 100:.0f}" for n in missed)
                                + " araç hedefe ulaşıyor (kontrolsüzde %100)."))
    return notes
