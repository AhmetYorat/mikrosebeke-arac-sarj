"""Döngüyü kurmak için ortak yardımcılar (YM-4). Komut satırı (sim/__main__) ve dashboard aynı yolu kullanır.

Neden ayrı modül: "veri yoksa ne olacak" kararı tek yerde olsun. Repoyu yeni klonlayan biri
`python -m microgrid.data` çalıştırmadan dashboard'u açarsa hata yerine sahte girdilerle ve açık bir uyarıyla
çalışsın; ama komut satırında gerçek veri istenmişse sessizce sahteye düşmesin.
"""
from __future__ import annotations

import pandas as pd

from microgrid.data.inputs import build_inputs
from microgrid.sim.mocks import mock_inputs

GERCEK = "gercek"   # YM-1 build_inputs: PVGIS + BDEW yük profilleri + EPDK tarife
SAHTE = "sahte"     # sim.mocks.mock_inputs: çan eğrisi PV, akşam pikli yük


def load_inputs(cfg: dict, index: pd.DatetimeIndex, allow_mock: bool = True) -> tuple[pd.DataFrame, str]:
    """Girdi tablosu ve kaynağı. Veri dosyaları yoksa allow_mock=True ise sahte girdilere düşer.

    Kaynak, sonuçla birlikte gösterilmeli: sahte girdiyle çıkan sayı raporda gerçek sonuç gibi kullanılmamalı.
    """
    try:
        return build_inputs(cfg, index), GERCEK
    except FileNotFoundError:
        if not allow_mock:
            raise
        return mock_inputs(cfg, index), SAHTE


def with_start(cfg: dict, start: str | None) -> dict:
    """Simülasyon başlangıcı değiştirilmiş config kopyası (temsili gün seçimi için)."""
    if not start:
        return cfg
    return {**cfg, "simulation": {**cfg["simulation"], "start": start}}


# Temsili günler (ekip kararı, docs/arayuz-sozlesmesi.md): hafta içi ortalama gün, öğlen başlar ertesi gün öğlen biter.
TEMSILI_GUNLER = {"haziran": "2023-06-21 12:00", "aralik": "2023-12-20 12:00"}
