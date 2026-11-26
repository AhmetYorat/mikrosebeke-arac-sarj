"""ems/milp.py: kayan ufuklu MILP EMS (YM-3, Hafta 7)."""
import copy

import numpy as np
import pandas as pd
import pytest

pulp = pytest.importorskip("pulp")
if not pulp.PULP_CBC_CMD(msg=False).available():     # pragma: no cover
    pytest.skip("CBC çözücüsü yok (pip install 'pulp>=2.9,<4')", allow_module_level=True)

from microgrid.config import load_config
from microgrid.data.tariff import price_series
from microgrid.ems.bess import BESS
from microgrid.ems.milp import MilpEMS
from microgrid.ems.rule_based import RuleBasedEMS
from microgrid.interfaces import EmsInputs, StepContext, VehicleRequest
from microgrid.kpi import compute
from microgrid.sim.loop import run, time_index
from microgrid.sim.mocks import MockStation, mock_inputs

TZ = "Europe/Istanbul"


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def index(cfg):
    return time_index(cfg)


@pytest.fixture()
def ems(cfg, index):
    e = MilpEMS(cfg)
    e.prepare(pd.DataFrame({"pv_kw": 0.0, "base_load_kw": 30.0, "price_tl_per_kwh": price_series(cfg, index)}))
    return e


def _inp(cfg, index, hhmm, vehicles, pv=0.0, base=30.0, bess_soc=0.5, station_limit=150.0, site_limit=180.0):
    ts = pd.Timestamp(f"{'2023-06-21' if hhmm >= '12:00' else '2023-06-22'} {hhmm}", tz=TZ)
    step = int((ts - index[0]) / pd.Timedelta(minutes=15))
    return EmsInputs(
        ctx=StepContext(step=step, timestamp=ts, dt_h=0.25), pv_kw=pv, base_load_kw=base,
        price_tl_per_kwh=float(price_series(cfg, index).iloc[step]), vehicles=list(vehicles), bess_soc=bess_soc,
        station_limit_kw=station_limit, site_limit_kw=site_limit,
    )


def _veh(cid="AC1", soc=0.4, target=0.8, dep="2023-06-22 07:30", max_kw=22.0):
    return VehicleRequest(cid, f"EV-{cid}", soc, 60.0, target, pd.Timestamp(dep, tz=TZ), max_kw)


def test_decide_requires_prepare(cfg, index):
    with pytest.raises(RuntimeError):
        MilpEMS(cfg).decide(_inp(cfg, index, "19:00", []))


def test_vehicle_waits_for_cheap_tariff(cfg, index, ems):
    v = _veh()
    assert ems.decide(_inp(cfg, index, "19:00", [v], bess_soc=0.5)).ev_kw["AC1"] == pytest.approx(0.0, abs=1e-6)
    assert ems.decide(_inp(cfg, index, "22:00", [v], bess_soc=0.5)).ev_kw["AC1"] > 0.0
    assert ems.fallbacks == 0


def test_vehicle_that_cannot_make_it_charges_at_full_power(cfg, index, ems):
    v = _veh(soc=0.05, dep="2023-06-21 21:00")     # 45 kWh gerek, 2 saatte en çok 44 kWh verilebilir
    assert ems.decide(_inp(cfg, index, "19:00", [v])).ev_kw["AC1"] == pytest.approx(22.0, abs=1e-3)


def test_respects_station_and_site_limits(cfg, index, ems):
    vs = [_veh(f"AC{i}", soc=0.2, dep="2023-06-21 21:00") for i in range(1, 9)]
    d = ems.decide(_inp(cfg, index, "19:00", vs, base=60.0, bess_soc=0.5))
    assert sum(d.ev_kw.values()) <= 150.0 + 1e-4
    assert 60.0 + sum(d.ev_kw.values()) + d.bess_kw <= 180.0 + 1e-4


def test_battery_arbitrage_has_the_right_sign(cfg, index, ems):
    """Eski MILP'teki işaret hatasının regresyon testi: deşarj şebeke alımını AZALTMALI.

    Puant boyunca (19:00-22:00) adım adım çalıştırılır; eşit fiyatlı adımlarda ne zaman deşarj ettiği önemli değil."""
    bess, drawn, grid = BESS(cfg), 0.0, []
    for h in range(19, 22):
        for m in (0, 15, 30, 45):
            d = ems.decide(_inp(cfg, index, f"{h}:{m:02d}", [], base=40.0, bess_soc=bess.soc))
            p = bess.apply(d.bess_kw, 0.25)
            drawn += -p * 0.25 if p < 0 else 0.0
            grid.append(40.0 + p)
    assert drawn > 40.0                                # puantta bataryadan en az 40 kWh verildi
    assert min(grid) >= -1e-6                          # şebekeye veriş yok
    night = ems.decide(_inp(cfg, index, "22:00", [], base=40.0, bess_soc=0.3))
    assert night.bess_kw > 1.0                         # gece ucuzken şarj olur (gün sonu hedefi + puant için)


def test_battery_never_charges_and_discharges_together(cfg, index, ems):
    for hhmm in ["13:00", "19:00", "23:00", "05:00"]:
        d = ems.decide(_inp(cfg, index, hhmm, [], base=40.0, bess_soc=0.5))
        assert abs(d.bess_kw) <= cfg["bess"]["power_kw"] + 1e-6


def test_pv_surplus_is_stored_for_puant(cfg, index):
    e = MilpEMS(cfg)
    pv = np.where(index.hour < 17, 90.0, 0.0)          # öğleden sonra PV fazlası, akşam yok
    fc = pd.DataFrame({"pv_kw": pv, "base_load_kw": 30.0, "price_tl_per_kwh": price_series(cfg, index)})
    e.prepare(fc)
    d = e.decide(_inp(cfg, index, "13:00", [], pv=90.0, base=30.0, bess_soc=0.3))
    assert d.bess_kw > 20.0


def test_solver_failure_falls_back_to_rule_based(cfg, index, ems, monkeypatch):
    def boom(_):
        raise RuntimeError("çözücü yok")
    monkeypatch.setattr(ems, "_solve", boom)
    d = ems.decide(_inp(cfg, index, "22:00", [_veh()]))
    assert ems.fallbacks == 1
    assert d.ev_kw["AC1"] >= 0.0


def _small(cfg, n=6):
    c = copy.deepcopy(cfg)
    c["vehicles"]["count"] = n
    return c


def test_loop_milp_not_costlier_than_rule_based_and_meets_targets(cfg, index):
    c = _small(cfg)
    inputs = mock_inputs(c, index)

    def go(ems):
        st = MockStation(c, index[0], seed=0)
        return run(c, inputs, st, ems, BESS(c)).steps, st

    s4, st4 = go(RuleBasedEMS(c, use_bess=True))
    m = MilpEMS(c)
    s5, st5 = go(m)
    k4, k5 = compute(s4, c), compute(s5, c)
    assert m.fallbacks == 0 and m.solves == len(index)
    assert k5["maliyet_tl"] <= k4["maliyet_tl"] * 1.02      # kusursuz tahminle MILP kuraldan kötü olmamalı (%2: yeniden çözüm payı)
    assert k5["tepe_alim_kw"] <= k4["tepe_alim_kw"] + 1e-6
    assert k5["arac_sarj_kwh"] == pytest.approx(k4["arac_sarj_kwh"], rel=1e-3)
    # aynı araç, aynı SOC ile ayrılıyor
    soc4 = {v["id"]: v["soc"] for v in st4.vehicles}
    soc5 = {v["id"]: v["soc"] for v in st5.vehicles}
    assert all(soc5[k] >= soc4[k] - 0.01 for k in soc4)
    # fiziksel tutarlılık
    assert ((s5.base_load_kw + s5.ev_kw + s5.bess_kw - s5.pv_kw) - s5.grid_kw).abs().max() < 1e-9
    assert s5.bess_soc.between(c["bess"]["soc_min"] - 1e-9, c["bess"]["soc_max"] + 1e-9).all()
    assert s5.bess_soc.iloc[-1] >= c["bess"]["soc_initial"] - 0.02
    assert (s5.ev_kw <= c["station"]["power_limit_kw"] + 1e-4).all()
    assert s5.grid_kw.max() <= c["grid"]["site_import_limit_kw"] + 1e-4
