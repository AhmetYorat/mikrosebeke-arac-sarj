"""Tipik anlar için tek seferlik yük akışı:  python -m microgrid.grid

EM-2 ile sonuçları yorumlamak için. Sabit yük değerleri YM-1'in BDEW profillerinden (hafta içi ortalama gün).
"""
from microgrid.config import load_config
from microgrid.grid import PandapowerGrid
from microgrid.interfaces import GridInjections

cfg = load_config()
limit = cfg["station"]["power_limit_kw"]
installed = sum(c["count"] * c["power_kw"] for c in cfg["station"]["chargers"])
bess = cfg["bess"]["power_kw"]

CASES = [
    ("Boş ağ", GridInjections(pv_kw=0, base_load_kw=0, ev_kw=0, bess_kw=0)),
    ("Haziran 13:00, PV fazlası", GridInjections(pv_kw=71, base_load_kw=31, ev_kw=0, bess_kw=0)),
    (f"Aralık 18:00, istasyon {limit} kW", GridInjections(pv_kw=0, base_load_kw=38, ev_kw=limit, bess_kw=0)),
    (f"Aralık 18:00, istasyon {limit} kW + BESS deşarj", GridInjections(0, 38, limit, -bess)),
    (f"Tüm üniteler ({installed} kW), sınırsız", GridInjections(0, 38, installed, 0)),
]

grid = PandapowerGrid(cfg)
v_min = cfg["grid"]["voltage_min_pu"]
print(f"{'Durum':42s} {'min V':>7s} {'kablo %':>8s} {'trafo %':>8s}  bara gerilimleri (p.u.)")
for name, inj in CASES:
    r = grid.run(None, inj)
    flag = "  <-- gerilim sınırı altında" if r.min_vm_pu < v_min else ""
    flag += "  <-- kablo aşırı yüklü" if r.max_line_loading_pct > cfg["grid"]["max_loading_percent"] else ""
    buses = ", ".join(f"{k} {v:.3f}" for k, v in grid.bus_voltages().items())
    print(f"{name:42s} {r.min_vm_pu:7.3f} {r.max_line_loading_pct:8.1f} {r.trafo_loading_pct:8.1f}  {buses}{flag}")
