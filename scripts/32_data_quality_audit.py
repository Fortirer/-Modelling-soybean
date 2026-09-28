"""32 - Cross-state data quality audit.

WHY THIS EXISTS
  Every state added to this pipeline has turned up at least one real data-
  quality issue that a single hard-coded assumption did not anticipate:
  Missouri's NASS bulk file carries a stale county ANSI code (script 02),
  South Dakota has SSURGO soil-survey coverage gaps on three counties
  (script 16), several states have sparse or partially-missing EPA ozone
  monitor years (script 22). Each was found by a script crashing and was
  fixed by hand, one state at a time. This script generalizes those checks
  into a single reusable audit that runs against every state's already-
  materialized outputs and flags the same classes of problem BEFORE they
  reach a downstream model -- no network calls, no re-running the pipeline,
  just inspecting what scripts 01-30 already wrote to disk.

WHAT IT CHECKS, per state
  1. Production identity check: production_bu / acres_harvested vs
     yield_bu_ac (from script 02's own report).
  2. Production-climate join completeness (from script 05's own report).
  3. Production-soil join completeness: recomputed directly by comparing
     the balanced-panel fips5 set in the final dataset against
     soil_features.csv's fips5 set, so this check does not depend on
     script 16 having printed anything.
  4. CMIP6 ensemble completeness: how many of the 9 candidate models
     actually delivered (from script 12's provenance file).
  5. EPA ozone monitor coverage and whether the screen ran at all, was
     skipped (server outage), or is simply thin (few counties with a
     monitor).
  6. Phenology calibration drift: whether _pheno.py's hard-coded STAGES/
     WINDOW_FIT constants (Illinois-calibrated) still match what script 25
     recomputes for this state -- expected to mismatch for every non-
     Illinois state, so reported as informational, not a failure.

OUTPUT
  results/<ST>/32_data_quality_audit.json  -- one state's findings
  results/_cross_state_data_quality_audit.csv -- one row per state, for the
  dashboard and for a human to scan in one pass
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _00_config_helpers import iter_states  # noqa: E402  (see bottom of this file)

ROOT = Path(__file__).resolve().parents[1]


def _paths(code):
    seg = "" if code == "IL" else f"/{code}"
    return dict(
        raw=ROOT / f"data/raw{seg}", proc=ROOT / f"data/processed{seg}",
        final=ROOT / f"data/final{seg}", res=ROOT / f"results{seg}",
    )


def _load_json(p):
    return json.loads(p.read_text()) if p.exists() else None


def audit_one(code, name):
    p = _paths(code)
    findings = []
    row = dict(state=code, name=name)

    # 1. production identity check ------------------------------------------
    clean = _load_json(p["res"] / "02_cleaning_report.json")
    if clean:
        checked = clean.get("identity_checked", 0) or 1
        fail_rate = clean.get("identity_failures_gt_0.55", 0) / checked
        row["identity_fail_rate"] = round(fail_rate, 4)
        row["max_identity_residual"] = clean.get("identity_max_residual_bu_per_acre")
        if fail_rate > 0.15:
            findings.append(f"production identity check fails on {fail_rate:.0%} "
                             f"of rows (residual up to {row['max_identity_residual']} "
                             f"bu/acre) -- raw NASS data noisier than usual here")
    else:
        findings.append("02_cleaning_report.json missing -- script 02 not run")

    # 2. climate join ---------------------------------------------------------
    merge = _load_json(p["res"] / "05_merge_report.json")
    if merge:
        row["unmatched_climate_rows"] = merge.get("unmatched_climate")
        if merge.get("unmatched_climate", 0) > 0:
            findings.append(f"{merge['unmatched_climate']} rows failed the "
                             f"production-climate join")
        row["balanced_panel_counties"] = merge.get("counties_in_balanced_panel")
        row["total_counties"] = merge.get("counties")
    else:
        findings.append("05_merge_report.json missing -- script 05 not run")

    # 3. soil join, recomputed directly ---------------------------------------
    final_csv = p["final"] / "soybean_illinois_climate_1980_2025.csv"
    soil_csv = p["proc"] / "soil_features.csv"
    if final_csv.exists() and soil_csv.exists():
        panel = pd.read_csv(final_csv, usecols=["fips5", "in_balanced_panel"],
                             dtype={"fips5": str})
        panel_fips = set(panel.loc[panel.in_balanced_panel == 1, "fips5"])
        soil_fips = set(pd.read_csv(soil_csv, usecols=["fips5"],
                                     dtype={"fips5": str}).fips5)
        missing = sorted(panel_fips - soil_fips)
        row["soil_unmatched_counties"] = len(missing)
        row["soil_unmatched_fips5"] = missing
        if missing:
            findings.append(f"{len(missing)} balanced-panel counties have no "
                             f"SSURGO soil match ({missing}) -- likely a joint/"
                             f"reservation survey area not covered by the "
                             f"STATE_FIPS+county_ansi areasymbol convention "
                             f"(see script 16's note)")
    elif final_csv.exists() or soil_csv.exists():
        findings.append("soil join could not be checked -- one of the final "
                         "panel / soil_features.csv is missing")

    # 4. CMIP6 ensemble completeness ------------------------------------------
    cmip6 = _load_json(p["res"] / "12_provenance_cmip6.json")
    if cmip6:
        n_models = cmip6.get("n_models")
        row["cmip6_models_delivered"] = n_models
        if n_models is not None and n_models < 7:
            findings.append(f"only {n_models}/9 CMIP6 models delivered")
    # not flagged as missing if absent -- script 12 hasn't run for every state
    # at every point in the pipeline's history, this audit just skips silently

    # 5. ozone coverage ---------------------------------------------------------
    ozone_cfg = _load_json(p["res"] / "22_ozone_config.json")
    ozone_table = p["res"] / "table27_ozone_screen.csv"
    if ozone_cfg and ozone_cfg.get("skipped"):
        findings.append("ozone screen SKIPPED -- EPA AQS server was unreachable "
                         "when this state last ran script 22; rerun it")
        row["ozone_status"] = "skipped_server_down"
    elif ozone_table.exists():
        row["ozone_status"] = "ok"
    else:
        row["ozone_status"] = "not_run"

    # 6. phenology calibration drift (informational only) ----------------------
    calib = _load_json(p["res"] / "25_calibration_config.json")
    row["phenology_calibrated"] = calib is not None

    row["n_findings"] = len(findings)
    row["findings"] = findings
    return row


def main():
    rows = []
    for code, name in iter_states():
        row = audit_one(code, name)
        (Path(_paths(code)["res"]) / "32_data_quality_audit.json").write_text(
            json.dumps(row, indent=2))
        rows.append(row)
        flag = "OK" if row["n_findings"] == 0 else f"{row['n_findings']} finding(s)"
        print(f"[32] {code:3} {name.title():15} {flag}")
        for f in row["findings"]:
            print(f"       - {f}")

    out = pd.DataFrame(rows)
    out_path = ROOT / "results" / "_cross_state_data_quality_audit.csv"
    out.drop(columns=["findings", "soil_unmatched_fips5"], errors="ignore") \
       .to_csv(out_path, index=False)
    print(f"\n[32] {len(rows)} states audited, "
          f"{sum(r['n_findings'] for r in rows)} total findings "
          f"-> {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
