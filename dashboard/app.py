"""Streamlit transparency dashboard for the soybean-climate pipeline.

Reads only files scripts 01-34 already wrote to disk -- no new computation,
no network calls. Run with:

    streamlit run dashboard/app.py

from the repository root (or anywhere; paths are resolved relative to this
file). If results/_cross_state_summary.csv or _cross_state_data_quality_audit.csv
are missing or stale, regenerate them first:

    python scripts/34_cross_state_summary.py
    python scripts/32_data_quality_audit.py
"""
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"

st.set_page_config(page_title="Soybean-Climate Transparency Panel",
                    layout="wide")


@st.cache_data
def load_csv(path):
    return pd.read_csv(path) if path.exists() else None


@st.cache_data
def state_registry():
    import importlib.util as u, os
    prev = os.environ.get("STATE")
    os.environ["STATE"] = "IL"
    spec = u.spec_from_file_location("cfg_probe", ROOT / "scripts/00_config.py")
    cfg = u.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    if prev is None:
        os.environ.pop("STATE", None)
    else:
        os.environ["STATE"] = prev
    return cfg.STATE_REGISTRY


REGISTRY = state_registry()
STATE_NAMES = {code: spec["name"].title() for code, spec in REGISTRY.items()}


def state_paths(code):
    seg = "" if code == "IL" else f"/{code}"
    return dict(res=ROOT / f"results{seg}", fig=ROOT / f"figures{seg}")


st.title("Soybean x Climate -- cross-state transparency panel")
st.caption(
    "Twelve-state pipeline (Illinois through Wisconsin), one codebase, "
    "STATE=<code> selects everything. This page reads the tables and "
    "figures already produced by scripts 01-34; it computes nothing new."
)

tab_overview, tab_quality, tab_model, tab_state = st.tabs(
    ["Cross-state overview", "Data quality audit", "Cross-state model", "State detail"]
)

# ---------------------------------------------------------------- overview
with tab_overview:
    summary = load_csv(RESULTS / "_cross_state_summary.csv")
    if summary is None:
        st.warning("results/_cross_state_summary.csv not found. Run "
                   "`python scripts/34_cross_state_summary.py` first.")
    else:
        st.subheader("Headline numbers, one row per state")
        st.caption("From scripts 07 (climate-yield model), 11 (robustness), "
                   "12/13 (CMIP6), soil/irrigation feature tables, and 21 "
                   "(adaptation). NaN means that state's run predates a "
                   "column or the step hasn't produced that number.")
        st.dataframe(
            summary.style.format({
                "r2_two_way_fe": "{:.3f}", "dY_dT_bu_per_F": "{:.2f}",
                "ssp585_late_quad_bu": "{:.2f}", "mollisol_pct_mean": "{:.1f}",
                "irrigated_pct_mean": "{:.2f}",
            }, na_rep="-"),
            use_container_width=True, hide_index=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Heat-coefficient significance (of 13 robustness specs)")
            st.bar_chart(summary.set_index("state")["heat_sig_specs"])
        with c2:
            st.subheader("CMIP6 SSP5-8.5 late-century yield change (bu/acre, quadratic panel)")
            chart_df = summary.dropna(subset=["ssp585_late_quad_bu"]).set_index("state")
            st.bar_chart(chart_df["ssp585_late_quad_bu"])
            st.caption("Missing bars: those states' script 13 run predates "
                       "the parametric-column naming used here (IL/IA/IN/MN).")

        c3, c4 = st.columns(2)
        with c3:
            st.subheader("Irrigated share by state (%)")
            st.bar_chart(summary.set_index("state")["irrigated_pct_mean"])
        with c4:
            st.subheader("Mollisol share by state (%)")
            st.bar_chart(summary.set_index("state")["mollisol_pct_mean"])

# ------------------------------------------------------------- data quality
with tab_quality:
    audit = load_csv(RESULTS / "_cross_state_data_quality_audit.csv")
    if audit is None:
        st.warning("results/_cross_state_data_quality_audit.csv not found. "
                   "Run `python scripts/32_data_quality_audit.py` first.")
    else:
        n_findings = int(audit["n_findings"].sum())
        st.subheader(f"{len(audit)} states audited, {n_findings} finding(s)")
        st.caption(
            "Generalizes the manual fixes already made in this project -- "
            "Missouri's stale NASS county code, South Dakota's SSURGO "
            "coverage gap -- into a reusable check that runs against every "
            "state's already-materialized outputs (see scripts/32)."
        )

        def _flag(n):
            return "OK" if n == 0 else f"{n} finding(s)"

        show = audit.copy()
        show["status"] = show["n_findings"].apply(_flag)
        st.dataframe(
            show[["state", "name", "status", "identity_fail_rate",
                  "unmatched_climate_rows", "soil_unmatched_counties",
                  "cmip6_models_delivered", "ozone_status"]],
            use_container_width=True, hide_index=True,
        )

        flagged = audit[audit.n_findings > 0]
        if len(flagged):
            st.subheader("Detail")
            for _, row in flagged.iterrows():
                with st.expander(f"{row.state} -- {row['name'].title()} "
                                  f"({int(row.n_findings)} finding(s))"):
                    import json
                    p = state_paths(row.state)["res"] / "32_data_quality_audit.json"
                    if p.exists():
                        detail = json.loads(p.read_text())
                        for f in detail.get("findings", []):
                            st.markdown(f"- {f}")

# --------------------------------------------------------- cross-state model
with tab_model:
    cfg_path = RESULTS / "33_cross_state_classifier_config.json"
    by_state = load_csv(RESULTS / "table41_loso_by_state.csv")
    summary_m = load_csv(RESULTS / "table42_loso_summary.csv")
    importance = load_csv(RESULTS / "table43_pooled_feature_importance.csv")

    if by_state is None:
        st.warning("Cross-state classifier results not found. Run "
                   "`python scripts/33_cross_state_yield_classifier.py` first.")
    else:
        st.subheader("Pooled yield-tercile classifier, leave-one-state-out")
        st.caption(
            "Every model in this project so far is trained and tested "
            "within one state. This pools all twelve into one dataset and "
            "asks whether a pattern learned in eleven states predicts the "
            "twelfth -- the transfer question that matters for deciding "
            "whether a US Corn-Belt model says anything about a new region."
        )
        if cfg_path.exists():
            import json
            cfg = json.loads(cfg_path.read_text())
            m1, m2, m3 = st.columns(3)
            m1.metric("Best model", cfg["best_model"])
            m2.metric("Mean accuracy (held-out states)",
                      f"{cfg['mean_accuracy']:.1%}")
            m3.metric("Baseline (most-frequent class)",
                      f"{cfg['baseline_accuracy']:.1%}")

        st.subheader("Accuracy by held-out state and model")
        pivot = by_state.pivot(index="held_out_state", columns="model",
                                values="accuracy")
        st.dataframe(pivot.style.format("{:.3f}"), use_container_width=True)
        st.bar_chart(pivot)

        if importance is not None:
            st.subheader("Pooled feature importance (top 10)")
            imp_col = importance.columns[-1]
            st.bar_chart(importance.set_index(importance.columns[0]).head(10)[imp_col])

# ------------------------------------------------------------- state detail
with tab_state:
    code = st.selectbox("State", options=list(REGISTRY.keys()),
                         format_func=lambda c: f"{c} -- {STATE_NAMES[c]}")
    paths = state_paths(code)
    st.subheader(STATE_NAMES[code])

    import json
    manifest_path = paths["res"] / "10_final_dataset_manifest.json"
    if manifest_path.exists():
        m = json.loads(manifest_path.read_text())
        c1, c2, c3 = st.columns(3)
        c1.metric("Counties", m.get("counties"))
        c2.metric("County-years", m.get("rows"))
        c3.metric("Focal county", m.get("focal"))

    figs_to_show = [
        ("fig01_state_production_timeseries.png", "State production over time"),
        ("fig13_county_climate_sensitivity.png", "County climate sensitivity"),
        ("fig19_cmip6_warming.png", "CMIP6 ensemble warming"),
        ("fig33_county_validation.png", "County-level validation"),
    ]
    cols = st.columns(2)
    for i, (fname, caption) in enumerate(figs_to_show):
        fpath = paths["fig"] / fname
        if fpath.exists():
            cols[i % 2].image(str(fpath), caption=caption, use_container_width=True)

    st.subheader("All figures for this state")
    all_figs = sorted(paths["fig"].glob("*.png")) if paths["fig"].exists() else []
    if all_figs:
        chosen = st.selectbox("Pick a figure", [f.name for f in all_figs])
        st.image(str(paths["fig"] / chosen), use_container_width=True)
    else:
        st.info("No figures found for this state yet.")
