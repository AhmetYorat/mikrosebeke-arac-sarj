"""Senaryo tanımları ve tek gün çalıştırma (YM-4). Dashboard senaryo listesini buradan okur.

Bir senaryo; istasyon, EMS ve batarya modüllerini nasıl kuracağını ve config'te neyi değiştireceğini söyler.
YM-2/YM-3 modülleri geldikçe senaryo listesine tek satır eklenir; dashboard kendiliğinden gösterir:

    Scenario("S3 akıllı şarj", ems=lambda cfg: RuleBasedEMS(cfg), station=lambda cfg, start: ChargingStation(cfg, start))

Not: YM-1'in duyarlılık analizi (ym1/hafta9-duyarlilik, analysis.py) aynı alanlara sahip bir Scenario kullanıyor.
O branch birleşince ikisi tek sınıfta toplanmalı (analysis.py bunu buradan import etsin).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from microgrid.sim.loop import SimResult, run, time_index
from microgrid.sim.mocks import MockStation, SimpleBattery, UncontrolledEMS


@dataclass
class Scenario:
    name: str
    description: str = ""
    ems: Callable = lambda cfg: UncontrolledEMS()
    station: Callable = lambda cfg, start: MockStation(cfg, start)
    battery: Callable = lambda cfg: SimpleBattery(cfg)
    config: dict = field(default_factory=dict)   # {"vehicles.count": 0} gibi noktalı yol -> değer
    temporary: bool = False                      # gerçek modül gelene kadar sahte modülle çalışıyorsa True


def set_path(cfg: dict, path: str, value) -> None:
    """'pv.installed_kw' gibi noktalı yolu config'te değiştirir. Yanlış yazılmış yol sessizce eklenmesin diye hata verir."""
    *parents, leaf = path.split(".")
    node = cfg
    for p in parents:
        node = node[p]
    if leaf not in node:
        raise KeyError(f"config'te '{path}' yok")
    node[leaf] = value


def apply_overrides(cfg: dict, overrides: dict) -> dict:
    """Değişiklikler uygulanmış config kopyası; orijinal config değişmez."""
    c = copy.deepcopy(cfg)
    for path, value in overrides.items():
        set_path(c, path, value)
    return c


SCENARIOS: dict[str, Scenario] = {
    s.name: s for s in [
        Scenario(
            "S1 Temel (araç yok)",
            "Karşılaştırma tabanı: istasyon boş, yalnızca PV + sabit yük + şebeke.",
            config={"vehicles.count": 0},
        ),
        Scenario(
            "S2 Kontrolsüz şarj",
            "Araç geldiği an tam güçle şarj olur, batarya kullanılmaz. Sorunun görüldüğü senaryo.",
            temporary=True,   # MockStation: CC-CV yok (YM-2 istasyonu bekleniyor)
        ),
    ]
}


def simulate(cfg: dict, scenario: Scenario, inputs: pd.DataFrame, grid=None) -> SimResult:
    """Senaryoyu tek temsili günde çalıştırır. cfg'ye senaryonun değişiklikleri burada uygulanır."""
    c = apply_overrides(cfg, scenario.config)
    index = time_index(c)
    if not inputs.index.equals(index):
        raise ValueError("inputs indeksi senaryonun zaman ekseniyle aynı olmalı (time_index(cfg))")
    return run(c, inputs, scenario.station(c, index[0]), scenario.ems(c), scenario.battery(c), grid)
