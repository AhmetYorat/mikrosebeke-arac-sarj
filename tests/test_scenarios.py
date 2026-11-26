"""sim/scenarios.py: senaryo listesi, config değişiklikleri, tek gün çalıştırma (YM-4)."""
import pytest

from microgrid.config import load_config
from microgrid.sim.loop import time_index
from microgrid.sim.mocks import mock_inputs
from microgrid.sim.scenarios import SCENARIOS, apply_overrides, set_path, simulate


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def test_set_path_rejects_typos(cfg):
    with pytest.raises(KeyError):
        set_path(apply_overrides(cfg, {}), "vehicle.count", 5)   # doğrusu vehicles.count


def test_overrides_do_not_mutate(cfg):
    before = cfg["vehicles"]["count"]
    c = apply_overrides(cfg, {"vehicles.count": 3})
    assert c["vehicles"]["count"] == 3 and cfg["vehicles"]["count"] == before


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_every_scenario_runs_and_balances(cfg, name):
    index = time_index(cfg)
    s = simulate(cfg, SCENARIOS[name], mock_inputs(cfg, index)).steps
    assert len(s) == len(index)
    assert ((s.base_load_kw + s.ev_kw + s.bess_kw - s.pv_kw) - s.grid_kw).abs().max() < 1e-9


def test_s1_has_no_charging(cfg):
    index = time_index(cfg)
    s = simulate(cfg, SCENARIOS["S1 Temel (araç yok)"], mock_inputs(cfg, index)).steps
    assert s["ev_kw"].abs().max() == 0


def test_s2_charges_in_evening(cfg):
    index = time_index(cfg)
    s = simulate(cfg, SCENARIOS["S2 Kontrolsüz şarj"], mock_inputs(cfg, index)).steps
    assert s.loc[s.index.hour.isin([18, 19, 20]), "ev_kw"].max() > 0


def test_s3_moves_charging_out_of_puant_without_new_peak(cfg):
    """Kural tabanlı akıllı şarj (YM-3) + gerçek istasyon (YM-2): puanttaki araç şarjı azalır, maliyet ve tepe düşer, sınırlara uyulur."""
    from microgrid.kpi import compute

    index = time_index(cfg)
    inputs = mock_inputs(cfg, index)
    s2 = compute(simulate(cfg, SCENARIOS["S2 Kontrolsüz şarj"], inputs).steps, cfg)
    s3_steps = simulate(cfg, SCENARIOS["S3 Akıllı şarj"], inputs).steps
    s3 = compute(s3_steps, cfg)
    assert s3["arac_sarj_puant_payi"] < 0.1 < s2["arac_sarj_puant_payi"]
    assert s3["maliyet_tl"] < s2["maliyet_tl"]
    assert s3["tepe_alim_kw"] < s2["tepe_alim_kw"]
    # sınırlara uyuyor
    assert (s3_steps["ev_kw"] <= cfg["station"]["power_limit_kw"] + 1e-6).all()
    assert (s3_steps["grid_kw"] <= cfg["grid"]["site_import_limit_kw"] + 1e-6).all()


@pytest.mark.xfail(strict=True, reason=(
    "YM-4 entegrasyon notu (YM-3'e): gerçek istasyonda 20 araç / 10 ünite var. RuleBasedEMS şarjı ayrılışa kadarki "
    "ucuz adımlara yaydığı için bağlı araçlar sabaha kadar dolmuyor, nöbetleşe şarj tetiklenmiyor ve sıradaki "
    "araçların bir kısmı hedefe ulaşamıyor (verim düzeltmesinden sonra S3 486 kWh, S2 590 kWh; hedefe ulaşma 16/20). "
    "İstasyon doğru davranıyor; EMS ünite sırasını hesaba katmalı. Düzelince bu xfail kaldırılmalı."))
def test_s3_delivers_same_energy_as_s2(cfg):
    from microgrid.kpi import compute

    inputs = mock_inputs(cfg, time_index(cfg))
    s2 = compute(simulate(cfg, SCENARIOS["S2 Kontrolsüz şarj"], inputs).steps, cfg)
    s3 = compute(simulate(cfg, SCENARIOS["S3 Akıllı şarj"], inputs).steps, cfg)
    assert abs(s3["arac_sarj_kwh"] - s2["arac_sarj_kwh"]) < 1e-6


def test_s3_does_not_leave_efficiency_tail(cfg):
    """EMS istediği gücü istasyon verimine göre hesaplamalı; yoksa araca her adım ihtiyacın %5'i kalır."""
    log = simulate(cfg, SCENARIOS["S3 Akıllı şarj"], mock_inputs(cfg, time_index(cfg))).station
    assert ((log.power_kw > 0) & (log.power_kw < 0.05)).sum() == 0


# --- YM-2: gerçek istasyon döngüde ------------------------------------------------------------------------------
S2 = "S2 Kontrolsüz şarj"


def test_default_station_is_real(cfg):
    from microgrid.station import ChargingStation
    assert isinstance(SCENARIOS[S2].station(cfg, time_index(cfg)[0]), ChargingStation)


def test_s2_not_temporary():
    assert SCENARIOS[S2].temporary is False


def test_s2_has_sessions(cfg):
    r = simulate(cfg, SCENARIOS[S2], mock_inputs(cfg, time_index(cfg)))
    assert len(r.sessions) == cfg["vehicles"]["count"]


def test_s1_sessions_empty(cfg):
    r = simulate(cfg, SCENARIOS["S1 Temel (araç yok)"], mock_inputs(cfg, time_index(cfg)))
    assert r.sessions.empty and (r.steps.ev_kw == 0).all()
