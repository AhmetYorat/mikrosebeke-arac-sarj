"""Bir senaryoyu temsili gün(ler)de çalıştırır:  python -m microgrid.sim

PV, sabit yük ve tarife gerçek veriden (YM-1), istasyon gerçek model (YM-2), EMS ve batarya senaryoya göre (YM-3).
Bütün senaryoları birlikte ve rapor tablolarıyla çalıştırmak için: python -m microgrid.sim.sonuclar

Seçenekler:
    --senaryo S1..S6                 hangi senaryo (varsayılan S2, kontrolsüz şarj). Liste: sim/scenarios.py
    --gun haziran | aralik | ikisi   temsili gün (ekip kararı: Haziran ve Aralık hafta içi ortalaması).
                                     Verilmezse config'teki simulation.start kullanılır.
    --mock                           girdiler için de sahte veri
Veri dosyaları (data/processed/) yoksa döngü uyarı verip sahte girdilerle çalışır (YM-4, sim/setup.py).

Önce veri hazırlanmalı (bir kez):  python -m microgrid.data
Sonuçlar results/ altına yazılır (repoya girmez). S2'nin dosya adları v0 ile aynıdır (v0_<gün>_steps.csv);
diğer senaryolarda sona senaryo kodu eklenir (v0_<gün>_S3_steps.csv).
"""
import argparse

from microgrid.config import REPO_ROOT, load_config
from microgrid.grid import PandapowerGrid
from microgrid.sim.loop import time_index
from microgrid.sim.mocks import mock_inputs
from microgrid.sim.scenarios import SCENARIOS, simulate
from microgrid.sim.setup import SAHTE, TEMSILI_GUNLER, load_inputs, with_start

CODES = {name.split()[0]: name for name in SCENARIOS}

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--senaryo", choices=list(CODES), default="S2")
parser.add_argument("--gun", choices=[*TEMSILI_GUNLER, "ikisi"])
parser.add_argument("--mock", action="store_true", help="girdiler için sahte veri")
args = parser.parse_args()
scenario = SCENARIOS[CODES[args.senaryo]]

if args.gun is None:
    days = {"config": None}
elif args.gun == "ikisi":
    days = TEMSILI_GUNLER
else:
    days = {args.gun: TEMSILI_GUNLER[args.gun]}

out = REPO_ROOT / "results"
out.mkdir(exist_ok=True)
print(f"Senaryo: {scenario.name}")

for name, start in days.items():
    cfg = with_start(load_config(), start)
    index = time_index(cfg)
    if args.mock:
        inputs, source = mock_inputs(cfg, index), SAHTE
    else:
        inputs, source = load_inputs(cfg, index)
        if source == SAHTE:
            print("UYARI: data/processed/ dosyaları yok, sahte girdilerle çalışılıyor. "
                  "Gerçek veri için bir kez: python -m microgrid.data")
    result = simulate(cfg, scenario, inputs, PandapowerGrid(cfg))
    sessions = result.sessions

    prefix = f"{'mock' if source == SAHTE else 'v0'}_{name}" + ("" if args.senaryo == "S2" else f"_{args.senaryo}")
    result.steps.to_csv(out / f"{prefix}_steps.csv")
    result.station.to_csv(out / f"{prefix}_station.csv", index=False)

    s = result.steps
    dt = cfg["simulation"]["step_minutes"] / 60
    peak = s["grid_kw"].idxmax()
    limit = cfg["grid"]["site_import_limit_kw"]
    print(f"\n[{name}] {index[0]:%d.%m.%Y %H:%M} başlangıç, {len(s)} adım -> {out / prefix}_steps.csv")
    print(f"  PV {s['pv_kw'].sum() * dt:.0f} kWh, sabit yük {s['base_load_kw'].sum() * dt:.0f} kWh, "
          f"araç şarjı {s['ev_kw'].clip(lower=0).sum() * dt:.0f} kWh")
    print(f"  Şebeke tepe yükü: {s['grid_kw'].max():.0f} kW ({peak:%H:%M}), istasyon tepe: {s['ev_kw'].max():.0f} kW, "
          f"site sınırı ({limit} kW) aşılan adım: {(s['grid_kw'] > limit + 1e-3).sum()}")
    if len(sessions):
        print(f"  Hedef SOC'ye ulaşan araç: {int(sessions.reached_target.sum())}/{len(sessions)}, "
              f"ortalama bekleme {sessions.waited_h.mean():.1f} sa")
    print(f"  Toplam maliyet: {s['cost_tl'].sum():.0f} TL")
    print(f"  En düşük gerilim: {s['min_vm_pu'].min():.3f} p.u. ({s['min_vm_pu'].idxmin():%H:%M}), "
          f"en yüksek kablo yüklenmesi: %{s['max_line_loading_pct'].max():.0f}, trafo: %{s['trafo_loading_pct'].max():.0f}")
