"""Döngüyü 24 saat çalıştırır:  python -m microgrid.sim

v0 (Hafta 4): PV, sabit yük ve tarife gerçek veriden gelir (YM-1, build_inputs).
İstasyon ve EMS henüz sahte (mock): kontrolsüz şarj (Senaryo 2). YM-2/YM-3 modülleri gelince değişecek.

Seçenekler:
    --gun haziran | aralik | ikisi   temsili gün (ekip kararı: Haziran ve Aralık hafta içi ortalaması).
                                     Verilmezse config'teki simulation.start kullanılır.
    --mock                           girdiler için de sahte veri
Veri dosyaları (data/processed/) yoksa döngü uyarı verip sahte girdilerle çalışır (YM-4, sim/setup.py).

Önce veri hazırlanmalı (bir kez):  python -m microgrid.data
Sonuçlar results/ altına yazılır (repoya girmez).
"""
import argparse

from microgrid.config import REPO_ROOT, load_config
from microgrid.grid import PandapowerGrid
from microgrid.sim.loop import run, time_index
from microgrid.sim.mocks import MockStation, SimpleBattery, UncontrolledEMS, mock_inputs
from microgrid.sim.setup import SAHTE, TEMSILI_GUNLER, load_inputs, with_start

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--gun", choices=[*TEMSILI_GUNLER, "ikisi"])
parser.add_argument("--mock", action="store_true", help="girdiler için sahte veri")
args = parser.parse_args()

if args.gun is None:
    days = {"config": None}
elif args.gun == "ikisi":
    days = TEMSILI_GUNLER
else:
    days = {args.gun: TEMSILI_GUNLER[args.gun]}

out = REPO_ROOT / "results"
out.mkdir(exist_ok=True)
grid = PandapowerGrid(load_config())

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
    result = run(cfg, inputs, MockStation(cfg, index[0]), UncontrolledEMS(), SimpleBattery(cfg), grid=grid)

    prefix = f"{'mock' if source == SAHTE else 'v0'}_{name}"
    result.steps.to_csv(out / f"{prefix}_steps.csv")
    result.station.to_csv(out / f"{prefix}_station.csv", index=False)

    s = result.steps
    peak = s["grid_kw"].idxmax()
    limit = cfg["grid"]["site_import_limit_kw"]
    print(f"\n[{name}] {index[0]:%d.%m.%Y %H:%M} başlangıç, {len(s)} adım -> {out / prefix}_steps.csv")
    print(f"  PV {s['pv_kw'].sum() * 0.25:.0f} kWh, sabit yük {s['base_load_kw'].sum() * 0.25:.0f} kWh, "
          f"araç şarjı {s['ev_kw'].sum() * 0.25:.0f} kWh")
    print(f"  Şebeke tepe yükü: {s['grid_kw'].max():.0f} kW ({peak:%H:%M}), istasyon tepe: {s['ev_kw'].max():.0f} kW, "
          f"site sınırı ({limit} kW) aşılan adım: {(s['grid_kw'] > limit).sum()}")
    print(f"  Toplam maliyet: {s['cost_tl'].sum():.0f} TL")
    print(f"  En düşük gerilim: {s['min_vm_pu'].min():.3f} p.u. ({s['min_vm_pu'].idxmin():%H:%M}), "
          f"en yüksek kablo yüklenmesi: %{s['max_line_loading_pct'].max():.0f}, trafo: %{s['trafo_loading_pct'].max():.0f}")
