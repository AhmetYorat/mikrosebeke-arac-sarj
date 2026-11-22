"""Dashboard hatasız açılıyor mu? (YM-4) Streamlit'in test aracıyla tarayıcısız çalıştırılır.

Neden: dashboard canlı demoda kullanılacak; bir modül değişikliği onu kırarsa derste değil burada görülsün.
"""
from pathlib import Path

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP = str(Path(__file__).resolve().parents[1] / "dashboard" / "app.py")


def _run(**sidebar):
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    for label, value in sidebar.items():
        next(w for w in at.sidebar.selectbox if w.label == label).set_value(value)
    if sidebar:
        at.run()
    return at


def test_dashboard_opens_without_errors():
    at = _run()
    assert not at.exception
    assert len(at.metric) >= 4


def test_every_scenario_renders():
    from microgrid.sim.scenarios import SCENARIOS
    for name in SCENARIOS:
        at = _run(Senaryo=name)
        assert not at.exception, name
