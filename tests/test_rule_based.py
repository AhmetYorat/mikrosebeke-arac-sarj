"""ems/rule_based.py: SOC eşikli, tarifeye duyarlı akıllı şarj (YM-3, Hafta 5)."""
import numpy as np
import pandas as pd
import pytest

from microgrid.config import load_config
from microgrid.data.tariff import price_series
from microgrid.ems.bess import BESS
from microgrid.ems.rule_based import RuleBasedEMS
from microgrid.interfaces import EmsInputs, StepContext, VehicleRequest
from microgrid.kpi import compute
from microgrid.sim.loop import run, time_index
from microgrid.sim.mocks import MockStation, UncontrolledEMS, mock_inputs

TZ = "Europe/Istanbul"


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def index(cfg):
    return time_index(cfg)


@pytest.fixture()
def ems(cfg, index):
    e = RuleBasedEMS(cfg)
    e.prepare(pd.DataFrame({"pv_kw": 0.0, "base_load_kw": 30.0, "price_tl_per_kwh": price_series(cfg, index)}))
    return e


def _inp(cfg, index, hhmm, vehicles, pv=0.0, base=30.0, station_limit=150.0, site_limit=180.0):
    ts = pd.Timestamp(f"{'2023-06-21' if hhmm >= '12:00' else '2023-06-22'} {hhmm}", tz=TZ)
    step = int((ts - index[0]) / pd.Timedelta(minutes=15))
    return EmsInputs(
        ctx=StepContext(step=step, timestamp=ts, dt_h=0.25), pv_kw=pv, base_load_kw=base,
        price_tl_per_kwh=float(price_series(cfg, index).iloc[step]), vehicles=list(vehicles), bess_soc=0.5,
        station_limit_kw=station_limit, site_limit_kw=site_limit,
    )


def _veh(cid="AC1", soc=0.4, target=0.8, kwh=60.0, dep="2023-06-22 07:30", max_kw=22.0):
    return VehicleRequest(cid, f"EV-{cid}", soc, kwh, target, pd.Timestamp(dep, tz=TZ), max_kw)


def test_waits_in_puant_then_charges_in_night_tier(cfg, index, ems):
    v = _veh()
    assert ems.decide(_inp(cfg, index, "19:00", [v])).ev_kw["AC1"] == 0.0       # puant: bekle
    assert ems.decide(_inp(cfg, index, "22:00", [v])).ev_kw["AC1"] > 0.0        # gece dilimi başladı


def test_night_charge_is_spread_evenly_not_full_power(cfg, index, ems):
    v = _veh(soc=0.4)                           # 24 kWh gerek; küme = gece dilimi (22:00-06:00 = 32 adım)
    p = ems.decide(_inp(cfg, index, "22:00", [v])).ev_kw["AC1"]
    assert p == pytest.approx(24.0 / (32 * 0.25), rel=1e-6)
    assert p < 22.0 / 5                          # tam gücün çok altında: geri tepme tepesi yok


def test_energy_is_delivered_by_departure_when_following_the_rule(cfg, index, ems):
    """Aynı aracı pencere boyunca kuralla sürerek hedefe ulaşıldığını gösterir (CC-CV'siz)."""
    soc, dep = 0.35, pd.Timestamp("2023-06-22 07:30", tz=TZ)
    t = pd.Timestamp("2023-06-21 19:00", tz=TZ)
    while t < dep:
        v = VehicleRequest("AC1", "EV", soc, 60.0, 0.8, dep, 22.0)
        p = ems.decide(_inp(cfg, index, f"{t:%H:%M}", [v])).ev_kw["AC1"] if soc < 0.8 else 0.0
        soc += p * 0.25 / 60
        t += pd.Timedelta(minutes=15)
    assert soc == pytest.approx(0.8, abs=1e-6)


def test_soc_floor_charges_immediately_even_in_puant(cfg, index, ems):
    low = _veh(soc=0.20)
    p = ems.decide(_inp(cfg, index, "19:00", [low])).ev_kw["AC1"]
    assert p == pytest.approx(min(22.0, (0.30 - 0.20) * 60 / 0.25))     # 0.1 × 60 kWh = 6 kWh → bir adımda 22 kW sınırı
    ok = _veh(soc=0.35)
    assert ems.decide(_inp(cfg, index, "19:00", [ok])).ev_kw["AC1"] == 0.0


def test_floor_power_stops_at_floor(cfg, index, ems):
    just_below = _veh(soc=0.299)
    p = ems.decide(_inp(cfg, index, "19:00", [just_below])).ev_kw["AC1"]
    assert p == pytest.approx(0.001 * 60 / 0.25)


def test_infeasible_window_charges_at_full_power(cfg, index, ems):
    v = _veh(soc=0.2, dep="2023-06-21 21:00")      # 2 saatte 36 kWh gerek; 22 kW × 0.8 × 2 h = 35 kWh yetmez
    assert ems.decide(_inp(cfg, index, "19:00", [v])).ev_kw["AC1"] == pytest.approx(22.0)


def test_departure_pressure_pulls_charging_into_expensive_hours(cfg, index, ems):
    """Gece dilimine ulaşmadan ayrılacak araç puantta şarj edilmek zorundadır."""
    v = _veh(soc=0.4, dep="2023-06-21 21:30")
    assert ems.decide(_inp(cfg, index, "19:00", [v])).ev_kw["AC1"] > 0.0


def test_full_vehicle_gets_nothing(cfg, index, ems):
    assert ems.decide(_inp(cfg, index, "23:00", [_veh(soc=0.8)])).ev_kw["AC1"] == 0.0


def test_without_prepare_falls_back_to_flat_tariff(cfg, index):
    e = RuleBasedEMS(cfg)       # prepare çağrılmadı
    p = e.decide(_inp(cfg, index, "19:00", [_veh(soc=0.4)])).ev_kw["AC1"]
    assert p == pytest.approx(24 / (50 * 0.25))      # düz tarife: 24 kWh ayrılışa kadarki 12.5 saate (50 adım) eşit yayılır


def test_pv_surplus_goes_to_vehicles_even_in_puant(cfg, index, ems):
    v = _veh(soc=0.4)
    d = ems.decide(_inp(cfg, index, "19:00", [v], pv=60.0, base=20.0))
    assert d.ev_kw["AC1"] == pytest.approx(22.0)            # fazla 40 kW, ünite 22 kW


def test_station_limit_respected(cfg, index, ems):
    vs = [_veh(f"AC{i}", soc=0.2) for i in range(1, 9)]
    d = ems.decide(_inp(cfg, index, "19:00", vs))
    assert sum(d.ev_kw.values()) == pytest.approx(150.0)


def test_site_limit_respected_in_december_like_case(cfg, index, ems):
    vs = [_veh(f"AC{i}", soc=0.2) for i in range(1, 9)]
    d = ems.decide(_inp(cfg, index, "19:00", vs, base=60.0, site_limit=180.0))
    assert 60.0 + sum(d.ev_kw.values()) <= 180.0 + 1e-9


def test_site_limit_includes_pv(cfg, index, ems):
    vs = [_veh(f"AC{i}", soc=0.2) for i in range(1, 9)]
    d = ems.decide(_inp(cfg, index, "19:00", vs, base=60.0, pv=20.0, site_limit=180.0, station_limit=500.0))
    assert 60.0 - 20.0 + sum(d.ev_kw.values()) <= 180.0 + 1e-9


def test_limit_serves_earliest_departure_first(cfg, index, ems):
    early = _veh("AC1", soc=0.2, dep="2023-06-21 23:00")
    late = _veh("AC2", soc=0.2, dep="2023-06-22 08:00")
    d = ems.decide(_inp(cfg, index, "19:00", [late, early], station_limit=22.0))
    assert d.ev_kw["AC1"] == pytest.approx(22.0) and d.ev_kw["AC2"] == pytest.approx(0.0)


def test_never_negative_and_never_above_unit_limit(cfg, index, ems):
    vs = [_veh(f"AC{i}", soc=0.1 + 0.05 * i) for i in range(1, 9)]
    for h in ["19:00", "21:45", "22:00", "03:00", "07:00"]:
        d = ems.decide(_inp(cfg, index, h, vs))
        assert all(0.0 <= p <= 22.0 + 1e-9 for p in d.ev_kw.values())


# --- döngüde: S2 (kontrolsüz) ile karşılaştırma ---

def _run(cfg, index, ems, seed=0):
    station = MockStation(cfg, index[0], seed=seed)
    steps = run(cfg, mock_inputs(cfg, index), station, ems, BESS(cfg)).steps
    return steps, {v["id"]: v["soc"] for v in station.vehicles}


def test_loop_smart_beats_uncontrolled_on_cost_puant_and_peak(cfg, index):
    s2, soc2 = _run(cfg, index, UncontrolledEMS())
    s3, soc3 = _run(cfg, index, RuleBasedEMS(cfg))
    k2, k3 = compute(s2, cfg), compute(s3, cfg)
    assert k3["arac_sarj_kwh"] == pytest.approx(k2["arac_sarj_kwh"], rel=1e-6)    # aynı enerji
    assert k3["arac_sarj_puant_payi"] < 0.1 < k2["arac_sarj_puant_payi"]
    assert k3["maliyet_tl"] < k2["maliyet_tl"]
    assert k3["tepe_alim_kw"] < k2["tepe_alim_kw"]
    assert (s3.ev_kw <= cfg["station"]["power_limit_kw"] + 1e-6).all()
    assert s3.grid_kw.max() <= cfg["grid"]["site_import_limit_kw"] + 1e-6
    # kullanıcı memnuniyeti: hiçbir araç kontrolsüz şarjdan daha düşük SOC ile ayrılmadı
    assert all(soc3[k] >= soc2[k] - 0.01 for k in soc2)


def test_loop_no_rebound_peak_after_puant(cfg, index):
    """Gece dilimine geçerken yeni bir tepe oluşmamalı (YM-4'ün ilk denemesinde 157 → 180 kW'a çıkmıştı)."""
    s3, _ = _run(cfg, index, RuleBasedEMS(cfg))
    night = s3[(s3.index.hour >= 22) | (s3.index.hour < 6)]
    assert night.ev_kw.max() < 0.6 * cfg["station"]["power_limit_kw"]


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_loop_other_seeds_same_energy_and_no_worse_satisfaction(cfg, index, seed):
    s2, soc2 = _run(cfg, index, UncontrolledEMS(), seed=seed)
    s3, soc3 = _run(cfg, index, RuleBasedEMS(cfg), seed=seed)
    assert s3.ev_kw.sum() == pytest.approx(s2.ev_kw.sum(), rel=1e-6)
    assert all(soc3[k] >= soc2[k] - 0.01 for k in soc2)
    assert (s3.ev_kw <= cfg["station"]["power_limit_kw"] + 1e-6).all()
