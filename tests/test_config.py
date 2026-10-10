from microgrid.config import load_config


def test_default_config_loads():
    cfg = load_config()
    assert cfg["station"]["type"] in {"site_otoparki", "avm", "otoyol"}
    assert cfg["simulation"]["step_minutes"] > 0


def test_station_limit_below_installed_charger_power():
    # Limit toplam ünite gücünden küçük olmalı; yoksa EMS'in yöneteceği bir kısıt kalmaz.
    cfg = load_config()
    installed = sum(c["count"] * c["power_kw"] for c in cfg["station"]["chargers"])
    assert cfg["station"]["power_limit_kw"] < installed
