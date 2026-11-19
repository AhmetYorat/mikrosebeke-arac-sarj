"""Hafta 8 (YM-1): senaryolar arası karşılaştırma tablosu (yıllık, 24 temsili gün, pandapower ile).

Şu an çalışan: S1 (araç yok), S2 (kontrolsüz şarj). S3–S6 için YM-2 istasyonu ve YM-3 EMS'i gerekiyor;
modüller ana koda girince aşağıdaki BEKLENEN listesindeki satırı SCENARIOS'a taşımak yeterli.

Önce veri:  python -m microgrid.data
Sonra:      python scripts/ym1_hafta8_senaryolar.py
Çıktı: results/senaryo_tablosu.csv, docs/raporlar/hafta8-ym1-senaryolar.md (rapora girecek tablo)
"""
from microgrid.analysis import Scenario, scenario_table
from microgrid.config import REPO_ROOT, load_config
from microgrid.grid import PandapowerGrid

SCENARIOS = [
    Scenario("S1 araç yok", config={"vehicles.count": 0}),
    Scenario("S2 kontrolsüz"),
]

# Modüller gelince (örnek; sınıf adları YM-2/YM-3'ün koduna göre değişir):
#   from microgrid.station import ChargingStation
#   from microgrid.ems import RuleBasedEMS, MilpEMS
#   Scenario("S3 akıllı şarj", ems=lambda c: RuleBasedEMS(c), station=lambda c, t: ChargingStation(c, t)),
#   Scenario("S4 akıllı şarj + batarya", ...), Scenario("S5 optimizasyon", ems=lambda c: MilpEMS(c), ...),
#   Scenario("S6 V2G", ...)
BEKLENEN = ["S3 akıllı şarj (kural tabanlı)", "S4 akıllı şarj + batarya", "S5 optimizasyonlu EMS", "S6 V2G"]

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
    text = pattern.replace("%{:.0%}", "%{:.0f}").format(v * 100) if "%}" in pattern else pattern.format(v)
    return text.replace(",", "§").replace(".", ",").replace("§", ".")   # Türkçe: 1.234,5


cfg = load_config()
table = scenario_table(SCENARIOS, cfg, grid=PandapowerGrid(cfg))
out_csv = REPO_ROOT / "results" / "senaryo_tablosu.csv"
out_csv.parent.mkdir(exist_ok=True)
table.to_csv(out_csv)

names = [s.name for s in SCENARIOS]
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
    "S1–S2 sahte istasyonla (20 araç, 10 ünite). S3–S6 YM-2 istasyon modeli ve YM-3 EMS'i ana koda girince "
    "aynı betikle doldurulacak.\n",
    encoding="utf-8",
)
print(md)
print(f"\nYazıldı: {out_csv}\nYazıldı: {out_md}")
