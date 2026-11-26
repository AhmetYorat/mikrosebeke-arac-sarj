"""Bütün senaryoların sonuç tabloları ve grafikleri (YM-4). Rapordaki sayıların tek kaynağı.

    python -m microgrid.sim.sonuclar                # iki temsili gün, yük akışıyla -> results/sonuclar/
    python -m microgrid.sim.sonuclar --gun haziran --hizli   # yük akışısız, hızlı deneme

Çıktılar:
    kpi_<gün>.csv       senaryo × gösterge (YM-1 KPI'ları + YM-2 kullanıcı memnuniyeti + V2G)
    ozet.md             rapora yapıştırılacak tablo; girdi kaynağı (gerçek/sahte) ve üretim tarihi yazılı
    <gün>_<S>_steps.csv adım tabloları
    karsilastirma_<gün>.png  şebeke alımı ve istasyon gücü, bütün senaryolar

GitHub Actions'ta "sonuclar" iş akışı bunu gerçek PVGIS verisiyle çalıştırıp çıktıları indirilebilir dosya olarak
yükler (Actions → sonuclar → Run workflow). Raporda yalnızca kaynak = gercek olan sayılar kullanılmalı.
"""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import pandas as pd

from microgrid.config import REPO_ROOT, load_config
from microgrid.kpi import compute
from microgrid.sim.loop import SimResult, time_index
from microgrid.sim.scenarios import SCENARIOS, simulate
from microgrid.sim.setup import GERCEK, TEMSILI_GUNLER, load_inputs, with_start
from microgrid.station.strategies import satisfaction


def kpi_row(result: SimResult, cfg: dict) -> pd.Series:
    """Bir senaryonun bütün göstergeleri: şebeke/maliyet (YM-1), kullanıcı (YM-2), V2G."""
    k = compute(result.steps, cfg)
    dt_h = cfg["simulation"]["step_minutes"] / 60
    sat = satisfaction(result.sessions) if len(result.sessions) else satisfaction(pd.DataFrame())
    v2g_kwh = max(0.0, float(-result.steps["ev_kw"].clip(upper=0).sum() * dt_h))   # -0 görünmesin
    return pd.concat([k, sat, pd.Series({"v2g_veris_kwh": v2g_kwh})])


# Rapor ve dashboard'da gösterilen göstergeler, sırasıyla (anahtar, başlık, biçim)
SHOWN = [
    ("tepe_alim_kw", "Şebeke tepe alımı (kW)", "{:.0f}"),
    ("tepe_alim_saati", "Tepe saati", "{}"),
    ("puant_tepe_alim_kw", "Puant tepe alımı (kW)", "{:.0f}"),
    ("maliyet_tl", "Günlük maliyet (TL)", "{:,.0f}"),
    ("arac_sarj_kwh", "Araç şarjı (kWh)", "{:.0f}"),
    ("arac_sarj_puant_payi", "Araç şarjının puant payı", "{:.0%}"),
    ("hedefe_ulasma_orani", "Hedefe ulaşan araç", "{:.0%}"),
    ("hizmet_alamayan", "Hiç bağlanamayan araç", "{:.0f}"),
    ("ortalama_bekleme_saat", "Ortalama ünite beklemesi (sa)", "{:.1f}"),
    ("v2g_veris_kwh", "V2G ile şebekeye (kWh)", "{:.0f}"),
    ("oz_tuketim_orani", "PV öz tüketim", "{:.0%}"),
    ("site_siniri_asim_adim", "Site sınırı aşımı (adım)", "{:.0f}"),
    ("istasyon_siniri_asim_adim", "İstasyon sınırı aşımı (adım)", "{:.0f}"),
    ("min_gerilim_pu", "En düşük gerilim (p.u.)", "{:.3f}"),
    ("max_trafo_yuklenme_pct", "Trafo en yüksek yüklenme (%)", "{:.0f}"),
]


def fmt(key: str, value) -> str:
    spec = next(f for k, _, f in SHOWN if k == key)
    if isinstance(value, float) and value != value:
        return "—"
    try:
        return spec.format(value).replace(",", ".")
    except (ValueError, TypeError):
        return str(value)


def run_day(cfg: dict, grid_factory=None, progress=None) -> tuple[dict[str, SimResult], str]:
    """Bütün senaryoları aynı girdilerle çalıştırır. progress(i, n, ad) verilirse her senaryodan önce çağrılır."""
    index = time_index(cfg)
    inputs, source = load_inputs(cfg, index)
    results = {}
    for i, (name, sc) in enumerate(SCENARIOS.items()):
        if progress:
            progress(i, len(SCENARIOS), name)
        results[name] = simulate(cfg, sc, inputs, grid_factory(cfg) if grid_factory else None)
    return results, source


def kpi_table(results: dict[str, SimResult], cfg: dict) -> pd.DataFrame:
    return pd.DataFrame({name: kpi_row(r, cfg) for name, r in results.items()})


def markdown_table(table: pd.DataFrame) -> str:
    short = [c.split()[0] for c in table.columns]
    lines = ["| Gösterge | " + " | ".join(short) + " |", "|---|" + "---|" * len(short)]
    for key, title, _ in SHOWN:
        if key in table.index:
            lines.append(f"| {title} | " + " | ".join(fmt(key, table.at[key, c]) for c in table.columns) + " |")
    return "\n".join(lines)


def comparison_png(results: dict[str, SimResult], cfg: dict, path: Path, title: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = ["#7A8793", "#D1495B", "#2E86AB", "#3B8C4A", "#E0A100", "#6C4AB6"]
    fig, axes = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True)
    for (name, r), c in zip(results.items(), colors):
        s = r.steps
        axes[0].plot(s.index, s["grid_kw"], label=name, color=c, lw=1.8)
        axes[1].plot(s.index, s["ev_kw"], label=name, color=c, lw=1.8)
    axes[0].axhline(cfg["grid"]["site_import_limit_kw"], ls="--", color="k", lw=1)
    axes[0].text(next(iter(results.values())).steps.index[0], cfg["grid"]["site_import_limit_kw"] + 3,
                 "site sınırı", fontsize=8)
    axes[1].axhline(0, color="k", lw=0.6)
    axes[0].set_ylabel("Şebekeden alım (kW)")
    axes[1].set_ylabel("İstasyon (kW, − = V2G)")
    for ax in axes:
        for day in pd.Series(ax.lines[0].get_xdata()).dt.normalize().unique():
            ax.axvspan(day + pd.Timedelta(hours=17), day + pd.Timedelta(hours=22), color="#D1495B", alpha=0.07, lw=0)
        ax.grid(alpha=0.3)
    axes[0].legend(ncol=3, fontsize=8, loc="upper left")
    axes[0].set_title(title)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    from microgrid.grid import PandapowerGrid

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gun", choices=[*TEMSILI_GUNLER, "ikisi"], default="ikisi")
    ap.add_argument("--hizli", action="store_true", help="yük akışı (pandapower) olmadan")
    ap.add_argument("--cikti", default=str(REPO_ROOT / "results" / "sonuclar"))
    args = ap.parse_args()

    out = Path(args.cikti)
    out.mkdir(parents=True, exist_ok=True)
    days = TEMSILI_GUNLER if args.gun == "ikisi" else {args.gun: TEMSILI_GUNLER[args.gun]}
    md = [f"# Senaryo sonuçları\n\nÜretim: {dt.datetime.now():%Y-%m-%d %H:%M} · `python -m microgrid.sim.sonuclar`"
          f"{' --hizli (yük akışı yok)' if args.hizli else ''}\n"]
    for day, start in days.items():
        cfg = with_start(load_config(), start)
        results, source = run_day(cfg, None if args.hizli else PandapowerGrid,
                                  progress=lambda i, n, name: print(f"[{day}] {i + 1}/{n} {name}"))
        table = kpi_table(results, cfg)
        table.to_csv(out / f"kpi_{day}.csv")
        for name, r in results.items():
            r.steps.to_csv(out / f"{day}_{name.split()[0]}_steps.csv")
        uyar = "" if source == GERCEK else "\n\n> **UYARI: sahte girdilerle üretildi. Bu sayılar raporda kullanılmamalı.**"
        comparison_png(results, cfg, out / f"karsilastirma_{day}.png",
                       f"{day.capitalize()} temsili günü · girdi: {source}")
        md.append(f"## {day.capitalize()} (girdi kaynağı: {source}){uyar}\n\n{markdown_table(table)}\n\n"
                  f"![{day}](karsilastirma_{day}.png)\n")
        print(f"[{day}] girdi: {source}\n{markdown_table(table)}\n")
    (out / "ozet.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Çıktılar: {out}")


if __name__ == "__main__":
    main()
