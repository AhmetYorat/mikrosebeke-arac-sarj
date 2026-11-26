"""Performans göstergeleri (KPI, YM-1). Döngünün adım tablosundan (SimResult.steps) hesaplanır.

Bütün senaryolar aynı fonksiyondan geçer; böylece "kontrolsüz vs. akıllı şarj" karşılaştırması
aynı tanımlarla yapılır. Dashboard ve rapor bu sayıları kullanır.

    python -m microgrid.kpi            # results/*_steps.csv dosyalarının KPI tablosu -> results/kpi.csv

Tanımlar (dt = adım süresi, saat; işaret kuralı docs/arayuz-sozlesmesi.md):
    alım      = Σ max(grid_kw, 0) · dt          şebekeden çekilen enerji
    veriş     = Σ max(-grid_kw, 0) · dt         şebekeye verilen enerji (PV fazlası; satış şimdilik ücretsiz)
    tüketim   = Σ (base_load_kw + max(ev_kw, 0)) · dt     sitenin ve araçların ihtiyacı
    öz tüketim oranı   = (PV − veriş) / PV        PV'nin ne kadarı sitede kullanıldı
    yenilenebilir payı = (PV − veriş) / tüketim   tüketimin ne kadarı PV'den karşılandı
Batarya bir depodur, tüketim sayılmaz; kayıpları şebeke alımına yansır.
"""
import pandas as pd

from microgrid.config import REPO_ROOT, load_config
from microgrid.data.tariff import period_at

# Tablo sırası ve birimleri; dashboard bu adlara güvenebilir.
LIMIT_TOL_KW = 1e-3   # 1 W: sınır aşımı sayılmayan sayısal pay

KPI_UNITS = {
    "tepe_alim_kw": "kW",
    "tepe_alim_saati": "",
    "puant_tepe_alim_kw": "kW",
    "maliyet_tl": "TL",
    "ortalama_fiyat_tl_kwh": "TL/kWh",
    "alim_kwh": "kWh",
    "alim_gunduz_kwh": "kWh",
    "alim_puant_kwh": "kWh",
    "alim_gece_kwh": "kWh",
    "veris_kwh": "kWh",
    "pv_kwh": "kWh",
    "tuketim_kwh": "kWh",
    "arac_sarj_kwh": "kWh",
    "arac_sarj_puant_payi": "0-1",
    "oz_tuketim_orani": "0-1",
    "yenilenebilir_payi": "0-1",
    "yuk_faktoru": "0-1",
    "site_siniri_asim_adim": "adım",
    "site_siniri_asim_kwh": "kWh",
    "istasyon_siniri_asim_adim": "adım",
    "min_gerilim_pu": "p.u.",
    "gerilim_ihlal_adim": "adım",
    "max_kablo_yuklenme_pct": "%",
    "max_trafo_yuklenme_pct": "%",
}


def _label(key):
    return "/".join(map(str, key)) if isinstance(key, tuple) else str(key)


def _ratio(a, b):
    return float(a / b) if b > 0 else float("nan")


def compute(steps: pd.DataFrame, cfg=None) -> pd.Series:
    """Bir simülasyonun adım tablosundan KPI'lar."""
    cfg = cfg or load_config()
    dt = cfg["simulation"]["step_minutes"] / 60
    grid = steps["grid_kw"]
    imp, exp = grid.clip(lower=0), (-grid).clip(lower=0)
    ev_charge = steps["ev_kw"].clip(lower=0)

    hours = steps.index.hour + steps.index.minute / 60
    period = pd.Series([period_at(cfg, h)["name"] for h in hours], index=steps.index)
    puant = period == "puant"

    pv_kwh = steps["pv_kw"].sum() * dt
    exp_kwh = exp.sum() * dt
    imp_kwh = imp.sum() * dt
    demand_kwh = (steps["base_load_kw"] + ev_charge).sum() * dt
    pv_used_kwh = max(pv_kwh - exp_kwh, 0.0)
    ev_kwh = ev_charge.sum() * dt

    site_limit = cfg["grid"]["site_import_limit_kw"]
    # Sınıra tam oturan çözümler (MILP) çözücü toleransı kadar (~1e-6 kW) aşabilir; bu aşım sayılmaz (YM-4).
    over = (grid - site_limit).clip(lower=0)
    over = over.where(over > LIMIT_TOL_KW, 0.0)
    has_grid = steps["min_vm_pu"].notna().any()

    k = {
        "tepe_alim_kw": float(grid.max()),
        "tepe_alim_saati": f"{grid.idxmax():%H:%M}",
        "puant_tepe_alim_kw": float(grid[puant].max()) if puant.any() else float("nan"),
        "maliyet_tl": float(steps["cost_tl"].sum()),
        "ortalama_fiyat_tl_kwh": _ratio(steps["cost_tl"].sum(), imp_kwh),
        "alim_kwh": imp_kwh,
        **{f"alim_{p}_kwh": float(imp[period == p].sum() * dt) for p in ("gunduz", "puant", "gece")},
        "veris_kwh": exp_kwh,
        "pv_kwh": pv_kwh,
        "tuketim_kwh": demand_kwh,
        "arac_sarj_kwh": ev_kwh,
        "arac_sarj_puant_payi": _ratio(ev_charge[puant].sum() * dt, ev_kwh),
        "oz_tuketim_orani": _ratio(pv_used_kwh, pv_kwh),
        "yenilenebilir_payi": _ratio(pv_used_kwh, demand_kwh),
        "yuk_faktoru": _ratio(imp.mean(), imp.max()),
        "site_siniri_asim_adim": int((over > 0).sum()),
        "site_siniri_asim_kwh": float(over.sum() * dt),
        "istasyon_siniri_asim_adim": int((steps["ev_kw"] > cfg["station"]["power_limit_kw"] + LIMIT_TOL_KW).sum()),
        "min_gerilim_pu": float(steps["min_vm_pu"].min()) if has_grid else float("nan"),
        "gerilim_ihlal_adim": int((steps["min_vm_pu"] < cfg["grid"]["voltage_min_pu"]).sum()),
        "max_kablo_yuklenme_pct": float(steps["max_line_loading_pct"].max()) if has_grid else float("nan"),
        "max_trafo_yuklenme_pct": float(steps["trafo_loading_pct"].max()) if has_grid else float("nan"),
    }
    return pd.Series(k)[list(KPI_UNITS)]


def compare(results: dict, cfg=None) -> pd.DataFrame:
    """Birden çok senaryonun KPI tablosu: satırlar KPI, sütunlar senaryo; son sütun birim."""
    cfg = cfg or load_config()
    table = pd.DataFrame({name: compute(steps, cfg) for name, steps in results.items()})
    table["birim"] = pd.Series(KPI_UNITS)
    return table


# Gün sayısıyla çarpılıp toplanan (yayılı) KPI'lar; gerisi oran ya da uç değer.
_SUMMED = [
    "maliyet_tl", "alim_kwh", "alim_gunduz_kwh", "alim_puant_kwh", "alim_gece_kwh", "veris_kwh", "pv_kwh",
    "tuketim_kwh", "arac_sarj_kwh", "site_siniri_asim_adim", "site_siniri_asim_kwh", "istasyon_siniri_asim_adim",
    "gerilim_ihlal_adim",
]


def annualize(results: dict, weights: dict, cfg=None) -> pd.Series:
    """Temsili günlerin sonuçlarından yıllık KPI (data/seasons.py).

    results: {anahtar: adım tablosu}, weights: {anahtar: yılda kaç gün}. Enerji, maliyet ve aşım sayıları
    ağırlıklı toplanır; oranlar yıllık toplamlardan yeniden hesaplanır; tepe ve gerilim uç değerlerdir.
    """
    cfg = cfg or load_config()
    per_day = pd.DataFrame({k: compute(s, cfg) for k, s in results.items() if weights.get(k, 0) > 0})
    w = pd.Series({k: weights[k] for k in per_day.columns}, dtype=float)
    num = per_day.loc[_SUMMED].astype(float)

    a = (num * w).sum(axis=1)
    pv_used = a["pv_kwh"] - a["veris_kwh"]
    ev_puant = (per_day.loc["arac_sarj_puant_payi"].astype(float).fillna(0) * num.loc["arac_sarj_kwh"] * w).sum()
    peaks = per_day.loc["tepe_alim_kw"].astype(float)
    hours_per_year = w.sum() * 24

    k = {
        **a.to_dict(),
        "tepe_alim_kw": peaks.max(),
        "tepe_alim_saati": f"{per_day.loc['tepe_alim_saati', peaks.idxmax()]} ({_label(peaks.idxmax())})",
        "puant_tepe_alim_kw": per_day.loc["puant_tepe_alim_kw"].astype(float).max(),
        "ortalama_fiyat_tl_kwh": _ratio(a["maliyet_tl"], a["alim_kwh"]),
        "arac_sarj_puant_payi": _ratio(ev_puant, a["arac_sarj_kwh"]),
        "oz_tuketim_orani": _ratio(pv_used, a["pv_kwh"]),
        "yenilenebilir_payi": _ratio(pv_used, a["tuketim_kwh"]),
        "yuk_faktoru": _ratio(a["alim_kwh"] / hours_per_year, peaks.max()),
        "min_gerilim_pu": per_day.loc["min_gerilim_pu"].astype(float).min(),
        "max_kablo_yuklenme_pct": per_day.loc["max_kablo_yuklenme_pct"].astype(float).max(),
        "max_trafo_yuklenme_pct": per_day.loc["max_trafo_yuklenme_pct"].astype(float).max(),
    }
    return pd.Series(k)[list(KPI_UNITS)]


def load_steps(path) -> pd.DataFrame:
    """Döngünün yazdığı *_steps.csv dosyasını okur (indeks Türkiye saatinde)."""
    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert("Europe/Istanbul")
    return df


if __name__ == "__main__":
    files = sorted((REPO_ROOT / "results").glob("*_steps.csv"))
    if not files:
        raise SystemExit("results/ altında *_steps.csv yok. Önce döngüyü çalıştır: python -m microgrid.sim")
    table = compare({f.name.removesuffix("_steps.csv"): load_steps(f) for f in files})
    out = REPO_ROOT / "results" / "kpi.csv"
    table.to_csv(out)
    with pd.option_context("display.float_format", "{:.2f}".format, "display.width", 140):
        print(table)
    print(f"\nYazıldı: {out}")
