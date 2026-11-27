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


def _html(at) -> str:
    return "".join(str(e.proto) for e in at.get("html"))


def test_dashboard_opens_without_errors():
    at = _run()
    assert not at.exception
    page = _html(at)
    for text in ("Şebeke tepe alımı", "Günlük maliyet", "Canlı tek hat şeması", "Otopark"):
        assert text in page, text


def test_every_scenario_renders():
    from microgrid.sim.scenarios import SCENARIOS
    for name in SCENARIOS:
        at = _run(Senaryo=name)
        assert not at.exception, name


def test_live_diagram_parts():
    """Tek hat şeması ve otopark: seçilen adımın değerleri doğru yerde görünüyor (tarayıcısız, saf HTML)."""
    import base64
    import sys

    import pandas as pd

    sys.path.insert(0, str(Path(APP).parent))
    import sema
    from microgrid.config import load_config

    cfg = load_config()
    row = pd.Series(dict(pv_kw=2.0, base_load_kw=24.0, ev_kw=210.0, bess_kw=0.0, grid_kw=232.0, bess_soc=0.5,
                         min_vm_pu=0.961, max_line_loading_pct=117.0, trafo_loading_pct=60.0))
    img = sema.single_line(row, cfg, connected=10)
    svg = base64.b64decode(img.split("base64,")[1].split('"')[0]).decode("utf-8")
    assert "alım 232 kW" in svg and "%117" in svg and "site sınırı 180 kW aşıldı" in svg

    t = pd.Timestamp("2023-06-21 19:45", tz="Europe/Istanbul")
    at_t = pd.DataFrame([dict(timestamp=t, charger_id="AC1", vehicle_id="EV01", soc=0.42, power_kw=11.0)])
    bays = sema.parking(at_t, pd.DataFrame(), t, cfg)
    assert bays.count("mk-bay\"") + bays.count("mk-bay on") == 10 and "EV01" in bays and "%42" in bays


def test_presentation_notes_follow_results():
    """Sunum notları sabit metin değil: sonuçtaki sınır aşımını, kablo yüklenmesini ve tepe kaymasını söylüyor."""
    import sys

    import pandas as pd

    sys.path.insert(0, str(Path(APP).parent))
    import re

    import notlar
    from microgrid.config import load_config

    plain = lambda notes: " ".join(re.sub("<[^>]+>", "", t) for _, t in notes)
    cfg = load_config()
    idx = pd.date_range("2023-06-21 12:00", periods=96, freq="15min", tz="Europe/Istanbul")
    steps = pd.DataFrame(0.0, index=idx, columns=["pv_kw", "base_load_kw", "ev_kw", "bess_kw", "grid_kw",
                                                  "min_vm_pu", "max_line_loading_pct", "trafo_loading_pct"])
    steps["min_vm_pu"], steps["max_line_loading_pct"], steps["trafo_loading_pct"] = 0.99, 50.0, 20.0
    peak = idx[31]   # 19:45
    steps.loc[peak, ["grid_kw", "ev_kw", "max_line_loading_pct"]] = [232.0, 210.0, 117.0]
    k = pd.Series({"arac_sarj_puant_payi": 0.9})
    text = plain(notlar.power("S2 Kontrolsüz şarj", steps, k, cfg) + notlar.grid(steps, cfg))
    assert "15 dakika aşılıyor" in text and "adım" not in text and "232 kW" in text and "19:45" in text and "%117" in text

    morning = idx[71]   # 05:45: tepe puant dışında → tepe kayması notu
    steps.loc[peak, ["grid_kw", "ev_kw"]] = [30.0, 0.0]
    steps.loc[morning, ["grid_kw", "ev_kw"]] = [180.0, 150.0]
    text = plain(notlar.power("S5 Optimizasyon (MILP)", steps, pd.Series({"arac_sarj_puant_payi": 0.05}), cfg))
    assert "tepe kayması" in text and "05:45" in text
