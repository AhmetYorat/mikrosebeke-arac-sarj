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
        return cc_cv_limit(self.soc, self.hw_kw(kind, unit_kw), threshold, min_fraction)

    def hw_kw(self, kind: str, unit_kw: float) -> float:
        """Ünite ile araç donanımının küçüğü (CC-CV öncesi). AC'de aracın OBC'si çift yönlü kabul edilir."""
        return min(self.max_ac_kw if kind.upper() == "AC" else self.max_dc_kw, unit_kw)

    def max_discharge_kw(self, ts: pd.Timestamp, dt_h: float, unit_kw: float, p_charge_kw: float,
                         min_soc: float, eff: float) -> float:
        """V2G'de bu adımda şebekeye verebileceği en yüksek güç (şebeke tarafı, pozitif).

        İki garanti:
          1. SOC min_soc'nin altına inmez.
          2. Verilen enerji ayrılışa kadar geri doldurulabilir: bu adımdan sonra kalan sürede tam güçle şarj
             edilirse araç yine hedef SOC'ye ulaşır. Koşul  t_sonra · p_şarj · η ≥ (hedef − soc) · B + e_çıkan,
             e_çıkan için çözülünce  e_çıkan ≤ t_sonra · p_şarj · η − (hedef − soc) · B.
        V2G'ye uygun olmayan araç için 0. (station.v2g_enabled kapalıysa istasyon bu metodu hiç çağırmaz.)
        """
        if not self.v2g_capable:
            return 0.0
        t_after = (self.departure - ts).total_seconds() / 3600 - dt_h
        e_floor = (self.soc - min_soc) * self.battery_kwh
        e_slack = t_after * p_charge_kw * eff - max(0.0, self.target_soc - self.soc) * self.battery_kwh
        e_out = max(0.0, min(e_floor, e_slack))
        return min(unit_kw, e_out * eff / dt_h)

    def discharge(self, p_kw: float, dt_h: float, eff: float) -> float:
        """V2G: p_kw (≥ 0, şebeke tarafı) verir; bataryadan p · dt / η çıkar."""
        self.soc -= p_kw * dt_h / (eff * self.battery_kwh)
        self.energy_out_kwh += p_kw * dt_h
        return p_kw

    def charge(self, p_kw: float, dt_h: float, eff: float) -> float:
        """p_kw (≥ 0, şebeke tarafı) ile dt_h saat şarj eder. Sınırlama istasyonda yapılır; burada yalnızca uygulanır."""
        self.soc += p_kw * dt_h * eff / self.battery_kwh
        self.energy_in_kwh += p_kw * dt_h
        return p_kw
