"""ems/pv_first.py: EMS v0, önce PV sonra şebeke (YM-3, Hafta 4)."""
import pandas as pd
import pytest

from microgrid.config import load_config
from microgrid.ems.bess import BESS
from microgrid.ems.pv_first import PvFirstEMS
from microgrid.interfaces import EmsInputs, StepContext, VehicleRequest
from microgrid.sim.loop import run, time_index
from microgrid.sim.mocks import MockStation, UncontrolledEMS, mock_inputs


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def _inp(pv=0.0, base=30.0, vehicles=(), soc=0.5):
    ts = pd.Timestamp("2023-06-21 19:00", tz="Europe/Istanbul")
    return EmsInputs(
        ctx=StepContext(step=28, timestamp=ts, dt_h=0.25), pv_kw=pv, base_load_kw=base, price_tl_per_kwh=6.0,
        vehicles=list(vehicles), bess_soc=soc, station_limit_kw=150, site_limit_kw=180,
    )


def _veh(cid="AC1", soc=0.3, max_kw=22.0):
    return VehicleRequest(cid, "EV01", soc, 60.0, 0.8, pd.Timestamp("2023-06-22 07:30", tz="Europe/Istanbul"), max_kw)


def test_vehicle_charges_at_full_power_on_arrival():
    d = PvFirstEMS().decide(_inp(vehicles=[_veh()]))
    assert d.ev_kw == {"AC1": 22.0}
    assert d.bess_kw == 0.0


def test_vehicle_power_capped_by_remaining_energy():
    v = _veh(soc=0.79)    # 0.6 kWh kaldı: 0.25 saatte 2.4 kW yeter
    d = PvFirstEMS().decide(_inp(vehicles=[v]))
    assert d.ev_kw["AC1"] == pytest.approx(0.01 * 60 / 0.25)


def test_does_not_enforce_limits_on_purpose():
    """Kontrolsüz şarj istasyon sınırını aşabilmeli: Senaryo 2 aşımı göstermek için var."""
    vs = [_veh(f"AC{i}") for i in range(1, 9)] + [_veh("DC1", max_kw=50), _veh("DC2", max_kw=50)]
    d = PvFirstEMS().decide(_inp(vehicles=vs))
    assert sum(d.ev_kw.values()) > 150


def test_without_bess_never_uses_battery():
    assert PvFirstEMS().decide(_inp(pv=90, base=20)).bess_kw == 0.0
    assert PvFirstEMS().decide(_inp(pv=0, base=80)).bess_kw == 0.0


def test_pv_surplus_charges_battery():
    d = PvFirstEMS(bess_power_kw=100).decide(_inp(pv=90, base=30))
    assert d.bess_kw == pytest.approx(60)


def test_deficit_discharges_battery_after_pv():
    d = PvFirstEMS(bess_power_kw=100).decide(_inp(pv=10, base=30, vehicles=[_veh()]))
    assert d.bess_kw == pytest.approx(-(30 + 22 - 10))


def test_battery_request_limited_by_inverter_power():
    assert PvFirstEMS(bess_power_kw=40).decide(_inp(pv=200, base=30)).bess_kw == 40
    assert PvFirstEMS(bess_power_kw=40).decide(_inp(pv=0, base=300)).bess_kw == -40


def test_prepare_is_noop():
    PvFirstEMS().prepare(None)


def test_matches_mock_uncontrolled_in_full_loop(cfg):
    """Bataryasız v0, YM-4'ün kontrolsüz şarj referansıyla (S2) adım adım aynı sonucu vermeli."""
    index = time_index(cfg)
    inputs = mock_inputs(cfg, index)
    ref = run(cfg, inputs, MockStation(cfg, index[0]), UncontrolledEMS(), BESS(cfg)).steps
    v0 = run(cfg, inputs, MockStation(cfg, index[0]), PvFirstEMS.from_config(cfg), BESS(cfg)).steps
    pd.testing.assert_frame_equal(ref[["ev_kw", "bess_kw", "grid_kw"]], v0[["ev_kw", "bess_kw", "grid_kw"]])


def test_full_loop_with_battery_balances_and_reduces_import(cfg):
    index = time_index(cfg)
    inputs = mock_inputs(cfg, index)
    base = run(cfg, inputs, MockStation(cfg, index[0]), PvFirstEMS.from_config(cfg), BESS(cfg)).steps
    with_b = run(cfg, inputs, MockStation(cfg, index[0]), PvFirstEMS.from_config(cfg, use_bess=True), BESS(cfg)).steps
    assert ((with_b.base_load_kw + with_b.ev_kw + with_b.bess_kw - with_b.pv_kw) - with_b.grid_kw).abs().max() < 1e-9
    assert with_b.bess_kw.abs().max() > 0
    assert with_b.bess_soc.between(cfg["bess"]["soc_min"] - 1e-9, cfg["bess"]["soc_max"] + 1e-9).all()
    # PV fazlası şebekeye boşa gitmek yerine bataryaya girer: şebekeye veriş azalır
    assert (-with_b.grid_kw).clip(lower=0).sum() < (-base.grid_kw).clip(lower=0).sum()
