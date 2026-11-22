"""Senaryo tanımları ve tek gün çalıştırma (YM-4). Dashboard senaryo listesini buradan okur.

Bir senaryo; istasyon, EMS ve batarya modüllerini nasıl kuracağını ve config'te neyi değiştireceğini söyler.
YM-2 istasyonu geldikçe `station=` tek satırla değişir (S3 artık YM-3'ün RuleBasedEMS'iyle çalışıyor); dashboard kendiliğinden gösterir:

    Scenario("S3 akıllı şarj", ems=lambda cfg: RuleBasedEMS(cfg), station=lambda cfg, start: ChargingStation(cfg, start))

Not: YM-1'in duyarlılık analizi (ym1/hafta9-duyarlilik, analysis.py) aynı alanlara sahip bir Scenario kullanıyor.
O branch birleşince ikisi tek sınıfta toplanmalı (analysis.py bunu buradan import etsin).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from microgrid.ems.bess import BESS
from microgrid.ems.milp import MilpEMS
from microgrid.ems.rule_based import RuleBasedEMS
from microgrid.sim.loop import SimResult, run, time_index
from microgrid.sim.mocks import MockStation, UncontrolledEMS, V2GMockStation


@dataclass
class Scenario:
    name: str
    description: str = ""
    ems: Callable = lambda cfg: UncontrolledEMS()
    station: Callable = lambda cfg, start: MockStation(cfg, start)
    battery: Callable = lambda cfg: BESS(cfg)
    config: dict = field(default_factory=dict)   # {"vehicles.count": 0} gibi noktalı yol -> değer
    temporary: bool = False                      # gerçek modül gelene kadar sahte modülle çalışıyorsa True (şu an: MockStation)


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
        Scenario(
            "S3 Akıllı şarj",
            "Kural tabanlı EMS (YM-3): şarj ayrılışa kadar en ucuz tarife adımlarına eşit yayılır, SOC < 0.30 olan araç "
            "hemen taban SOC'ye çıkarılır, PV fazlası araçlara verilir, istasyon ve site sınırlarına uyulur. Batarya yok.",
            ems=lambda cfg: RuleBasedEMS(cfg),
            temporary=True,   # MockStation: CC-CV yok (YM-2 istasyonu bekleniyor)
        ),
        Scenario(
            "S4 Akıllı şarj + batarya",
            "S3'ün araç kuralı + 200 kWh / 100 kW batarya (YM-3): puantta yükü bataryadan karşılar, gece ucuz tarifede "
            "ve PV fazlasıyla dolar, site sınırını aşacak anda devreye girer.",
            ems=lambda cfg: RuleBasedEMS(cfg, use_bess=True),
            temporary=True,
        ),
        Scenario(
            "S5 Optimizasyon (MILP)",
            "Maliyeti en aza indiren kayan ufuklu MILP (YM-3, PuLP): her adımda bağlı araçlar, batarya, istasyon ve "
            "site sınırlarıyla gün sonuna kadar çözülür, ilk adım uygulanır. Tepe alımı küçük ağırlıkla bastırılır.",
            ems=lambda cfg: MilpEMS(cfg),
            temporary=True,
        ),
        Scenario(
            "S6 V2G (MILP)",
            "S5'e V2G eklenir (YM-3): araçların %40'ı şebekeye geri verebilir (11 kW). Araç SOC'si 0.30 altına inmez, "
            "ayrılışta hedef SOC garanti. Karşılaştırma tabanı: aynı istasyonda V2G kapalı (S5).",
            ems=lambda cfg: MilpEMS(cfg, v2g=True),
            station=lambda cfg, start: V2GMockStation(cfg, start),
            temporary=True,   # V2GMockStation: YM-2 istasyonu bekleniyor
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
