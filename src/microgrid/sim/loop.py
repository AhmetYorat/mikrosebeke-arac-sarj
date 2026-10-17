"""Simülasyon döngüsü (YM-4). Modülleri her adımda sözleşmedeki sırayla çağırır."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from microgrid.interfaces import (
    EMS,
    INPUT_COLUMNS,
    Battery,
    ChargingStation,
    EmsInputs,
    GridInjections,
    GridModel,
    StepContext,
)

# Sonuç tablosunun sütunları. Dashboard ve KPI modülü bunlara güvenir; değiştirmek PR ister.
STEP_COLUMNS = [
    "pv_kw", "base_load_kw", "ev_kw", "bess_kw", "grid_kw",
    "bess_soc", "price_tl_per_kwh", "cost_tl", "n_vehicles",
    "grid_converged", "min_vm_pu", "max_vm_pu", "max_line_loading_pct", "trafo_loading_pct",
]
STATION_COLUMNS = ["timestamp", "charger_id", "vehicle_id", "soc", "power_kw"]


@dataclass
class SimResult:
    steps: pd.DataFrame      # adım başına bir satır, indeks timestamp, sütunlar STEP_COLUMNS
    station: pd.DataFrame    # adım × bağlı araç başına bir satır, sütunlar STATION_COLUMNS


def time_index(cfg: dict) -> pd.DatetimeIndex:
    sim = cfg["simulation"]
    n = int(sim["horizon_hours"] * 60 / sim["step_minutes"])
    start = pd.Timestamp(sim["start"], tz=sim["timezone"])
    return pd.date_range(start, periods=n, freq=f"{sim['step_minutes']}min", name="timestamp")


def run(
    cfg: dict,
    inputs: pd.DataFrame,
    station: ChargingStation,
    ems: EMS,
    battery: Battery,
    grid: GridModel | None = None,
) -> SimResult:
    """inputs: indeksi time_index(cfg), sütunları INPUT_COLUMNS olan tablo (YM-1)."""
    missing = set(INPUT_COLUMNS) - set(inputs.columns)
    if missing:
        raise ValueError(f"inputs tablosunda eksik sütun: {sorted(missing)}")

    dt_h = cfg["simulation"]["step_minutes"] / 60
    limit_kw = cfg["station"]["power_limit_kw"]
    ems.prepare(inputs[INPUT_COLUMNS])

    rows, station_rows = [], []
    for step, (ts, row) in enumerate(inputs.iterrows()):
        ctx = StepContext(step=step, timestamp=ts, dt_h=dt_h)

        vehicles = station.requests(ctx)
        decision = ems.decide(EmsInputs(
            ctx=ctx,
            pv_kw=row.pv_kw,
            base_load_kw=row.base_load_kw,
            price_tl_per_kwh=row.price_tl_per_kwh,
            vehicles=vehicles,
            bess_soc=battery.soc,
            station_limit_kw=limit_kw,
        ))
        ev_applied = station.apply(ctx, decision.ev_kw)
        bess_kw = battery.apply(decision.bess_kw, dt_h)

        ev_kw = sum(ev_applied.values())
        grid_kw = row.base_load_kw + ev_kw + bess_kw - row.pv_kw

        if grid is not None:
            gr = grid.run(ctx, GridInjections(row.pv_kw, row.base_load_kw, ev_kw, bess_kw))
            grid_cols = [gr.converged, gr.min_vm_pu, gr.max_vm_pu, gr.max_line_loading_pct, gr.trafo_loading_pct]
        else:
            grid_cols = [None] + [float("nan")] * 4

        rows.append([
            row.pv_kw, row.base_load_kw, ev_kw, bess_kw, grid_kw,
            battery.soc, row.price_tl_per_kwh,
            # Şimdilik yalnızca alım ücretlendirilir; şebekeye satış fiyatı açık soru.
            max(grid_kw, 0.0) * row.price_tl_per_kwh * dt_h,
            len(vehicles),
            *grid_cols,
        ])
        for v in vehicles:
            station_rows.append([ts, v.charger_id, v.vehicle_id, v.soc, ev_applied.get(v.charger_id, 0.0)])

    steps = pd.DataFrame(rows, index=inputs.index, columns=STEP_COLUMNS)
    return SimResult(steps=steps, station=pd.DataFrame(station_rows, columns=STATION_COLUMNS))
