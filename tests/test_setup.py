"""sim/setup.py: veri yoksa sahte girdiye düşme, temsili gün seçimi (YM-4)."""
import pytest

import microgrid.sim.setup as setup
from microgrid.config import load_config
from microgrid.interfaces import INPUT_COLUMNS
from microgrid.sim.loop import time_index


def _missing(*_a, **_k):
    raise FileNotFoundError("data/processed/pv_bandirma_2023.csv yok")


def test_falls_back_to_mock_when_data_missing(monkeypatch):
    monkeypatch.setattr(setup, "build_inputs", _missing)
    cfg = load_config()
    index = time_index(cfg)
    inputs, source = setup.load_inputs(cfg, index)
    assert source == setup.SAHTE
    assert list(inputs.columns) == INPUT_COLUMNS and inputs.index.equals(index)


def test_no_silent_fallback_when_real_data_required(monkeypatch):
    monkeypatch.setattr(setup, "build_inputs", _missing)
    cfg = load_config()
    with pytest.raises(FileNotFoundError):
        setup.load_inputs(cfg, time_index(cfg), allow_mock=False)


def test_with_start_does_not_mutate_original():
    cfg = load_config()
    original = cfg["simulation"]["start"]
    aralik = setup.with_start(cfg, setup.TEMSILI_GUNLER["aralik"])
    assert time_index(aralik)[0].month == 12
    assert cfg["simulation"]["start"] == original
    assert setup.with_start(cfg, None) is cfg
