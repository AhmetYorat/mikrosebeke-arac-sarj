"""V2G: kural tabanlı EMS (YM-3, Hafta 8) ve V2G'li sahte istasyon."""
import pandas as pd
import pytest

from microgrid.config import load_config
from microgrid.data.tariff import price_series
from microgrid.ems.bess import BESS
from microgrid.ems.rule_based import RuleBasedEMS
from microgrid.interfaces import EmsInputs, StepContext, VehicleRequest
from microgrid.kpi import compute
from microgrid.sim.loop import run, time_index
from microgrid.sim.mocks import V2GMockStation, mock_inputs

TZ = "Europe/Istanbul"


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def index(cfg):
    return time_index(cfg)


def _prepared(e, cfg, index):
    e.prepare(pd.DataFrame({"pv_kw": 0.0, "base_load_kw": 30.0, "price_tl_per_kwh": price_series(cfg, index)}))
    return e


@pytest.fixture()
def ems(cfg, index):
    return _prepared(RuleBasedEMS(cfg, use_bess=False, v2g=True), cfg, index)


def _inp(cfg, index, hhmm, vehicles, pv=0.0, base=30.0, bess_soc=0.5, station_limit=150.0, site_limit=180.0):
    ts = pd.Timestamp(f"{'2023-06-21' if hhmm >= '12:00' else '2023-06-22'} {hhmm}", tz=TZ)
    step = int((ts - index[0]) / pd.Timedelta(minutes=15))
    return EmsInputs(
        ctx=StepContext(step=step, timestamp=ts, dt_h=0.25), pv_kw=pv, base_load_kw=base,
        price_tl_per_kwh=float(price_series(cfg, index).iloc[step]), vehicles=list(vehicles), bess_soc=bess_soc,
        station_limit_kw=station_limit, site_limit_kw=site_limit,
    )


def _veh(cid="AC1", soc=0.7, target=0.8, dep="2023-06-22 07:30", max_kw=22.0, dis_kw=11.0):
    return VehicleRequest(cid, f"EV-{cid}", soc, 60.0, target, pd.Timestamp(dep, tz=TZ), max_kw, dis_kw)


def test_v2g_vehicle_covers_puant_load(cfg, index, ems):
    d = ems.decide(_inp(cfg, index, "19:00", [_veh()], base=30.0))
    assert d.ev_kw["AC1"] < -1.0
    assert 30.0 + d.ev_kw["AC1"] >= -1e-9               # şebekeye veriş yok


def test_no_v2g_when_flag_off(cfg, index):
    e = _prepared(RuleBasedEMS(cfg, v2g=False), cfg, index)
    assert e.decide(_inp(cfg, index, "19:00", [_veh()])).ev_kw["AC1"] >= 0.0


def test_vehicle_without_v2g_capability_never_discharges(cfg, index, ems):
    assert ems.decide(_inp(cfg, index, "19:00", [_veh(dis_kw=0.0)])).ev_kw["AC1"] >= 0.0


def test_no_v2g_outside_puant_without_site_pressure(cfg, index, ems):
    assert ems.decide(_inp(cfg, index, "23:00", [_veh()])).ev_kw["AC1"] >= 0.0
    assert ems.decide(_inp(cfg, index, "14:00", [_veh()], base=40.0)).ev_kw["AC1"] >= 0.0


def test_discharge_power_limited_by_vehicle(cfg, index, ems):
    d = ems.decide(_inp(cfg, index, "19:00", [_veh(dis_kw=5.0)], base=80.0))
    assert d.ev_kw["AC1"] >= -5.0 - 1e-9


def test_soc_floor_guarantee(cfg, index, ems):
    """Taban SOC'nin altına inecek kadar deşarj istenmez: 0.31 SOC'de 0.01 × 60 kWh = 0.6 kWh kalır."""
    d = ems.decide(_inp(cfg, index, "19:00", [_veh(soc=0.31)], base=80.0))
    p = -min(d.ev_kw["AC1"], 0.0)
    assert p * 0.25 / 0.95 <= 0.01 * 60 + 1e-9
    d0 = ems.decide(_inp(cfg, index, "19:00", [_veh(soc=0.30)], base=80.0))
    assert d0.ev_kw["AC1"] >= 0.0


def test_target_soc_at_departure_guarantee(cfg, index, ems):
    """Ayrılışa az kala yeniden dolmaya vakit yoksa deşarj yok."""
    v = _veh(soc=0.7, dep="2023-06-21 21:30")          # ayrılıştan önce gece dilimi hiç başlamıyor
    assert ems.decide(_inp(cfg, index, "19:00", [v], base=80.0)).ev_kw["AC1"] >= 0.0


def test_refill_capacity_bounds_discharge(cfg, index, ems):
    """Deşarj edilen enerji, gece dilimindeki yeniden doldurma kapasitesini aşmaz (hedef SOC garantisi)."""
    v = _veh(soc=0.75, dep="2023-06-22 00:00")          # gece diliminde yalnızca 2 saat (8 adım) var
    d = ems.decide(_inp(cfg, index, "19:00", [v], base=80.0))
    need = (0.8 - 0.75) * 60
    refill = 8 * 22.0 * 0.8 * 0.25 * 0.95
    batt_drawn_kwh = -d.ev_kw["AC1"] * 0.25 / 0.95      # bu adımda araç bataryasından çekilen
    assert batt_drawn_kwh <= (refill - need) + 1e-9


def test_vehicle_that_charges_this_step_is_not_discharged(cfg, index, ems):
    v = _veh(soc=0.2, dep="2023-06-21 21:00")           # pencereye sığmıyor: tam güç şarj
    assert ems.decide(_inp(cfg, index, "19:00", [v], base=80.0)).ev_kw["AC1"] > 0.0


def test_v2g_never_exceeds_net_load(cfg, index, ems):
    vs = [_veh(f"AC{i}") for i in range(1, 9)]
    d = ems.decide(_inp(cfg, index, "19:00", vs, base=25.0))
    assert 25.0 + sum(d.ev_kw.values()) >= -1e-9


def test_site_limit_duty_uses_v2g_outside_puant(cfg, index):
    e = _prepared(RuleBasedEMS(cfg, use_bess=False, v2g=True), cfg, index)
    d = e.decide(_inp(cfg, index, "14:00", [_veh()], base=185.0))       # site sınırının 5 kW üstü, gündüz dilimi
    assert 185.0 + sum(d.ev_kw.values()) <= 180.0 + 1e-9


def test_battery_is_used_before_vehicles(cfg, index):
    e = _prepared(RuleBasedEMS(cfg, use_bess=True, v2g=True), cfg, index)
    d = e.decide(_inp(cfg, index, "19:00", [_veh()], base=30.0, bess_soc=0.9))
    assert d.bess_kw < 0
    assert 30.0 + d.bess_kw + d.ev_kw["AC1"] >= -1e-9


# --- V2G'li sahte istasyon ---

def test_v2g_mock_station_flags_share_of_fleet(cfg, index):
    assert sum(v["v2g"] for v in V2GMockStation(cfg, index[0], v2g_share=0.4).vehicles) == 8
    assert sum(v["v2g"] for v in V2GMockStation(cfg, index[0], v2g_share=0.0).vehicles) == 0


def test_v2g_mock_station_discharge_updates_soc_with_losses(cfg, index):
    st = V2GMockStation(cfg, index[0], v2g_share=1.0)
    v = st.vehicles[0]
    ts = v["arrival"].ceil("15min") + pd.Timedelta(minutes=30)
    v["soc"] = 0.6
    ctx = StepContext(step=0, timestamp=ts, dt_h=0.25)
    r = next(r for r in st.requests(ctx) if r.vehicle_id == v["id"])
    assert r.max_discharge_kw > 0
    applied = st.apply(ctx, {r.charger_id: -5.0})
    assert applied[r.charger_id] == pytest.approx(-5.0)
    assert v["soc"] == pytest.approx(0.6 - 5.0 * 0.25 / 0.95 / 60)


def test_v2g_mock_station_never_goes_below_min_soc(cfg, index):
    st = V2GMockStation(cfg, index[0], v2g_share=1.0)
    v = st.vehicles[0]
    ts = v["arrival"].ceil("15min") + pd.Timedelta(minutes=30)
    v["soc"] = 0.3
    ctx = StepContext(step=0, timestamp=ts, dt_h=0.25)
    r = next((r for r in st.requests(ctx) if r.vehicle_id == v["id"]), None)
    assert r is None or r.max_discharge_kw == 0.0
    st.apply(ctx, {v["charger"]: -11.0})
    assert v["soc"] >= 0.3 - 1e-12


# --- döngüde ---

def _loop(cfg, index, ems, v2g_share=0.4, seed=0):
    st = V2GMockStation(cfg, index[0], seed=seed, v2g_share=v2g_share)
    res = run(cfg, mock_inputs(cfg, index), st, ems, BESS(cfg))
    return res, st


def test_loop_rule_v2g_lowers_cost_and_keeps_targets(cfg, index):
    base, st0 = _loop(cfg, index, RuleBasedEMS(cfg, use_bess=True))
    v2g, st1 = _loop(cfg, index, RuleBasedEMS(cfg, use_bess=True, v2g=True))
    b, g = base.steps, v2g.steps
    assert (g.ev_kw < -0.1).any()                                      # gerçekten deşarj oldu
    assert compute(g, cfg)["maliyet_tl"] < compute(b, cfg)["maliyet_tl"]
    # hedef SOC garantisi: hiçbir araç V2G yüzünden daha düşük SOC ile ayrılmadı
    soc0 = {v["id"]: v["soc"] for v in st0.vehicles}
    soc1 = {v["id"]: v["soc"] for v in st1.vehicles}
    assert all(soc1[k] >= soc0[k] - 0.01 for k in soc0)
    # fiziksel tutarlılık ve sınırlar
    assert ((g.base_load_kw + g.ev_kw + g.bess_kw - g.pv_kw) - g.grid_kw).abs().max() < 1e-9
    assert (g.ev_kw <= cfg["station"]["power_limit_kw"] + 1e-6).all()
    assert g.grid_kw.max() <= cfg["grid"]["site_import_limit_kw"] + 1e-6


def test_loop_rule_v2g_min_soc_guarantee(cfg, index):
    """V2G yapan bir araç, ilk deşarjından sonra taban SOC'nin altına inmez."""
    res, _ = _loop(cfg, index, RuleBasedEMS(cfg, use_bess=True, v2g=True))
    for _, grp in res.station.groupby("vehicle_id"):
        if (grp.power_kw < -1e-6).any():
            first = grp.index[grp.power_kw < -1e-6][0]
            assert grp.loc[first:, "soc"].min() >= 0.3 - 0.02


def test_loop_without_v2g_capable_vehicles_changes_nothing(cfg, index):
    a, _ = _loop(cfg, index, RuleBasedEMS(cfg, use_bess=True), v2g_share=0.0)
    b, _ = _loop(cfg, index, RuleBasedEMS(cfg, use_bess=True, v2g=True), v2g_share=0.0)
    pd.testing.assert_frame_equal(a.steps[["ev_kw", "bess_kw", "grid_kw"]], b.steps[["ev_kw", "bess_kw", "grid_kw"]])
