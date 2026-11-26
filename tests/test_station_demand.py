"""YM-2: config'ten araç talep modeli."""
import pandas as pd
import pytest

from microgrid.config import load_config
from microgrid.sim.loop import time_index
from microgrid.sim.scenarios import apply_overrides
from microgrid.station.demand_model import DemandModel


@pytest.fixture
def cfg():
    return load_config()


def fleet(cfg, n=None, seed=0):
    c = apply_overrides(cfg, {"vehicles.count": n}) if n is not None else cfg
    return DemandModel(c, seed).generate_fleet(time_index(c)[0])


def test_fleet_size_and_ids(cfg):
    f = fleet(cfg)
    assert len(f) == cfg["vehicles"]["count"]
    assert sorted(v.vehicle_id for v in f) == [f"EV{i:02d}" for i in range(1, len(f) + 1)]
    arrivals = [v.arrival for v in f]
    assert arrivals == sorted(arrivals)


def test_times_inside_window(cfg):
    start = time_index(cfg)[0]
    end = start + pd.Timedelta(hours=cfg["simulation"]["horizon_hours"])
    for v in fleet(cfg, 2000):
        assert start <= v.arrival < start + pd.Timedelta(hours=12)
        assert v.arrival + pd.Timedelta(hours=1) <= v.departure <= end


def test_soc_ranges_and_target(cfg):
    for v in fleet(cfg, 500):
        assert 0.2 <= v.soc_arrival <= 0.6
        assert v.soc == v.soc_arrival
        assert v.target_soc == 0.8


def test_fleet_shares(cfg):
    f = fleet(cfg, 2000)
    counts = pd.Series([v.model_name for v in f]).value_counts(normalize=True)
    for m in cfg["vehicles"]["fleet"]:
        assert counts.get(m["model"], 0) == pytest.approx(m["share"], abs=0.03)


def test_without_fleet_key_uses_battery_kwh(cfg):
    c = apply_overrides(cfg, {})
    del c["vehicles"]["fleet"]
    f = DemandModel(c).generate_fleet(time_index(c)[0])
    assert all(v.battery_kwh == 60 and v.max_ac_kw == 22 and not v.v2g_capable for v in f)


def test_same_seed_same_fleet(cfg):
    a, b, c = fleet(cfg, seed=1), fleet(cfg, seed=1), fleet(cfg, seed=2)
    key = lambda f: [(v.model_name, v.arrival, v.soc_arrival) for v in f]
    assert key(a) == key(b)
    assert key(a) != key(c)


def test_zero_vehicles(cfg):
    assert fleet(cfg, 0) == []
