"""Senaryo karşılaştırması ve duyarlılık analizi (YM-1, Hafta 8–9).

Her senaryo yılın temsili günlerinde (data/seasons.py) çalıştırılır, KPI'lar yıla genişletilir (kpi.annualize).
Bir senaryo; istasyon, EMS ve batarya modüllerini nasıl kuracağını ve config'te neyi değiştireceğini söyler.
YM-2/YM-3 modülleri geldikçe Senaryo 3–6 aynı tabloya tek satırla eklenir:

    Scenario("S3 akıllı şarj", ems=lambda cfg: RuleBasedEMS(cfg), station=ChargingStation)

Duyarlılık: sweep(cfg, senaryo, "pv.installed_kw", [0, 50, 100, 150]) her değer için yıllık KPI satırı verir.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from microgrid.config import load_config
from microgrid.data import seasons
from microgrid.kpi import KPI_UNITS, annualize
from microgrid.sim.loop import run
from microgrid.sim.mocks import MockStation, SimpleBattery, UncontrolledEMS


@dataclass
class Scenario:
    name: str
    ems: Callable = lambda cfg: UncontrolledEMS()
    station: Callable = lambda cfg, start: MockStation(cfg, start)
    battery: Callable = lambda cfg: SimpleBattery(cfg)
    config: dict = field(default_factory=dict)   # {"vehicles.count": 0} gibi config değişiklikleri


def set_path(cfg: dict, path: str, value) -> None:
    """'pv.installed_kw' gibi noktalı yolu config'te değiştirir."""
    *parents, leaf = path.split(".")
    node = cfg
    for p in parents:
        node = node[p]
    if leaf not in node:
        raise KeyError(f"config'te '{path}' yok")
    node[leaf] = value


def scenario_cfg(cfg: dict, scenario: Scenario, overrides: dict | None = None) -> dict:
    c = copy.deepcopy(cfg)
    for path, value in {**scenario.config, **(overrides or {})}.items():
        set_path(c, path, value)
    return c


def run_day(cfg: dict, scenario: Scenario, inputs: pd.DataFrame, grid=None, warmup: int = 2) -> pd.DataFrame:
    """Bir temsili günü çalıştırır. Batarya döngüsel: gün, bir önceki çalıştırmanın bittiği SOC ile başlar.

    Neden: batarya her temsili günde config'teki başlangıç SOC'siyle başlasaydı, gün içinde boşalttığı enerji
    her gün bedavaya geri gelirdi ve tasarruf olduğundan büyük çıkardı. Gün warmup kez tekrarlanır; son çalıştırma
    yaklaşık olarak aynı SOC'de başlayıp biter (gerçekte günler art arda gelir).
    """
    soc = None
    for _ in range(warmup + 1):
        battery = scenario.battery(cfg)
        if soc is not None:
            battery.soc = soc
        steps = run(cfg, inputs, scenario.station(cfg, inputs.index[0]), scenario.ems(cfg), battery,
                    grid if _ == warmup else None).steps
        soc = battery.soc
    return steps


def run_year(cfg: dict, scenario: Scenario, grid=None) -> tuple[pd.Series, dict]:
    """Senaryoyu temsili günlerde çalıştırır; (yıllık KPI, {temsili gün: adım tablosu}) döndürür."""
    days = seasons.day_table(cfg)
    profs = seasons.profiles(cfg)
    weights = seasons.calendar(cfg, days)
    results = {
        key: run_day(cfg, scenario, seasons.representative_inputs(cfg, key, profs, days), grid)
        for key in weights.index
    }
    return annualize(results, weights.to_dict(), cfg), results


def scenario_table(scenarios: list[Scenario], cfg=None, grid=None) -> pd.DataFrame:
    """Senaryoların yıllık KPI tablosu: satırlar KPI, sütunlar senaryo, son sütun birim."""
    cfg = cfg or load_config()
    table = pd.DataFrame({s.name: run_year(scenario_cfg(cfg, s), s, grid)[0] for s in scenarios})
    table["birim"] = pd.Series(KPI_UNITS)
    return table


def sweep(cfg: dict, scenario: Scenario, path: str, values, grid=None) -> pd.DataFrame:
    """Bir parametrenin değerlerine göre yıllık KPI'lar: satırlar değer, sütunlar KPI."""
    rows = {v: run_year(scenario_cfg(cfg, scenario, {path: v}), scenario, grid)[0] for v in values}
    out = pd.DataFrame(rows).T
    out.index.name = path
    return out
