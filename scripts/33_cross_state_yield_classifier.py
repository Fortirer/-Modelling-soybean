"""33 - Pooled, cross-state yield classifier with leave-one-state-out validation.

WHY THIS EXISTS
  Every predictive model built so far (scripts 08, 13, 20) is trained and
  tested within a single state. That answers "does climate predict this
  state's yield anomaly," but never "does a pattern learned in one place
  transfer to another" -- the question that actually matters for deciding
  whether a model built on US Corn Belt data says anything useful about,
  say, Brazil. This script pools all twelve states' balanced-panel county-
  years into one dataset and tests transfer directly with leave-one-state-
  out (LOSO) cross-validation: train a classifier on eleven states, predict
  the twelfth, repeat for every state.

TARGET
  A 3-class label -- yield_anom tercile (LOW / MID / HIGH) -- computed
  WITHIN each state, not pooled, because yield_anom is already a county-
  specific-trend residual (mean zero by construction within a county) and
  its scale differs by state (Missouri's residual SD is much larger than
  Michigan's). Classifying within-state terciles keeps the target
  comparable across states and turns this into the "predictive and/or
  classification model" this repo has not yet built, using the same 20
  calendar climate features every state already shares (08_ml_config.json).

WHY LOSO, NOT A RANDOM SPLIT
  A random split would let the model see 11 counties from a state in
  training and predict a 12th from the SAME state in the test fold --
  leaking that state's mean climate and its particular yield-anomaly scale.
  LOSO removes an entire state, so what's left in training has never seen
  that state's climate distribution at all. This is a strictly harder and
  more honest test, mirroring script 26's spatial-holdout design at the
  state level instead of the district level.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
from sklearn.dummy import DummyClassifier

sys.path.insert(0, str(Path(__file__).parent))
from _00_config_helpers import iter_states  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SEED = 42
CLASSES = ["LOW", "MID", "HIGH"]


def load_state_panel(code):
    seg = "" if code == "IL" else f"/{code}"
    final = ROOT / f"data/final{seg}/soybean_illinois_climate_1980_2025.csv"
    cfg_path = ROOT / f"results{seg}/08_ml_config.json"
    if not final.exists() or not cfg_path.exists():
        return None, None
    feats = json.loads(cfg_path.read_text())["features"]
    d = pd.read_csv(final, dtype={"fips5": str})
    d = d[d.in_balanced_panel == 1].copy()
    d = d.dropna(subset=feats + ["yield_anom"])
    if len(d) < 50:
        return None, None
    d["state"] = code
    # within-state terciles, computed on THIS state's distribution only
    d["target"] = pd.qcut(d.yield_anom, 3, labels=CLASSES)
    return d, feats


def main():
    pooled, feat_sets = [], []
    for code, name in iter_states():
        d, feats = load_state_panel(code)
        if d is None:
            print(f"[33] {code:3} {name.title():15} SKIPPED (missing final panel or ml config)")
            continue
        pooled.append(d)
        feat_sets.append(set(feats))
        print(f"[33] {code:3} {name.title():15} {len(d):,} county-years, "
              f"terciles {dict(d.target.value_counts())}")

    common = sorted(set.intersection(*feat_sets))
    print(f"\n[33] {len(pooled)} states pooled | {len(common)} climate features "
          f"common to all of them")
    df = pd.concat(pooled, ignore_index=True)
    print(f"[33] pooled dataset: {len(df):,} county-years, {df.state.nunique()} states")

    models = {
        "baseline (most frequent)": lambda: DummyClassifier(strategy="most_frequent"),
        "logistic regression": lambda: LogisticRegression(max_iter=2000),
        "gradient boosting": lambda: GradientBoostingClassifier(
            n_estimators=200, max_depth=3, learning_rate=.05, random_state=SEED),
    }

    print("\n[33] LEAVE-ONE-STATE-OUT CROSS-VALIDATION")
    rows, all_true, all_pred = [], {m: [] for m in models}, {m: [] for m in models}
    for held_out in sorted(df.state.unique()):
        trn = df[df.state != held_out]
        tst = df[df.state == held_out]
        for mname, mfactory in models.items():
            mdl = mfactory()
            mdl.fit(trn[common], trn.target)
            pred = mdl.predict(tst[common])
            acc = accuracy_score(tst.target, pred)
            f1 = f1_score(tst.target, pred, average="macro")
            rows.append(dict(held_out_state=held_out, model=mname,
                              n_test=len(tst), accuracy=acc, macro_f1=f1))
            all_true[mname].extend(tst.target.tolist())
            all_pred[mname].extend(pred.tolist())

    T = pd.DataFrame(rows)
    print(T.pivot(index="held_out_state", columns="model", values="accuracy")
           .round(3).to_string())

    print("\n[33] MEAN ACROSS ALL 12 HELD-OUT STATES")
    summary = T.groupby("model")[["accuracy", "macro_f1"]].mean().round(4)
    summary["n_states"] = T.groupby("model").size() // 1
    print(summary.sort_values("accuracy", ascending=False).to_string())

    best = summary["accuracy"].idxmax()
    cm = confusion_matrix(all_true[best], all_pred[best], labels=CLASSES)
    print(f"\n[33] confusion matrix, best model ({best}), pooled across all "
          f"held-out folds")
    print(pd.DataFrame(cm, index=[f"true_{c}" for c in CLASSES],
                        columns=[f"pred_{c}" for c in CLASSES]).to_string())

    # a permutation-style feature importance from one full-data GBM fit,
    # informational only -- LOSO already answers the transfer question above
    gbm = GradientBoostingClassifier(n_estimators=200, max_depth=3,
                                      learning_rate=.05, random_state=SEED)
    gbm.fit(df[common], df.target)
    imp = (pd.Series(gbm.feature_importances_, index=common)
             .sort_values(ascending=False))
    print("\n[33] feature importance (full-data fit, informational)")
    print(imp.head(10).round(4).to_string())

    res_dir = ROOT / "results"
    T.to_csv(res_dir / "table41_loso_by_state.csv", index=False)
    summary.to_csv(res_dir / "table42_loso_summary.csv")
    imp.round(5).rename_axis("feature").reset_index(name="importance").to_csv(
        res_dir / "table43_pooled_feature_importance.csv", index=False)
    (res_dir / "33_cross_state_classifier_config.json").write_text(json.dumps(dict(
        states_pooled=sorted(df.state.unique().tolist()),
        n_county_years=len(df), n_features=len(common), features=common,
        target="within-state yield_anom tercile (LOW/MID/HIGH)",
        validation="leave-one-state-out", seed=SEED,
        best_model=best,
        mean_accuracy=float(summary.loc[best, "accuracy"]),
        mean_macro_f1=float(summary.loc[best, "macro_f1"]),
        baseline_accuracy=float(summary.loc["baseline (most frequent)", "accuracy"]),
    ), indent=2))
    print(f"\n[33] -> results/table41_loso_by_state.csv")
    print(f"[33] -> results/table42_loso_summary.csv")
    print(f"[33] -> results/table43_pooled_feature_importance.csv")
    print(f"[33] -> results/33_cross_state_classifier_config.json")


if __name__ == "__main__":
    main()
