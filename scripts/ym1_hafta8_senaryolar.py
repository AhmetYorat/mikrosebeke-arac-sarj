"""Hafta 8 (YM-1): senaryolar arası karşılaştırma tablosu (yıllık, 24 temsili gün, pandapower ile).

Senaryolar YM-4'ün listesinden gelir (sim/scenarios.py SCENARIOS; dashboard da aynı listeyi gösterir).
YM-2 istasyonu ve YM-3 EMS'i oraya eklendikçe tablo kendiliğinden genişler; BEKLENEN listesi yalnızca henüz
olmayan sütunları "bekleniyor" diye göstermek için. Geçici (sahte modülle çalışan) senaryolar dipnotla işaretlenir.

Önce veri:  python -m microgrid.data
Sonra:      python scripts/ym1_hafta8_senaryolar.py
Çıktı: results/senaryo_tablosu.csv, docs/raporlar/hafta8-ym1-senaryolar.md (rapora girecek tablo)
"""
from microgrid.analysis import scenario_table
from microgrid.config import REPO_ROOT, load_config
from microgrid.grid import PandapowerGrid
from microgrid.sim.scenarios import SCENARIOS

BEKLENEN = ["S4 akıllı şarj + batarya", "S5 optimizasyonlu EMS", "S6 V2G"]
BEKLENEN = [b for b in BEKLENEN if not any(name.startswith(b[:2]) for name in SCENARIOS)]

ROWS = {  # rapordaki tablo: (KPI, başlık, biçim)
    "maliyet_tl": ("Yıllık maliyet", "{:,.0f} TL"),
    "tepe_alim_kw": ("Yılın tepe alımı", "{:.0f} kW"),
    "alim_puant_kwh": ("Puantta alım", "{:,.0f} kWh"),
    "arac_sarj_puant_payi": ("Araç şarjının puant payı", "%{:.0%}"),
    "yenilenebilir_payi": ("Yenilenebilir payı", "%{:.0%}"),
    "oz_tuketim_orani": ("Öz tüketim", "%{:.0%}"),
    "site_siniri_asim_kwh": ("Site sınırı (180 kW) aşımı", "{:,.0f} kWh"),
    "min_gerilim_pu": ("En düşük gerilim", "{:.3f} p.u."),
    "max_kablo_yuklenme_pct": ("En yüksek kablo yüklenmesi", "%{:.0f}"),
    "max_trafo_yuklenme_pct": ("En yüksek trafo yüklenmesi", "%{:.0f}"),
}


def fmt(value, pattern):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if v != v:   # NaN
        return "—"
    if "%}" in pattern:
        pattern, v = pattern.replace("%{:.0%}", "%{:.0f}"), v * 100
    spec = pattern[pattern.index("{"): pattern.index("}") + 1]
    number = spec.format(v).replace(",", "§").replace(".", ",").replace("§", ".")   # Türkçe: 1.234,5
    return pattern.replace(spec, number)   # birimdeki noktalar ("p.u.") değişmesin


cfg = load_config()
scenarios = list(SCENARIOS.values())
table = scenario_table(scenarios, cfg, grid=PandapowerGrid(cfg))
out_csv = REPO_ROOT / "results" / "senaryo_tablosu.csv"
out_csv.parent.mkdir(exist_ok=True)
table.to_csv(out_csv)

names = [s.name for s in scenarios]
header = "| KPI | " + " | ".join(names + BEKLENEN) + " |"
lines = [header, "| --- |" + " --- |" * (len(names) + len(BEKLENEN))]
for kpi, (title, pattern) in ROWS.items():
    cells = [fmt(table.loc[kpi, n], pattern) for n in names] + ["bekleniyor"] * len(BEKLENEN)
    lines.append(f"| {title} | " + " | ".join(cells) + " |")
md = "\n".join(lines)

out_md = REPO_ROOT / "docs" / "raporlar" / "hafta8-ym1-senaryolar.md"
out_md.write_text(
    "# Senaryolar arası karşılaştırma (yıllık)\n\n"
    "Bandırma, 24 temsili gün (4 mevsim × 2 gün tipi × 3 gökyüzü) → yıl; pandapower yük akışıyla. "
    "Üreten betik: `scripts/ym1_hafta8_senaryolar.py`.\n\n"
    f"{md}\n\n"
    + "".join(f"- {s.name}: {s.description}" + (" **Geçici:** sahte modülle çalışıyor.\n" if s.temporary and "GEÇİCİ" not in s.description else "\n")
              for s in scenarios)
    + "\n\"bekleniyor\" sütunları YM-2 istasyon modeli ve YM-3 EMS'i senaryo listesine eklenince aynı betikle dolacak.\n",
    encoding="utf-8",
)
print(md)
print(f"\nYazıldı: {out_csv}\nYazıldı: {out_md}")
