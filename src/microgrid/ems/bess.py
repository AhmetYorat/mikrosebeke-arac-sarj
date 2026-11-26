"""Sabit batarya (BESS) modeli (YM-3, Hafta 3). Sözleşmedeki `Battery` arayüzünü uygular.

İşaret kuralı (docs/arayuz-sozlesmesi.md): güç > 0 batarya şarj oluyor, < 0 deşarj oluyor.
Güç, bataryanın şebeke/inverter tarafındaki (AC) değeridir; enerji kayıpları depolanan enerjide görünür.

Verim (`bess.efficiency`) her yönde ayrı uygulanır (şarjda ve deşarjda), yani gidiş-dönüş verimi η²'dir
(0.95 → ~%90). Neden: kayıp hem şarj hem deşarj inverterinde ve hücrede oluşur; yalnızca şarjda saymak
bataryayı olduğundan verimli gösterir ve gece ucuz şarj / puant deşarj kazancını şişirir.

    depolanan enerji değişimi  =  P · dt · η          (P > 0, şarj)
    depolanan enerji değişimi  =  P · dt / η          (P < 0, deşarj; P negatif olduğundan enerji azalır)

Güç iki şeyle sınırlanır: `power_kw` (inverter) ve SOC bandı `[soc_min, soc_max]`.
`apply` istenen gücü kırpar ve gerçekte uygulanan gücü döndürür.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BessParams:
    capacity_kwh: float = 200.0
    power_kw: float = 100.0
    efficiency: float = 0.95      # her yön için
    soc_min: float = 0.1
    soc_max: float = 0.9
    soc_initial: float = 0.5

    def __post_init__(self):
        if self.capacity_kwh <= 0 or self.power_kw <= 0:
            raise ValueError("kapasite ve güç pozitif olmalı")
        if not 0 < self.efficiency <= 1:
            raise ValueError("verim (0, 1] aralığında olmalı")
        if not 0 <= self.soc_min < self.soc_max <= 1:
            raise ValueError("SOC bandı 0 <= soc_min < soc_max <= 1 olmalı")
        if not self.soc_min <= self.soc_initial <= self.soc_max:
            raise ValueError("başlangıç SOC'si SOC bandının içinde olmalı")

    @classmethod
    def from_config(cls, cfg: dict) -> "BessParams":
        b = cfg["bess"]
        return cls(b["capacity_kwh"], b["power_kw"], b["efficiency"], b["soc_min"], b["soc_max"], b["soc_initial"])


class BESS:
    """Durum: `soc` (0–1). Sayaçlar KPI ve rapor içindir (kayıp, çevrim)."""

    def __init__(self, params: BessParams | dict):
        self.p = params if isinstance(params, BessParams) else BessParams.from_config(params)
        self.soc = self.p.soc_initial
        self.charged_kwh = 0.0      # şebeke tarafından çekilen toplam enerji
        self.discharged_kwh = 0.0   # şebeke tarafına verilen toplam enerji

    # --- sınırlar: EMS'in "batarya şu an ne yapabilir?" sorusu için ---

    @property
    def stored_kwh(self) -> float:
        return self.soc * self.p.capacity_kwh

    def max_charge_kw(self, dt_h: float) -> float:
        """Bu adımda uygulanabilecek en yüksek şarj gücü (SOC üst sınırı ve inverter)."""
        room_kwh = max(0.0, (self.p.soc_max - self.soc) * self.p.capacity_kwh)
        return min(self.p.power_kw, room_kwh / (dt_h * self.p.efficiency))

    def max_discharge_kw(self, dt_h: float) -> float:
        """Bu adımda uygulanabilecek en yüksek deşarj gücü (pozitif sayı; SOC alt sınırı ve inverter)."""
        avail_kwh = max(0.0, (self.soc - self.p.soc_min) * self.p.capacity_kwh)
        return min(self.p.power_kw, avail_kwh * self.p.efficiency / dt_h)

    # --- Battery arayüzü ---

    def apply(self, power_kw: float, dt_h: float) -> float:
        """Gücü sınırlara kırpar, SOC'yi günceller, uygulanan gücü döndürür."""
        if dt_h <= 0:
            raise ValueError("dt_h pozitif olmalı")
        if power_kw >= 0:
            p = min(power_kw, self.max_charge_kw(dt_h))
            self.soc += p * dt_h * self.p.efficiency / self.p.capacity_kwh
            self.charged_kwh += p * dt_h
        else:
            p = -min(-power_kw, self.max_discharge_kw(dt_h))
            self.soc += p * dt_h / self.p.efficiency / self.p.capacity_kwh
            self.discharged_kwh += -p * dt_h
        # kayan nokta artığı SOC bandının dışına taşmasın
        self.soc = min(max(self.soc, self.p.soc_min), self.p.soc_max)
        return p

    # --- rapor için türetilmiş değerler ---

    @property
    def losses_kwh(self) -> float:
        """Şimdiye kadarki verim kaybı: şebekeden çekilen − verilen − depodaki net değişim."""
        return self.charged_kwh - self.discharged_kwh - (self.soc - self.p.soc_initial) * self.p.capacity_kwh

    @property
    def equivalent_cycles(self) -> float:
        """Tam çevrim eşdeğeri: toplam geçen enerji / (2 × kullanılabilir kapasite)."""
        usable = (self.p.soc_max - self.p.soc_min) * self.p.capacity_kwh
        return (self.charged_kwh + self.discharged_kwh) / (2 * usable)
