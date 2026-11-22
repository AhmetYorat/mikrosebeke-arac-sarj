"""YM-2 Hafta 8: V2G — deşarj kuralı, minimum SOC ve ayrılışta hedef SOC garantisi."""
import pandas as pd
import pytest

from microgrid.config import load_config
from microgrid.interfaces import Decision, StepContext
from microgrid.sim.loop import run, time_index
from microgrid.sim.mocks import SimpleBattery, mock_inputs
from microgrid.sim.scenarios import apply_overrides
from microgrid.station import ChargingStation, ElectricVehicle, satisfaction

DT = 0.25
ETA = 0.95


@pytest.fixture
def cfg():
    return apply_overrides(load_config(), {"station.v2g_enabled": True})


def ev(arrival, hours=13, soc=0.6, target=0.8, v2g=True, max_ac=11.0):
    return ElectricVehicle(vehicle_id="V1", model_name="Test", battery_kwh=60.0, soc_arrival=soc, target_soc=target,
                           arrival=arrival, departure=arrival + pd.Timedelta(hours=hours), max_ac_kw=max_ac,
                           max_dc_kw=50.0, v2g_capable=v2g)


def one(cfg, v):
    s = ChargingStation(cfg, time_index(cfg)[0])
    s.vehicles = [v]
    ctx = StepContext(0, v.arrival, DT)
    return s, ctx, s.requests(ctx)


def t0(cfg):
    return time_index(cfg)[0] + pd.Timedelta(hours=6)


def test_v2g_off_by_default():
    c = load_config()
    _, _, reqs = one(c, ev(t0(c)))
    assert reqs[0].max_discharge_kw == 0


def test_non_capable_vehicle_never_discharges(cfg):
    s, ctx, reqs = one(cfg, ev(t0(cfg), v2g=False))
    assert reqs[0].max_discharge_kw == 0
    assert s.apply(ctx, {"AC1": -10.0})["AC1"] == 0


def test_discharge_limited_by_unit_and_floor(cfg):
    _, _, reqs = one(cfg, ev(t0(cfg), soc=0.6))
    assert reqs[0].max_discharge_kw == pytest.approx(11.0)        # OBC = AC ünitede deşarj sınırı
    _, _, reqs = one(cfg, ev(t0(cfg), soc=0.31))
    assert reqs[0].max_discharge_kw == pytest.approx(0.01 * 60 * ETA / DT)


def test_no_discharge_near_departure(cfg):
    _, _, reqs = one(cfg, ev(t0(cfg), hours=0.25, soc=0.79))
    assert reqs[0].max_discharge_kw == 0


def test_full_vehicle_still_offered_for_v2g(cfg):
    _, _, reqs = one(cfg, ev(t0(cfg), soc=0.8))
    assert len(reqs) == 1 and reqs[0].max_discharge_kw > 0


class GreedyV2G:
    """17–22 arası istasyonun izin verdiği en fazla deşarjı, diğer saatlerde en fazla şarjı ister."""

    def prepare(self, forecast):
        pass

    def decide(self, inp):
        evening = 17 <= inp.ctx.hour < 22
        return Decision(ev_kw={v.charger_id: (-1000.0 if evening else v.max_charge_kw) for v in inp.vehicles})


def day(cfg, n=10):
    c = apply_overrides(cfg, {"vehicles.count": n})
    index = time_index(c)
    s = ChargingStation(c, index[0])
    return run(c, mock_inputs(c, index), s, GreedyV2G(), SimpleBattery(c)), s


def test_soc_never_below_min(cfg):
    # Araç 0,3'ün altında gelebilir (geliş SOC'si 0,2–0,6); garanti, V2G'nin onu 0,3'ün altına itmemesi.
    result, s = day(cfg)
    battery = {v.vehicle_id: v.battery_kwh for v in s.vehicles}
    dis = result.station[result.station.power_kw < 0]
    assert len(dis) > 0
    soc_after = dis.soc + dis.power_kw * DT / (ETA * dis.vehicle_id.map(battery))
    assert (soc_after >= cfg["vehicles"]["v2g_min_soc"] - 1e-9).all()


def test_target_still_reached_after_v2g(cfg):
    _, s = day(cfg)
    assert sum(v.energy_out_kwh for v in s.vehicles) > 0
    assert satisfaction(s.sessions())["hedefe_ulasma_orani"] == 1


def test_energy_conservation_with_v2g(cfg):
    _, s = day(cfg)
    lhs = sum(v.energy_in_kwh * ETA - v.energy_out_kwh / ETA for v in s.vehicles)
    rhs = sum((v.soc - v.soc_arrival) * v.battery_kwh for v in s.vehicles)
    assert lhs == pytest.approx(rhs)


def test_planned_sessions_report_discharge(cfg):
    plan = ChargingStation(cfg, time_index(cfg)[0]).planned_sessions()
    assert (plan.max_discharge_kw > 0).any() and (plan.max_discharge_kw == 0).any()
