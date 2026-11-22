"""Elektrikli araç modeli (YM-2): durum takibi ve şarj fiziği (CC-CV).

Güçler şebeke tarafıdır (kW). Bataryaya giren enerji: güç × süre × verim.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# SOC karşılaştırmalarında tek tolerans: 0.7999999 hedefi 0.8 sayılır (kayan nokta hatası).
SOC_TOL = 1e-6


def cc_cv_limit(soc: float, p_nom_kw: float, threshold: float, min_fraction: float) -> float:
    """CC-CV şarj eğrisi: eşiğin altında anma gücü (sabit akım), üstünde doğrusal azalan güç (sabit gerilim).

    SOC = eşik iken anma gücü, SOC = 1 iken 0'a iner; ama hiçbir zaman anma gücünün min_fraction'ının altına inmez.
    Örnek (eşik 0.8, taban 0.15): SOC 0.9 -> %50, SOC 0.99 -> %15.
    """
    if soc < threshold:
        return p_nom_kw
    return p_nom_kw * max(min_fraction, (1.0 - soc) / (1.0 - threshold))


@dataclass
class ElectricVehicle:
    """Otoparka gelen bir araç. Kimlik ve donanım bilgisi + simülasyon boyunca değişen durum."""

    vehicle_id: str
    model_name: str
    battery_kwh: float
    soc_arrival: float          # geliş anındaki SOC
    target_soc: float           # sürücünün ayrılırken istediği SOC
    arrival: pd.Timestamp
    departure: pd.Timestamp
    max_ac_kw: float            # yerleşik şarj cihazı (OBC) sınırı; 22 kW AC ünitede 11 kW'lık araç 11 kW çeker
    max_dc_kw: float
    v2g_capable: bool = False

    # Durum (simülasyon sırasında değişir)
    charger_id: str | None = None   # bağlı olduğu ünite; bağlı değilse None
    ever_connected: bool = False
    connected_at: pd.Timestamp | None = None
    first_charger: str | None = None
    energy_in_kwh: float = 0.0      # şebekeden çekilen (şebeke tarafı)
    energy_out_kwh: float = 0.0     # V2G ile şebekeye verilen (şebeke tarafı)

    def __post_init__(self):
        self.soc = self.soc_arrival

    @property
    def energy_needed_kwh(self) -> float:
        """Hedefe kalan batarya enerjisi (kWh, ≥ 0)."""
        return max(0.0, (self.target_soc - self.soc) * self.battery_kwh)

    @property
    def reached_target(self) -> bool:
        return self.soc >= self.target_soc - SOC_TOL

    def max_charge_kw(self, kind: str, unit_kw: float, threshold: float, min_fraction: float) -> float:
        """Bu üniteden şu an çekebileceği en yüksek güç: ünite ve araç donanımının küçüğü, sonra CC-CV."""
        if self.reached_target:
            return 0.0
        hw = min(self.max_ac_kw if kind.upper() == "AC" else self.max_dc_kw, unit_kw)
        return cc_cv_limit(self.soc, hw, threshold, min_fraction)

    def charge(self, p_kw: float, dt_h: float, eff: float) -> float:
        """p_kw (≥ 0, şebeke tarafı) ile dt_h saat şarj eder. Sınırlama istasyonda yapılır; burada yalnızca uygulanır."""
        self.soc += p_kw * dt_h * eff / self.battery_kwh
        self.energy_in_kwh += p_kw * dt_h
        return p_kw
