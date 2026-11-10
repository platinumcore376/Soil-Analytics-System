"""
Train per-nutrient/micronutrient deficiency classifiers (gradient-boosted)
and report per-parameter accuracy, matching the project's reporting standard.

Dataset: data/fertilizer_recommendation.csv
Columns: N, P, K, ph, EC, S, Cu, Fe, Mn, Zn, B, label

Labels are derived from threshold rules for each of the 11 soil parameters.
Thresholds are approximate agronomic bands; adjust to match your project
documentation's exact values if specified elsewhere.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_PATH = REPO_ROOT / "data" / "fertilizer_recommendation.csv"
MODEL_OUT_DIR = Path(__file__).resolve().parent / "models" / "structured"
MODEL_OUT_DIR.mkdir(parents=True, exist_ok=True)

# Approximate agronomic threshold bands per parameter (low / high cutoffs).
# N/P/K in kg/ha, EC in dS/m, S in %, Cu/Fe/Mn/Zn/B in ppm, ph on 0-14 scale.
THRESHOLDS = {
    "N":  {"low": 40,  "high": 120},
    "P":  {"low": 20,  "high": 60},
    "K":  {"low": 40,  "high": 200},
    "ph": {"low": 6.0, "high": 7.5},
    "EC": {"low": 0.2, "high": 0.8},
    "S":  {"low": 0.15, "high": 0.30},
    "Cu": {"low": 5.0, "high": 15.0},
    "Fe": {"low": 50.0, "high": 100.0},
    "Mn": {"low": 30.0, "high": 60.0},
    "Zn": {"low": 30.0, "high": 60.0},
    "B":  {"low": 20.0, "high": 40.0},
}

FEATURE_COLS = ["N", "P", "K", "ph", "EC", "S", "Cu", "Fe", "Mn", "Zn", "B"]


def status_from_threshold(value: float, low: float, high: float) -> str:
    if value < low:
        return "low"
    if value > high:
        return "high"
    return "adequate"


def main():
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} rows from {DATA_PATH.name}")
    print(f"Columns: {df.columns.tolist()}\n")

    features = df[FEATURE_COLS].copy()

    labels = pd.DataFrame(index=df.index)
    for param, bounds in THRESHOLDS.items():
        labels[param] = df[param].apply(
            lambda v, lo=bounds["low"], hi=bounds["high"]: status_from_threshold(v, lo, hi)
        )

    accuracies = {}
    encoders = {}

    for target in FEATURE_COLS:
        y = labels[target]

        # Skip a parameter if it has only one class (threshold too loose/tight)
        if y.nunique() < 2:
            print(f"Skipping {target}: only one class present ({y.unique()[0]})")
            continue

        # Drop the target nutrient column from features to prevent label leakage.
        # The model must learn deficiency correlations from the remaining soil indicators.
        X_target = features.drop(columns=[target])

        X_train, X_test, y_train, y_test = train_test_split(
            X_target, y, test_size=0.2, random_state=42, stratify=y
        )

        classes = sorted(y.unique())
        class_to_idx = {c: i for i, c in enumerate(classes)}
        y_train_enc = y_train.map(class_to_idx)
        y_test_enc = y_test.map(class_to_idx)

        model = XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.1,
            eval_metric="mlogloss", random_state=42,
        )
        model.fit(X_train, y_train_enc)

        preds = model.predict(X_test)
        acc = accuracy_score(y_test_enc, preds)
        accuracies[target] = acc
        encoders[target] = classes

        model.save_model(str(MODEL_OUT_DIR / f"deficiency_{target.lower()}_xgb.json"))

    joblib.dump(encoders, MODEL_OUT_DIR / "deficiency_label_encoders.joblib")

    print("=" * 60)
    print("DEFICIENCY MODEL ACCURACY (per nutrient)")
    print("=" * 60)
    for target, acc in accuracies.items():
        print(f"{target:>4}: {acc*100:.2f}%")
    overall = sum(accuracies.values()) / len(accuracies)
    print(f"\nOverall mean accuracy across nutrients: {overall*100:.2f}%")

    print(f"\nModel Saved Successfully!")
    print(f"Location: {MODEL_OUT_DIR}")


if __name__ == "__main__":
    main()