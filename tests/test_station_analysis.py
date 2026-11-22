"""YM-2 Hafta 5: araç sayısına göre tepe yük ve istasyonun kritik anı."""
import pytest

from microgrid.config import load_config
from microgrid.sim.loop import time_index
from microgrid.sim.mocks import mock_inputs
from microgrid.sim.scenarios import SCENARIOS, simulate
from microgrid.station.analysis import critical_station_snapshot, peak_vs_vehicle_count

COLUMNS = ["arac_sayisi", "istasyon_tepe_kw", "istasyon_tepe_saati", "sebeke_tepe_kw",
           "site_siniri_asim_adim", "hedefe_ulasma_orani"]


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def inputs(cfg):
    return mock_inputs(cfg, time_index(cfg))


def test_zero_vehicles_zero_peak(cfg, inputs):
    t = peak_vs_vehicle_count(cfg, inputs, [0])
    assert list(t.columns) == COLUMNS
    assert t.istasyon_tepe_kw.iloc[0] == 0


def test_more_vehicles_higher_peak(cfg, inputs):
    t = peak_vs_vehicle_count(cfg, inputs, [5, 20]).set_index("arac_sayisi")
    assert t.istasyon_tepe_kw[20] > t.istasyon_tepe_kw[5]


def test_many_vehicles_do_not_crash(cfg, inputs):
    t = peak_vs_vehicle_count(cfg, inputs, [40])
    assert len(t) == 1 and 0 <= t.hedefe_ulasma_orani.iloc[0] <= 1


def test_snapshot_matches_steps(cfg, inputs):
    r = simulate(cfg, SCENARIOS["S2 Kontrolsüz şarj"], inputs)
    snap = critical_station_snapshot(r, cfg)
    assert snap["istasyon_kw"] == pytest.approx(round(r.steps.ev_kw.max(), 1))
    assert snap["sarj_olan_ac"] + snap["sarj_olan_dc"] <= snap["bagli_arac"]
    assert snap["sarj_olan_ac"] > 0 and 0 < snap["ortalama_soc"] < 1


def test_md_table():
    import pandas as pd
    from microgrid.station.analysis import md_table
    assert md_table(pd.DataFrame({"a": [1], "b": [0.5]})) == "| a | b |\n| --- | --- |\n| 1 | 0.50 |"
