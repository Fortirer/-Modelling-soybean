"""34 - Cross-state summary table: one row per state, the headline numbers
from scripts 07/09/11/12/13/29/30 side by side.

Every number here already exists inside some state's results/ folder; nothing
is recomputed. This just collects the comparable ones into a single table so
a person (or the dashboard in app.py) can scan all twelve states at once
instead of opening twelve folders. Read on the fly, not cached, since it's
just concatenating small JSON/CSV files -- a fraction of a second even for
all twelve states.
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _00_config_helpers import iter_states  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _j(p):
    return json.loads(p.read_text()) if p.exists() else {}


def _csv(p, **kw):
    return pd.read_csv(p, **kw) if p.exists() else None


def one_state(code, name):
    seg = "" if code == "IL" else f"/{code}"
    res = ROOT / f"results{seg}"
    proc = ROOT / f"data/processed{seg}"
    row = dict(state=code, name=name.title())

    est = _j(res / "07_key_estimates.json")
    row["r2_two_way_fe"] = est.get("r2_M4")
    row["dY_dT_bu_per_F"] = est.get("dY_dT_at_means")
    row["n_county_years"] = est.get("n")

    rob = _j(res / "11_robustness_summary.json")
    row["heat_sig_specs"] = rob.get("temp_sig")
    row["heat_specs_total"] = rob.get("specs")

    cmip6 = _csv(res / "table11_cmip6_scenario_summary.csv")
    if cmip6 is not None:
        late585 = cmip6[(cmip6.scenario == "ssp585") & (cmip6.horizon == "late_century")]
        if len(late585):
            col = "ens_median_parametric_bu" if "ens_median_parametric_bu" in late585 else None
            row["ssp585_late_quad_bu"] = float(late585.iloc[0].get(col)) if col else None

    soil = _csv(proc / "soil_features.csv")
    if soil is not None and "soil_mollisol_pct" in soil:
        row["mollisol_pct_mean"] = round(float(soil.soil_mollisol_pct.mean()), 1)

    irr = _csv(proc / "irrigation_features.csv")
    if irr is not None and "irrigated_frac_avg" in irr:
        row["irrigated_pct_mean"] = round(float(irr.irrigated_frac_avg.mean()) * 100, 2)

    ozone_cfg = _j(res / "22_ozone_config.json")
    row["ozone_status"] = "skipped_server_down" if ozone_cfg.get("skipped") else (
        "ok" if (res / "table27_ozone_screen.csv").exists() else "not_run")

    frost = _csv(res / "table23_mg_frost_ceiling.csv")
    if frost is not None:
        base = frost[(frost.scenario == "baseline")]
        if len(base):
            row["max_viable_mg_baseline"] = base.iloc[0].max_viable_mg

    return row


def main():
    rows = [one_state(c, n) for c, n in iter_states()]
    df = pd.DataFrame(rows)
    out = ROOT / "results" / "_cross_state_summary.csv"
    df.to_csv(out, index=False)
    print(df.to_string(index=False))
    print(f"\n[34] -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
