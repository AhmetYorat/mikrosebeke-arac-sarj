"""YM-2: ChargingStation — sözleşmedeki requests/apply arayüzü, atama, sıra, nöbetleşe şarj, oturumlar."""
import pandas as pd
import pytest

from microgrid.config import load_config
from microgrid.interfaces import StepContext
from microgrid.sim.loop import STATION_COLUMNS, run, time_index
from microgrid.sim.mocks import SimpleBattery, UncontrolledEMS, mock_inputs
from microgrid.sim.scenarios import apply_overrides
from microgrid.station import ChargingStation, ElectricVehicle

DT = 0.25


@pytest.fixture
def cfg():
    return load_config()


def start_of(cfg):
    return time_index(cfg)[0]


def ev(i, arrival, hours=13, soc=0.3, target=0.8, max_ac=22.0, battery=60.0):
    return ElectricVehicle(
        vehicle_id=f"T{i:02d}", model_name="Test", battery_kwh=battery, soc_arrival=soc, target_soc=target,
        arrival=arrival, departure=arrival + pd.Timedelta(hours=hours), max_ac_kw=max_ac, max_dc_kw=50.0,
        v2g_capable=False,
    )


def make_station(cfg, vehicles):
    s = ChargingStation(cfg, start_of(cfg))
    s.vehicles = vehicles
    return s


def ctx_at(ts, step=0):
    return StepContext(step=step, timestamp=ts, dt_h=DT)


def test_charger_ids(cfg):
    s = ChargingStation(cfg, start_of(cfg))
    assert list(s.units) == [f"AC{i}" for i in range(1, 9)] + ["DC1", "DC2"]


def test_vehicle_visible_only_while_parked(cfg):
    t = start_of(cfg) + pd.Timedelta(hours=6)
    s = make_station(cfg, [ev(1, t, hours=2)])
    assert s.requests(ctx_at(t - pd.Timedelta(minutes=15))) == []
    reqs = s.requests(ctx_at(t))
    assert [r.vehicle_id for r in reqs] == ["T01"]
    assert reqs[0].charger_id == "AC1" and reqs[0].departure == t + pd.Timedelta(hours=2)
    assert s.requests(ctx_at(t + pd.Timedelta(hours=2))) == []
    assert s.units["AC1"].vehicle is None


def test_ac_filled_before_dc(cfg):
    t = start_of(cfg) + pd.Timedelta(hours=6)
    s = make_station(cfg, [ev(i, t) for i in range(9)])
    reqs = s.requests(ctx_at(t))
    assert sorted(r.charger_id for r in reqs) == sorted([f"AC{i}" for i in range(1, 9)] + ["DC1"])


def test_queue_when_full(cfg):
    t = start_of(cfg) + pd.Timedelta(hours=6)
    s = make_station(cfg, [ev(i, t) for i in range(11)])
    assert len(s.requests(ctx_at(t))) == 10
    assert len(s.queue) == 1


def test_apply_clips_to_obc_and_room(cfg):
    t = start_of(cfg) + pd.Timedelta(hours=6)
    a = ev(1, t, max_ac=11.0)
    b = ev(2, t, soc=0.8 - 2 / 60)          # hedefe 2 kWh kaldı
    s = make_station(cfg, [a, b])
    reqs = {r.vehicle_id: r for r in s.requests(ctx_at(t))}
    assert reqs["T01"].max_charge_kw == 11.0
    applied = s.apply(ctx_at(t), {reqs["T01"].charger_id: 22.0, reqs["T02"].charger_id: 22.0})
    assert applied[reqs["T01"].charger_id] == 11.0
    assert applied[reqs["T02"].charger_id] == pytest.approx(2 / (DT * 0.95))
    assert b.soc == pytest.approx(0.8)


def test_apply_ignores_unknown_and_empty_units(cfg):
    t = start_of(cfg) + pd.Timedelta(hours=6)
    s = make_station(cfg, [ev(1, t)])
    s.requests(ctx_at(t))
    applied = s.apply(ctx_at(t), {"AC7": 22.0, "XX9": 5.0})
    assert sum(applied.values()) == 0.0
    assert "XX9" not in applied and "AC7" not in applied


def test_negative_power_rejected_without_v2g(cfg):
    t = start_of(cfg) + pd.Timedelta(hours=6)
    a = ev(1, t)
    s = make_station(cfg, [a])
    s.requests(ctx_at(t))
    assert s.apply(ctx_at(t), {"AC1": -10.0}) == {"AC1": 0.0}
    assert a.soc == 0.3


def day_run(cfg, station=None):
    index = time_index(cfg)
    station = station or ChargingStation(cfg, index[0])
    return run(cfg, mock_inputs(cfg, index), station, UncontrolledEMS(), SimpleBattery(cfg)), station


def test_energy_conservation_over_a_day(cfg):
    result, station = day_run(cfg)
    eff = cfg["station"]["charge_efficiency"]
    delivered = result.steps.ev_kw.sum() * DT * eff
    gained = sum((v.soc - v.soc_arrival) * v.battery_kwh for v in station.vehicles)
    assert delivered == pytest.approx(gained)
    assert delivered > 0


def test_runs_in_loop_and_respects_unit_power(cfg):
    result, station = day_run(cfg)
    log = result.station
    assert list(log.columns) == STATION_COLUMNS
    unit_kw = {cid: u.power_kw for cid, u in station.units.items()}
    assert (log.power_kw <= log.charger_id.map(unit_kw) + 1e-9).all()
    assert (log.power_kw >= 0).all()


SESSION_COLUMNS = [
    "vehicle_id", "model", "battery_kwh", "arrival", "departure", "first_charger", "connected_at",
    "soc_arrival", "soc_final", "target_soc", "energy_kwh", "reached_target", "waited_h",
]


def eleven_with_one_almost_full(cfg, cfg_over=None):
    c = apply_overrides(cfg, cfg_over or {})
    t = start_of(c) + pd.Timedelta(hours=6)
    vehicles = [ev(0, t, soc=0.8 - 0.5 / 60)] + [ev(i, t) for i in range(1, 11)]   # ilki 0,5 kWh eksik
    return make_station(c, vehicles), vehicles, t


def step(s, ts, power=22.0, n=0):
    reqs = s.requests(ctx_at(ts, n))
    s.apply(ctx_at(ts, n), {r.charger_id: power for r in reqs})
    return reqs


def test_full_vehicle_frees_unit_for_queue(cfg):
    s, vs, t = eleven_with_one_almost_full(cfg)
    step(s, t)                                   # ilk araç bu adımda dolar
    unit = vs[0].first_charger
    step(s, t + pd.Timedelta(minutes=15), n=1)
    assert vs[0].charger_id is None
    assert s.units[unit].vehicle is vs[10]
    assert s.queue == []


def test_no_rotation_when_disabled(cfg):
    s, vs, t = eleven_with_one_almost_full(cfg, {"station.rotate_when_full": False})
    step(s, t)
    step(s, t + pd.Timedelta(minutes=15), n=1)
    assert vs[0].charger_id == vs[0].first_charger
    assert s.queue == [vs[10]]


def test_no_rotation_when_queue_empty(cfg):
    t = start_of(cfg) + pd.Timedelta(hours=6)
    a = ev(1, t, soc=0.8 - 0.5 / 60)
    s = make_station(cfg, [a])
    step(s, t)
    step(s, t + pd.Timedelta(minutes=15), n=1)
    assert a.charger_id == "AC1"


def test_almost_full_counts_as_reached(cfg):
    t = start_of(cfg) + pd.Timedelta(hours=6)
    vehicles = [ev(0, t, soc=0.8 - 1e-9)] + [ev(i, t) for i in range(1, 11)]
    s = make_station(cfg, vehicles)
    s.requests(ctx_at(t))                         # ilk adımda 10 bağlanır, 1 sırada
    s.requests(ctx_at(t + pd.Timedelta(minutes=15), 1))
    assert vehicles[0].charger_id is None and vehicles[10].charger_id is not None


def test_sessions_columns_and_rows(cfg):
    result, station = day_run(cfg)
    sess = station.sessions()
    assert list(sess.columns) == SESSION_COLUMNS
    assert len(sess) == cfg["vehicles"]["count"]
    assert sess.energy_kwh.sum() == pytest.approx(result.steps.ev_kw.sum() * DT)


def test_never_connected_vehicle_in_sessions(cfg):
    # Nöbetleşe şarj açıkken 40 aracın hepsi sırayla hizmet alıyor; hiç bağlanamayanı görmek için kapatıyoruz.
    c = apply_overrides(cfg, {"vehicles.count": 40, "station.rotate_when_full": False})
    _, station = day_run(c)
    sess = station.sessions()
    never = sess[sess.first_charger.isna()]
    assert len(sess) == 40 and len(never) > 0
    assert (never.energy_kwh == 0).all() and (~never.reached_target).all()
    assert list(never.waited_h) == pytest.approx(list((never.departure - never.arrival).dt.total_seconds() / 3600))


def test_rotation_serves_more_vehicles(cfg):
    c = apply_overrides(cfg, {"vehicles.count": 40})
    off = apply_overrides(c, {"station.rotate_when_full": False})
    served = lambda conf: day_run(conf)[1].sessions().connected_at.notna().sum()
    assert served(c) > served(off)


def test_default_day_serves_everyone(cfg):
    _, station = day_run(cfg)
    assert station.sessions().connected_at.notna().all()
