"""pandapower ağı ve yük akışı (YM-4 + EM-2). Sözleşmedeki GridModel arayüzünü uygular.

Ağ (config: grid.network):

    şebeke (OG) ── trafo ── AG ana pano (PCC) ─┬─ kablo "site"    ── sabit yük, PV
                                               └─ kablo "station" ── şarj istasyonu, BESS

pandapower MW ile çalışır, bizim arayüzümüz kW: çeviri yalnızca bu dosyada yapılır.
İşaret kuralı pandapower'la aynı: load ve storage tüketirken pozitif, sgen üretirken pozitif.
"""
from __future__ import annotations

import math
import warnings

import pandapower as pp

from microgrid.interfaces import GridInjections, GridResult, StepContext

KW = 1e-3  # kW -> MW


class PandapowerGrid:
    """Her adımda güçleri ağa yazar ve yük akışını çalıştırır."""

    def __init__(self, cfg: dict):
        g = cfg["grid"]
        n = g["network"]
        self.net = net = pp.create_empty_network(name="mikro-sebeke")

        mv = pp.create_bus(net, vn_kv=n["mv_kv"], name="OG")
        pcc = pp.create_bus(net, vn_kv=0.4, name="AG ana pano (PCC)")
        pp.create_ext_grid(net, mv, vm_pu=n["ext_grid_vm_pu"], name="Şebeke")
        self.trafo = pp.create_transformer(net, mv, pcc, std_type=n["trafo_std_type"], name="Trafo")

        self.bus = {"pcc": pcc}
        self.line = {}
        for name, f in n["feeders"].items():
            b = pp.create_bus(net, vn_kv=0.4, name=f"{name} ucu")
            self.bus[name] = b
            self.line[name] = pp.create_line(net, pcc, b, length_km=f["length_km"], std_type=f["std_type"], name=name)

        at = {k: self.bus[v] for k, v in n["placement"].items()}
        self.base_load = pp.create_load(net, at["base_load"], p_mw=0, name="Sabit yük")
        self.ev = pp.create_load(net, at["ev"], p_mw=0, name="Şarj istasyonu")
        self.pv = pp.create_sgen(net, at["pv"], p_mw=0, name="PV")
        self.bess = pp.create_storage(net, at["bess"], p_mw=0, max_e_mwh=cfg["bess"]["capacity_kwh"] * KW, name="BESS")
        self.tan_phi = math.tan(math.acos(n["base_load_power_factor"]))

    def run(self, ctx: StepContext | None, injections: GridInjections) -> GridResult:
        net = self.net
        net.load.at[self.base_load, "p_mw"] = injections.base_load_kw * KW
        net.load.at[self.base_load, "q_mvar"] = injections.base_load_kw * KW * self.tan_phi
        net.load.at[self.ev, "p_mw"] = injections.ev_kw * KW
        net.sgen.at[self.pv, "p_mw"] = injections.pv_kw * KW
        net.storage.at[self.bess, "p_mw"] = injections.bess_kw * KW
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                pp.runpp(net, numba=False)  # numba kurulu değil; 4 baralı ağda hız farkı yok
        except pp.LoadflowNotConverged:
            nan = float("nan")
            return GridResult(False, nan, nan, nan, nan)

        lv = net.res_bus.vm_pu.drop(net.ext_grid.bus.iloc[0])  # OG barası sabit tutulduğu için dışarıda
        return GridResult(
            converged=True,
            min_vm_pu=float(lv.min()),
            max_vm_pu=float(lv.max()),
            max_line_loading_pct=float(net.res_line.loading_percent.max()),
            trafo_loading_pct=float(net.res_trafo.loading_percent.at[self.trafo]),
        )

    def bus_voltages(self) -> dict[str, float]:
        """Son yük akışında AG baralarının gerilimi (p.u.). Açıklama ve hata ayıklama için."""
        return {name: float(self.net.res_bus.vm_pu.at[b]) for name, b in self.bus.items()}

    def line_loadings(self) -> dict[str, float]:
        """Son yük akışında kabloların yüklenmesi (%)."""
        return {name: float(self.net.res_line.loading_percent.at[i]) for name, i in self.line.items()}
