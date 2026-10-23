"""Döngüyü sahte modüllerle çalıştırır:  python -m microgrid.sim

Sonuçlar results/ altına yazılır (repoya girmez).
"""
from microgrid.config import REPO_ROOT, load_config
from microgrid.grid import PandapowerGrid
from microgrid.sim.loop import run, time_index
from microgrid.sim.mocks import MockStation, SimpleBattery, UncontrolledEMS, mock_inputs

cfg = load_config()
index = time_index(cfg)
result = run(
    cfg, mock_inputs(cfg, index), MockStation(cfg, index[0]), UncontrolledEMS(), SimpleBattery(cfg),
    grid=PandapowerGrid(cfg),
)

out = REPO_ROOT / "results"
out.mkdir(exist_ok=True)
result.steps.to_csv(out / "mock_steps.csv")
result.station.to_csv(out / "mock_station.csv", index=False)

s = result.steps
peak = s["grid_kw"].idxmax()
print(f"{len(s)} adım, sonuçlar: {out}")
print(f"Şebeke tepe yükü: {s['grid_kw'].max():.0f} kW ({peak:%H:%M}), istasyon tepe: {s['ev_kw'].max():.0f} kW")
print(f"Toplam maliyet: {s['cost_tl'].sum():.0f} TL")
print(f"En düşük gerilim: {s['min_vm_pu'].min():.3f} p.u. ({s['min_vm_pu'].idxmin():%H:%M}), "
      f"en yüksek kablo yüklenmesi: %{s['max_line_loading_pct'].max():.0f}, trafo: %{s['trafo_loading_pct'].max():.0f}")
