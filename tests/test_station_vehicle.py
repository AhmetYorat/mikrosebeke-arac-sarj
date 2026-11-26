"""YM-2: araç modeli ve CC-CV eğrisi."""
import pandas as pd
import pytest

from microgrid.station.vehicle import SOC_TOL, ElectricVehicle, cc_cv_limit

T0 = pd.Timestamp("2023-06-21 18:00", tz="Europe/Istanbul")


def make_ev(**kw):
    base = dict(
        vehicle_id="EV01", model_name="Test", battery_kwh=60.0, soc_arrival=0.3, target_soc=0.8,
        arrival=T0, departure=T0 + pd.Timedelta(hours=13), max_ac_kw=22.0, max_dc_kw=50.0, v2g_capable=False,
    )
    base.update(kw)
    return ElectricVehicle(**base)


def test_cc_cv_full_power_below_threshold():
    assert cc_cv_limit(0.5, 22, 0.8, 0.15) == 22


def test_cc_cv_tapers_linearly():
    assert cc_cv_limit(0.9, 22, 0.8, 0.15) == pytest.approx(11.0)


def test_cc_cv_floor():
    assert cc_cv_limit(0.99, 22, 0.8, 0.15) == pytest.approx(3.3)


def test_obc_limits_ac_unit():
    ev = make_ev(max_ac_kw=11.0, target_soc=1.0)
    assert ev.max_charge_kw("AC", 22.0, 0.8, 0.15) == 11.0


def test_dc_uses_vehicle_dc_limit():
    ev = make_ev(max_dc_kw=170.0, target_soc=1.0)
    assert ev.max_charge_kw("DC", 50.0, 0.8, 0.15) == 50.0


def test_full_vehicle_requests_nothing():
    ev = make_ev(soc_arrival=0.8 - 1e-9)
    assert ev.reached_target
    assert ev.max_charge_kw("AC", 22.0, 0.8, 0.15) == 0.0
    assert SOC_TOL == 1e-6


def test_charge_updates_soc_with_efficiency():
    ev = make_ev()
    applied = ev.charge(22.0, 0.25, 0.95)
    assert applied == 22.0
    assert ev.soc == pytest.approx(0.3 + 22 * 0.25 * 0.95 / 60)
    assert ev.energy_in_kwh == pytest.approx(5.5)
    assert ev.energy_needed_kwh == pytest.approx((0.8 - ev.soc) * 60)


def test_reached_target_tolerates_tiny_undershoot_in_energy():
    # Hedefe 1,5e-6 SOC (0,09 Wh) kala araç dolu sayılmalı; yoksa üniteyi bütün gece tutar (final review #1).
    assert make_ev(soc_arrival=0.8 - 1.5e-6).reached_target
    assert make_ev(soc_arrival=0.8 - 0.009 / 60).reached_target          # 9 Wh eksik
    assert not make_ev(soc_arrival=0.8 - 0.02 / 60).reached_target       # 20 Wh eksik
