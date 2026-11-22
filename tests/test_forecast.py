"""Hafta 7 (YM-1): ertesi gün PV/yük tahmini ve EMS'e tahmin verilmesi.

Yöntem testleri küçük matrislerle çalışır; diğerleri data/processed/ dosyaları yoksa atlanır.
"""
import copy

import numpy as np
import pandas as pd
import pytest

from microgrid.config import load_config
from microgrid.data import loads as load_profiles
from microgrid.data import pvgis
from microgrid.data.forecast import _climatology, _persistence, day_types, evaluate, forecast_inputs, hourly_forecast
from microgrid.data.inputs import INPUT_COLUMNS, build_inputs
from microgrid.sim.loop import run
from microgrid.sim.mocks import MockStation, SimpleBattery, UncontrolledEMS

TZ = "Europe/Istanbul"


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def data(cfg):
    if not (pvgis.processed_path(cfg).exists() and load_profiles.processed_path(cfg).exists()):
        pytest.skip("data/processed/ dosyaları yok (python -m microgrid.data)")


def test_persistence_and_climatology_use_only_past_days():
    days = np.arange(10, dtype=float).repeat(24).reshape(10, 24)   # gün d'nin her saati = d
    assert (_persistence(days)[5] == 4).all()
    assert (_persistence(days)[0] == 9).all()                      # yıl döngüsel: ilk günün dünü son gün
    assert (_climatology(days, 3)[5] == 3).all()                   # (4 + 3 + 2) / 3
    types = np.array([0, 1] * 5)                                   # aynı tipten: 3, 1 ve (döngüsel) 9
    assert (_climatology(days, 3, types)[5] == (3 + 1 + 9) / 3).all()


def test_day_types():
    days = pd.DatetimeIndex(["2023-10-27", "2023-10-28", "2023-10-29", "2023-10-30"])  # cuma, cmt, Cumhuriyet B. pazar, pzt
    assert list(day_types(days)) == [0, 1, 2, 0]
    assert day_types(pd.DatetimeIndex(["2023-05-01"]))[0] == 2    # pazartesi ama resmî tatil


def test_perfect_forecast_equals_actual_inputs(cfg, data):
    c = copy.deepcopy(cfg)
    c["inputs"]["mode"] = "actual"
    idx = pd.date_range(pd.Timestamp("2023-12-20 12:00", tz=TZ), periods=96, freq="15min")
    perfect = forecast_inputs(c, idx, hourly_forecast(c, "perfect", "perfect"))
    pd.testing.assert_frame_equal(perfect, build_inputs(c, idx))


def test_forecast_inputs_contract_and_realism(cfg, data):
    idx = pd.date_range(pd.Timestamp("2023-06-21 12:00", tz=TZ), periods=96, freq="15min")
    f = forecast_inputs(cfg, idx)
    assert list(f.columns) == INPUT_COLUMNS and f.index.equals(idx)
    assert not f.isna().any().any() and (f["pv_kw"] >= 0).all()
    # Tahmin gerçekten farklı ama aynı büyüklükte
    c = copy.deepcopy(cfg)
    c["inputs"]["mode"] = "actual"
    actual = build_inputs(c, idx)
    assert not np.allclose(f["pv_kw"], actual["pv_kw"])
    assert f["pv_kw"].sum() == pytest.approx(actual["pv_kw"].sum(), rel=0.5)


def test_chosen_methods_beat_persistence(cfg, data):
    e = evaluate(cfg)
    assert e.loc[("pv_kw", "blend"), "rmse_kw"] < e.loc[("pv_kw", "persistence"), "rmse_kw"]
    assert e.loc[("base_load_kw", "climatology"), "rmse_kw"] < e.loc[("base_load_kw", "persistence"), "rmse_kw"]


class RecordingEMS(UncontrolledEMS):
    def prepare(self, forecast):
        self.seen = forecast


def test_loop_passes_forecast_to_ems(cfg, data):
    c = copy.deepcopy(cfg)
    c["inputs"]["mode"] = "actual"
    idx = pd.date_range(pd.Timestamp("2023-06-21 12:00", tz=TZ), periods=96, freq="15min")
    inputs, forecast = build_inputs(c, idx), forecast_inputs(c, idx)
    ems = RecordingEMS()
    run(c, inputs, MockStation(c, idx[0]), ems, SimpleBattery(c), forecast=forecast)
    pd.testing.assert_frame_equal(ems.seen, forecast)
    ems = RecordingEMS()
    run(c, inputs, MockStation(c, idx[0]), ems, SimpleBattery(c))          # verilmezse gerçek girdi
    pd.testing.assert_frame_equal(ems.seen, inputs)
