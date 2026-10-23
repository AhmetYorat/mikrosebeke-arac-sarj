import pandas as pd
import pytest

from microgrid.simulink_io import load_simulink_csv


def write(tmp_path, **cols):
    path = tmp_path / "D1_yuk_basamagi.csv"
    pd.DataFrame(cols).to_csv(path, index=False)
    return path


def valid(**over):
    cols = dict(
        time_s=[0.0, 0.01, 0.02],
        freq_pu=[1.0, 0.9995, 1.0004],
        v_pcc_pu=[1.0, 0.98, 0.99],
        p_grid_kw=[120.0, 900.0, 850.0],
        soc_bess=[0.5, 0.5, 0.49],
    )
    cols.update(over)
    return cols


def test_valid_file_loads_indexed_by_time(tmp_path):
    df = load_simulink_csv(write(tmp_path, **valid()))
    assert df.index.name == "time_s"
    assert df.freq_pu.iloc[1] == 0.9995


def test_frequency_in_hz_is_caught_with_hint(tmp_path):
    with pytest.raises(ValueError, match="50'ye bölün"):
        load_simulink_csv(write(tmp_path, **valid(freq_pu=[50.0, 49.98, 50.02])))


def test_soc_in_percent_and_power_in_watts_are_caught(tmp_path):
    with pytest.raises(ValueError) as err:
        load_simulink_csv(write(tmp_path, **valid(soc_bess=[50, 50, 49], p_grid_kw=[1.2e5, 9e5, 8.5e5])))
    assert "100'e bölün" in str(err.value) and "1000'e bölün" in str(err.value)


def test_missing_and_unknown_columns_are_reported(tmp_path):
    cols = valid()
    del cols["v_pcc_pu"]
    cols["Vabc"] = [1, 2, 3]
    with pytest.raises(ValueError) as err:
        load_simulink_csv(write(tmp_path, **cols))
    assert "v_pcc_pu" in str(err.value) and "Vabc" in str(err.value)
