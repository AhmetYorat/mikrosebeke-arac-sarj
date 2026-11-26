"""sim/sonuclar.py: bütün senaryoların KPI tablosu ve rapor çıktıları (YM-4)."""
import pytest

from microgrid.config import load_config
from microgrid.sim.loop import time_index
from microgrid.sim.mocks import mock_inputs
from microgrid.sim.scenarios import SCENARIOS, simulate
from microgrid.sim.sonuclar import SHOWN, kpi_row, kpi_table, markdown_table


@pytest.fixture(scope="module")
def results():
    cfg = load_config()
    inputs = mock_inputs(cfg, time_index(cfg))
    return cfg, {n: simulate(cfg, s, inputs) for n, s in SCENARIOS.items()}


def test_kpi_row_has_station_and_v2g_metrics(results):
    cfg, res = results
    row = kpi_row(res["S2 Kontrolsüz şarj"], cfg)
    for key, _, _ in SHOWN:
        assert key in row.index, key
    assert row["arac_sayisi"] == cfg["vehicles"]["count"]
    assert row["v2g_veris_kwh"] == 0


def test_only_v2g_scenario_exports_from_vehicles(results):
    cfg, res = results
    table = kpi_table(res, cfg)
    v2g = table.loc["v2g_veris_kwh"]
    assert v2g["S6 V2G (MILP)"] > 0
    assert (v2g.drop("S6 V2G (MILP)") == 0).all()


def test_s1_has_no_vehicles(results):
    cfg, res = results
    row = kpi_row(res["S1 Temel (araç yok)"], cfg)
    assert row["arac_sayisi"] == 0 and row["arac_sarj_kwh"] == 0


def test_markdown_table_lists_every_scenario(results):
    cfg, res = results
    md = markdown_table(kpi_table(res, cfg))
    assert md.splitlines()[0].count("|") == len(SCENARIOS) + 2
    assert "Hedefe ulaşan araç" in md and "—" in md   # S1'de memnuniyet tanımsız


def test_solver_tolerance_is_not_counted_as_limit_violation(results):
    """MILP sınıra ~1e-7 kW aşarak oturabilir; KPI bunu aşım saymamalı (gerçek aşım S2'de var)."""
    cfg, res = results
    table = kpi_table(res, cfg)
    assert table.at["site_siniri_asim_adim", "S5 Optimizasyon (MILP)"] == 0
    assert table.at["istasyon_siniri_asim_adim", "S5 Optimizasyon (MILP)"] == 0
    assert table.at["site_siniri_asim_adim", "S2 Kontrolsüz şarj"] > 0
