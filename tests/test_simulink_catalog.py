"""simulink_io/catalog.py: dosya kataloğu, D1–D4 durumu, frekans özeti, kritik an (YM-4)."""
import numpy as np
import pandas as pd
import pytest

from microgrid.config import load_config
from microgrid.simulink_io import critical_moment, list_outputs, status_table, summarize
from microgrid.sim.loop import time_index
from microgrid.sim.mocks import mock_inputs
from microgrid.sim.scenarios import SCENARIOS, simulate

BAND = (0.999, 1.001)


def synthetic_step(t_end=40.0, dt=0.01, dip_at=10.0):
    """Sentetik test sinyali (gerçek Simulink sonucu değil): t=dip_at'te frekans düşüp üstel toparlanır."""
    t = np.arange(0, t_end, dt)
    f = 1.0 - 0.002 * np.where(t >= dip_at, np.exp(-(t - dip_at) / 1.5), 0.0)
    return pd.DataFrame({"time_s": t, "freq_pu": f, "v_pcc_pu": 1.0 - 0.02 * (1 - f) / 0.002,
                         "p_grid_kw": 100 + 50 * (t >= dip_at)})


def test_catalog_status_and_errors(tmp_path):
    synthetic_step().to_csv(tmp_path / "D1_yuk_basamagi.csv", index=False)
    bad = synthetic_step()
    bad["freq_pu"] *= 50   # Hz olarak kaydedilmiş
    bad.to_csv(tmp_path / "D3_pv_dususu.csv", index=False)
    synthetic_step().to_csv(tmp_path / "sonuc_son.csv", index=False)   # adı kurala uymuyor

    runs = list_outputs(tmp_path)
    by_name = {r.path.name: r for r in runs}
    assert by_name["D1_yuk_basamagi.csv"].error is None
    assert "50'ye bölün" in by_name["D3_pv_dususu.csv"].error
    assert "kuralına uymuyor" in by_name["sonuc_son.csv"].error

    status = status_table(runs).set_index("senaryo")["durum"]
    assert status.to_dict() == {"D1": "hazır", "D2": "gelmedi", "D3": "hatalı", "D4": "gelmedi"}


def test_empty_directory_means_nothing_arrived(tmp_path):
    assert (status_table(list_outputs(tmp_path))["durum"] == "gelmedi").all()


def test_summarize_band_exit_and_recovery():
    df = synthetic_step().set_index("time_s")
    s = summarize(df, BAND)
    assert s["f_min_pu"] == pytest.approx(0.998, abs=1e-6) and s["f_min_t_s"] == pytest.approx(10.0)
    # 0.002·e^(-τ/1.5) < 0.001  ->  τ > 1.5·ln2 ≈ 1.04 s banttan dışarıda
    assert s["bant_disi_s"] == pytest.approx(1.5 * np.log(2), abs=0.02)
    assert s["banda_donus_t_s"] == pytest.approx(10 + 1.5 * np.log(2), abs=0.02)


def test_critical_moment_is_peak_import():
    cfg = load_config()
    steps = simulate(cfg, SCENARIOS["S2 Kontrolsüz şarj"], mock_inputs(cfg, time_index(cfg))).steps
    cm = critical_moment(steps, cfg)
    assert cm["sebeke_alim_kw"] == pytest.approx(steps["grid_kw"].max(), abs=0.05)
    assert cm["istasyon_kw"] > 0
