"""Senaryo tanımları ve tek gün çalıştırma (YM-4). Dashboard senaryo listesini buradan okur.

Bir senaryo; istasyon, EMS ve batarya modüllerini nasıl kuracağını ve config'te neyi değiştireceğini söyler.
Varsayılan istasyon YM-2'nin gerçek istasyonudur (ChargingStation: CC-CV, araç kataloğu, sıra ve nöbetleşe şarj).
YM-3 modülleri geldikçe senaryo listesine tek satır eklenir; dashboard kendiliğinden gösterir:

    Scenario("S3 akıllı şarj", ems=lambda cfg: RuleBasedEMS(cfg))

Not: YM-1'in duyarlılık analizi (ym1/hafta9-duyarlilik, analysis.py) aynı alanlara sahip bir Scenario kullanıyor.
O branch birleşince ikisi tek sınıfta toplanmalı (analysis.py bunu buradan import etsin).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from microgrid.sim.loop import SimResult, run, time_index
from microgrid.sim.mocks import CheapHoursEMS, SimpleBattery, UncontrolledEMS
from microgrid.station import ChargingStation


@dataclass
class Scenario:
    name: str
    description: str = ""
    ems: Callable = lambda cfg: UncontrolledEMS()
    station: Callable = lambda cfg, start: ChargingStation(cfg, start)
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
        ),
        Scenario(
            "S3 Akıllı şarj (geçici)",
            "Gece tarifesine kaydırma + PV fazlası + sınırlara uyum. GEÇİCİ: YM-4'ün referans kuralı; "
            "YM-3'ün kural tabanlı EMS'i gelince onunla değiştirilecek.",
            ems=lambda cfg: CheapHoursEMS(cfg),
            temporary=True,
        ),
    ]
}


def simulate(cfg: dict, scenario: Scenario, inputs: pd.DataFrame, grid=None) -> SimResult:
    """Senaryoyu tek temsili günde çalıştırır. cfg'ye senaryonun değişiklikleri burada uygulanır."""
    c = apply_overrides(cfg, scenario.config)
    index = time_index(c)
    if not inputs.index.equals(index):
        raise ValueError("inputs indeksi senaryonun zaman ekseniyle aynı olmalı (time_index(cfg))")
    station = scenario.station(c, index[0])
    result = run(c, inputs, station, scenario.ems(c), scenario.battery(c), grid)
    if hasattr(station, "sessions"):
        result.sessions = station.sessions()
    return result
