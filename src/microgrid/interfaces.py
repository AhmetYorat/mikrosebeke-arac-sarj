"""Modüller arası arayüz sözleşmesi. Gerekçeler ve örnekler: docs/arayuz-sozlesmesi.md

Birimler: güç kW, enerji kWh, süre saat, SOC 0-1, fiyat TL/kWh, gerilim p.u.
Zaman noktaları saat dilimli pandas Timestamp'tir (Europe/Istanbul).

İşaret kuralı (hepsi kW):
    pv_kw         >= 0   üretim
    base_load_kw  >= 0   sabit yük tüketimi
    ev_kw         >  0   araç şarj oluyor,     < 0 araç şebekeye veriyor (V2G)
    bess_kw       >  0   batarya şarj oluyor,  < 0 deşarj
    grid_kw       >  0   şebekeden alım,       < 0 şebekeye veriş

Güç dengesi (döngü hesaplar, kimse ayrıca hesaplamaz):
    grid_kw = base_load_kw + ev_kw + bess_kw - pv_kw
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd

# Döngüye giren zaman serileri (YM-1 üretir). İndeks: simülasyon zaman adımları.
INPUT_COLUMNS = ["pv_kw", "base_load_kw", "price_tl_per_kwh"]


@dataclass(frozen=True)
class StepContext:
    """Döngünün her adımda modüllere verdiği zaman bilgisi."""

    step: int                  # 0'dan başlayan adım numarası
    timestamp: pd.Timestamp    # adımın başlangıcı
    dt_h: float                # adım uzunluğu (saat), 15 dk için 0.25

    @property
    def hour(self) -> float:
        """Saatin ondalık hâli (18:30 -> 18.5). Tarife ve profiller için."""
        return self.timestamp.hour + self.timestamp.minute / 60


@dataclass(frozen=True)
class VehicleRequest:
    """Bir ünitede bağlı aracın bu adımdaki durumu (YM-2 üretir, YM-3 okur)."""

    charger_id: str
    vehicle_id: str
    soc: float                 # adım başındaki SOC
    battery_kwh: float
    target_soc: float
    departure: pd.Timestamp
    max_charge_kw: float       # ünite gücü ve CC-CV eğrisiyle sınırlanmış üst sınır
    max_discharge_kw: float = 0.0  # V2G için verebileceği en yüksek güç (pozitif); V2G yoksa 0

    @property
    def energy_needed_kwh(self) -> float:
        return max(0.0, (self.target_soc - self.soc) * self.battery_kwh)


@dataclass(frozen=True)
class EmsInputs:
    """EMS'in bir adımda karar vermek için gördüğü her şey."""

    ctx: StepContext
    pv_kw: float
    base_load_kw: float
    price_tl_per_kwh: float
    vehicles: list[VehicleRequest]
    bess_soc: float
    station_limit_kw: float    # istasyon toplamı (ev_kw) için üst sınır
    site_limit_kw: float       # şebekeden alım (grid_kw) için üst sınır


@dataclass(frozen=True)
class Decision:
    """EMS kararı. Şebeke gücü burada yok: güç dengesinden döngü hesaplar."""

    ev_kw: dict[str, float]    # charger_id -> kW (işaret kuralına göre)
    bess_kw: float = 0.0


@dataclass(frozen=True)
class GridInjections:
    """Yük akışına giden güçler (işaret kuralına göre)."""

    pv_kw: float
    base_load_kw: float
    ev_kw: float
    bess_kw: float


@dataclass(frozen=True)
class GridResult:
    """pandapower yük akışı özeti (YM-4 + EM-2)."""

    converged: bool
    min_vm_pu: float
    max_vm_pu: float
    max_line_loading_pct: float
    trafo_loading_pct: float


class ChargingStation(Protocol):
    """YM-2. Araç geliş/gidişini, ünite atamasını ve SOC takibini yönetir."""

    def requests(self, ctx: StepContext) -> list[VehicleRequest]:
        """Bu adımda bağlı ve şarj/deşarj edilebilir araçlar."""
        ...

    def apply(self, ctx: StepContext, ev_kw: dict[str, float]) -> dict[str, float]:
        """EMS'in güçlerini uygular, SOC'leri günceller.

        Gerçekte uygulanan gücü döndürür (ör. araç dolduysa istenenden az olabilir).
        """
        ...


class Battery(Protocol):
    """YM-3. Sabit batarya (BESS)."""

    soc: float

    def apply(self, power_kw: float, dt_h: float) -> float:
        """Gücü güç ve SOC sınırlarına göre kırpar, SOC'yi günceller, uygulanan gücü döndürür."""
        ...


class EMS(Protocol):
    """YM-3. Kural tabanlı ya da optimizasyonlu enerji yönetimi."""

    def prepare(self, forecast: pd.DataFrame) -> None:
        """Simülasyon başında bir kez çağrılır; sütunlar INPUT_COLUMNS.

        Kural tabanlı EMS boş bırakabilir; MILP tüm günü burada çözüp adım adım okur.
        """
        ...

    def decide(self, inp: EmsInputs) -> Decision:
        ...


class GridModel(Protocol):
    """YM-4 + EM-2. pandapower ağı."""

    def run(self, ctx: StepContext, injections: GridInjections) -> GridResult:
        ...
