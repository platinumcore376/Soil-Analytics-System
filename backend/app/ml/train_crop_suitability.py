"""
Train a crop suitability classifier: predicts which crop is suitable
given a soil's N, P, K, ph, EC, S, Cu, Fe, Mn, Zn, B readings.

Dataset: data/fertilizer_recommendation.csv (column: label = crop name)
Outputs: app/ml/models/structured/crop_suitability_model.pkl
"""
from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import classification_report, accuracy_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_PATH = REPO_ROOT / "data" / "Crop_recommendation.csv"
MODEL_OUT_DIR = Path(__file__).resolve().parent / "models" / "structured"
MODEL_OUT_DIR.mkdir(parents=True, exist_ok=True)
MODEL_OUT_PATH = MODEL_OUT_DIR / "crop_suitability_model.pkl"

FEATURE_COLS = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]


def main():
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} rows from {DATA_PATH.name}")
    print(f"Crops found: {sorted(df['label'].unique())}\n")

    X = df[FEATURE_COLS]
    y = df["label"]

    classes = sorted(y.unique())
    class_to_idx = {c: i for i, c in enumerate(classes)}
    idx_to_class = {i: c for c, i in class_to_idx.items()}
    y_enc = y.map(class_to_idx)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_enc, test_size=0.2, random_state=42, stratify=y_enc
    )

    model = XGBClassifier(
        n_estimators=300, max_depth=5, learning_rate=0.1,
        eval_metric="mlogloss", random_state=42,
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)

    print("=" * 60)
    print("MODEL ACCURACY")
    print("=" * 60)
    print(f"Accuracy : {acc*100:.2f}%\n")

    print("Classification Report")
    target_names = [idx_to_class[i] for i in sorted(idx_to_class)]
    print(classification_report(y_test, preds, target_names=target_names, digits=2))

    joblib.dump({"model": model, "classes": classes}, MODEL_OUT_PATH)
    print(f"Model Saved Successfully!")
    print(f"Location: {MODEL_OUT_PATH}")


if __name__ == "__main__":
    main()