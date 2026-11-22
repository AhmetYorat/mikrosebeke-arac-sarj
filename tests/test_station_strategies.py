"""YM-2 Hafta 6: güç dağıtım yardımcıları ve kullanıcı memnuniyeti KPI'ı."""
import math

import numpy as np
import pandas as pd
import pytest

from microgrid.interfaces import VehicleRequest
from microgrid.station.strategies import by_departure, satisfaction, uncontrolled

T = pd.Timestamp("2023-06-22 07:00", tz="Europe/Istanbul")
DT = 0.25


def req(cid, dep_h=0.0, soc=0.3, max_kw=22.0, battery=60.0):
    return VehicleRequest(charger_id=cid, vehicle_id=cid, soc=soc, battery_kwh=battery, target_soc=0.8,
                          departure=T + pd.Timedelta(hours=dep_h), max_charge_kw=max_kw)


def test_uncontrolled_gives_full_power():
    out = uncontrolled([req("AC1"), req("AC2", max_kw=11.0), req("AC3", soc=0.8 - 1 / 60)], DT)
    assert out == {"AC1": 22.0, "AC2": 11.0, "AC3": pytest.approx(4.0)}


def test_by_departure_prioritizes_earliest():
    out = by_departure([req("AC1", dep_h=2), req("AC2", dep_h=1)], 22.0, DT)
    assert out == {"AC1": 0.0, "AC2": 22.0}


def test_by_departure_tie_prefers_bigger_need():
    out = by_departure([req("AC1", soc=0.7), req("AC2", soc=0.3)], 22.0, DT)
    assert out == {"AC1": 0.0, "AC2": 22.0}


def test_by_departure_never_exceeds_budget():
    rng = np.random.default_rng(3)
    vs = [req(f"AC{i}", dep_h=float(rng.uniform(0, 5)), soc=float(rng.uniform(0.2, 0.8)), max_kw=float(rng.choice([11, 22])))
          for i in range(10)]
    out = by_departure(vs, 70.0, DT)
    assert sum(out.values()) <= 70.0 + 1e-9
    assert all(out[v.charger_id] <= v.max_charge_kw + 1e-9 for v in vs)


def test_by_departure_large_budget_equals_uncontrolled():
    vs = [req("AC1", dep_h=1), req("AC2", dep_h=2, max_kw=11.0), req("AC3", soc=0.79)]
    assert by_departure(vs, 1000.0, DT) == pytest.approx(uncontrolled(vs, DT))


def test_by_departure_zero_budget():
    vs = [req("AC1"), req("AC2")]
    assert by_departure(vs, 0.0, DT) == {"AC1": 0.0, "AC2": 0.0}
    assert by_departure(vs, -5.0, DT) == {"AC1": 0.0, "AC2": 0.0}


def sessions_table():
    a = T - pd.Timedelta(hours=12)
    return pd.DataFrame({
        "vehicle_id": ["A", "B", "C", "D"], "battery_kwh": [60.0, 50.0, 60.0, 40.0],
        "arrival": [a] * 4, "departure": [T] * 4,
        "first_charger": ["AC1", "AC2", None, "DC1"],
        "connected_at": [a, a + pd.Timedelta(hours=1), pd.NaT, a + pd.Timedelta(hours=3)],
        "soc_final": [0.8, 0.7, 0.3, 0.8], "target_soc": [0.8, 0.8, 0.8, 0.8],
        "reached_target": [True, False, False, True],
        "waited_h": [0.0, 1.0, 12.0, 3.0],
    })


def test_satisfaction_known_values():
    k = satisfaction(sessions_table())
    assert k["arac_sayisi"] == 4
    assert k["hedefe_ulasma_orani"] == 0.5
    assert k["hizmet_alamayan"] == 1
    assert k["ortalama_eksik_kwh"] == pytest.approx((0 + 5 + 30 + 0) / 4)
    assert k["ortalama_bekleme_saat"] == pytest.approx(4.0)


def test_satisfaction_empty():
    k = satisfaction(sessions_table().iloc[0:0])
    assert k["arac_sayisi"] == 0 and k["hizmet_alamayan"] == 0
    assert math.isnan(k["hedefe_ulasma_orani"])
