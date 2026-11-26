"""ems/bess.py: batarya modeli (YM-3, Hafta 3)."""
import pytest

from microgrid.config import load_config
from microgrid.ems.bess import BESS, BessParams

DT = 0.25


@pytest.fixture
def bess():
    return BESS(BessParams(capacity_kwh=200, power_kw=100, efficiency=0.95, soc_min=0.1, soc_max=0.9, soc_initial=0.5))


def test_charge_stores_energy_times_efficiency(bess):
    p = bess.apply(40, DT)
    assert p == 40
    assert bess.soc == pytest.approx(0.5 + 40 * DT * 0.95 / 200)


def test_discharge_draws_more_than_delivered(bess):
    p = bess.apply(-40, DT)
    assert p == -40
    assert bess.soc == pytest.approx(0.5 - 40 * DT / 0.95 / 200)


def test_power_limit_clips(bess):
    assert bess.apply(500, DT) == 100
    assert bess.apply(-500, DT) == -100


def test_soc_upper_bound_clips_charge(bess):
    for _ in range(40):
        bess.apply(100, DT)
    assert bess.soc == pytest.approx(0.9)
    assert bess.apply(50, DT) == pytest.approx(0.0)


def test_soc_lower_bound_clips_discharge(bess):
    for _ in range(40):
        bess.apply(-100, DT)
    assert bess.soc == pytest.approx(0.1)
    assert bess.apply(-50, DT) == pytest.approx(0.0)


def test_last_step_is_partial_not_overshoot(bess):
    """Üst sınıra 5 kWh kala 100 kW istenirse yalnızca sığacak kadarı uygulanır."""
    bess.soc = 0.9 - 5 / 200
    p = bess.apply(100, DT)
    assert p == pytest.approx(5 / (DT * 0.95))
    assert bess.soc == pytest.approx(0.9)


def test_zero_power_changes_nothing(bess):
    assert bess.apply(0, DT) == 0
    assert bess.soc == 0.5


def test_max_charge_discharge_match_apply(bess):
    bess.soc = 0.88
    assert bess.apply(1000, DT) == pytest.approx(BESS(BessParams(soc_initial=0.88)).max_charge_kw(DT))
    bess.soc = 0.12
    cap = bess.max_discharge_kw(DT)
    assert bess.apply(-1000, DT) == pytest.approx(-cap)


def test_energy_balance_and_losses(bess):
    """Şarj + deşarj sonrası: şebekeden çekilen - verilen = depodaki değişim + kayıp."""
    for p in [60, 60, -30, -80, 20, -10]:
        bess.apply(p, DT)
    delta_kwh = (bess.soc - 0.5) * 200
    assert bess.charged_kwh - bess.discharged_kwh == pytest.approx(delta_kwh + bess.losses_kwh)
    assert bess.losses_kwh > 0


def test_round_trip_efficiency(bess):
    """Aynı enerjiyi şarj edip deşarj etmek η² kadarını geri verir."""
    bess.apply(40, DT)
    stored = (bess.soc - 0.5) * 200
    bess.apply(-stored * 0.95 / DT, DT)   # depodaki enerjinin tamamını geri çek
    assert bess.soc == pytest.approx(0.5)
    assert bess.discharged_kwh == pytest.approx(40 * DT * 0.95**2, rel=1e-3)
    assert stored == pytest.approx(40 * DT * 0.95)


def test_equivalent_cycles(bess):
    bess.apply(80, 1.0)
    bess.apply(-80, 1.0)
    assert bess.equivalent_cycles == pytest.approx((80 + 80) / (2 * 160))


def test_from_config_matches_default_yaml():
    cfg = load_config()
    b = BESS(cfg)
    assert b.soc == cfg["bess"]["soc_initial"]
    assert b.p.capacity_kwh == cfg["bess"]["capacity_kwh"]


@pytest.mark.parametrize("kw", [
    {"capacity_kwh": 0}, {"efficiency": 1.2}, {"soc_min": 0.9, "soc_max": 0.1}, {"soc_initial": 0.95},
])
def test_invalid_params_rejected(kw):
    with pytest.raises(ValueError):
        BessParams(**kw)


def test_non_positive_dt_rejected(bess):
    with pytest.raises(ValueError):
        bess.apply(10, 0)
