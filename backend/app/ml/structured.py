"""Structured-data inference service (Weeks 3-4).

Loads the artifacts produced by:
    app/ml/train_deficiency.py        -> per-parameter deficiency classifiers
    app/ml/train_crop_suitability.py  -> crop suitability classifier

and turns one set of soil lab readings into the outputs the project
documentation requires from the analysis endpoint:

    "Serve the model via a FastAPI endpoint returning soil health scores,
     deficiency diagnoses, and degradation risk indices."

Design decisions worth knowing:

* **The rule engine is the source of truth for deficiency status.** The
  gradient-boosted models were trained on labels derived from those same
  threshold bands (see THRESHOLDS below), so they cannot meaningfully
  disagree. They contribute calibrated confidence. Where a model does
  disagree with the rule, the rule wins and the disagreement is reported
  in `model_agreement`.
* Models load lazily on first use and are cached, so importing this module
  is cheap and a missing artifact does not prevent the API from starting.
* **The crop-suitability model uses a different feature set than the
  deficiency models.** It's trained on the public Kaggle Crop_recommendation
  dataset (N, P, K, temperature, humidity, ph, rainfall — 22 crop classes),
  which doesn't carry the micronutrient columns (EC, S, Cu, Fe, Mn, Zn, B)
  the deficiency models use. A separate feature frame (`crop_frame`) is
  built for crop prediction; see CROP_FEATURE_COLS below.
* **SHAP explainability degrades gracefully, it does not fail the request.**
  `shap` pulls in `numba`, which unconditionally loads `llvmlite.dll` the
  moment it's imported -- on a machine where Windows Smart App Control (or
  any code-integrity policy) blocks that DLL, `import shap` raises OSError
  even though the diagnosis itself never touches SHAP. `explain=True`
  therefore degrades to `explanation: None` with `explanation_error` set,
  rather than taking down soil_health_score/diagnosis/crop_recommendation,
  none of which depend on SHAP at all.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_LOCAL_MODELS = Path(__file__).resolve().parent / "models" / "structured"
_ROOT_MODELS = Path(__file__).resolve().parents[3] / "models" / "structured"
MODELS_DIR = _LOCAL_MODELS if _LOCAL_MODELS.is_dir() else _ROOT_MODELS

# All 11 soil parameters this pipeline was trained on.
FEATURE_COLS = ["N", "P", "K", "ph", "EC", "S", "Cu", "Fe", "Mn", "Zn", "B"]

# Crop-suitability model trains on a different column set (Kaggle
# Crop_recommendation.csv: N, P, K, temperature, humidity, ph, rainfall) —
# it does not use the micronutrient columns above.
CROP_FEATURE_COLS = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]

# Fallback values when weather inputs aren't supplied, so /analyze doesn't
# break for callers who only send the 11 chemistry parameters. These are
# rough dataset-average placeholders — replace with real weather lookups
# (e.g. an API by field location) if you want this to be more than a stopgap.
DEFAULT_TEMPERATURE = 25.6
DEFAULT_HUMIDITY = 71.5
DEFAULT_RAINFALL = 103.5

# Same threshold bands used in train_deficiency.py — must stay in sync.
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


class ModelsUnavailable(RuntimeError):
    """Raised when the trained artifacts are missing from models/structured."""


class ExplainabilityUnavailable(Exception):
    """Raised when SHAP/numba can't be loaded (e.g. a blocked native DLL).

    Caught at both call sites in this module so a code-integrity policy
    blocking llvmlite.dll degrades explain=True to "not available" instead
    of crashing /analyze entirely.
    """


# --------------------------------------------------------------------------- #
# Artifact loading
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _bundle() -> dict[str, Any]:
    """Load and cache deficiency models, encoders, and the crop suitability model."""
    import joblib
    import xgboost as xgb

    deficiency_models: dict[str, Any] = {}
    for param in FEATURE_COLS:
        path = MODELS_DIR / f"deficiency_{param.lower()}_xgb.json"
        if not path.is_file():
            raise ModelsUnavailable(
                f"Missing artifact: {path.name}. Run app/ml/train_deficiency.py first."
            )
        booster = xgb.XGBClassifier()
        booster.load_model(str(path))
        deficiency_models[param] = booster

    encoders_path = MODELS_DIR / "deficiency_label_encoders.joblib"
    if not encoders_path.is_file():
        raise ModelsUnavailable(f"Missing artifact: {encoders_path.name}")
    deficiency_encoders = joblib.load(encoders_path)

    crop_path = MODELS_DIR / "crop_suitability_model.pkl"
    if not crop_path.is_file():
        raise ModelsUnavailable(
            f"Missing artifact: {crop_path.name}. Run app/ml/train_crop_suitability.py first."
        )
    crop_bundle = joblib.load(crop_path)

    return {
        "deficiency_models": deficiency_models,
        "deficiency_encoders": deficiency_encoders,
        "crop_model": crop_bundle["model"],
        "crop_classes": crop_bundle["classes"],
    }


@lru_cache(maxsize=1)
def _explainers() -> dict[str, Any]:
    """SHAP TreeExplainers, built lazily (construction is not free).

    Raises ExplainabilityUnavailable instead of letting an ImportError/
    OSError (e.g. Windows Smart App Control blocking numba's llvmlite.dll,
    which numba loads unconditionally at import time -- not only when JIT
    compilation is actually used) propagate and crash the whole /analyze
    request.
    """
    try:
        import shap
    except (ImportError, OSError) as e:
        raise ExplainabilityUnavailable(str(e)) from e

    try:
        b = _bundle()
        exp = {param: shap.TreeExplainer(model) for param, model in b["deficiency_models"].items()}
        exp["crop"] = shap.TreeExplainer(b["crop_model"])
        return exp
    except OSError as e:
        raise ExplainabilityUnavailable(str(e)) from e


def models_available() -> bool:
    """True when the trained artifacts can be loaded."""
    try:
        _bundle()
        return True
    except (ModelsUnavailable, OSError):
        return False


# --------------------------------------------------------------------------- #
# Rule engine — the authoritative deficiency classifier
# --------------------------------------------------------------------------- #
def _status_from_threshold(value: float, low: float, high: float) -> str:
    if value < low:
        return "low"
    if value > high:
        return "high"
    return "adequate"


# --------------------------------------------------------------------------- #
# Soil health score
# --------------------------------------------------------------------------- #
def _health_score(diagnosis: dict[str, str]) -> float:
    """Composite 0-100 soil health score.

    Transparent, weighted deduction model rather than a learned regressor — no
    dataset carries a ground-truth "soil health score" to train against.
    Deductions (from 100): each parameter low -> 10, high -> 5, adequate -> 0.
    pH gets double weight (gates nutrient availability generally).
    """
    score = 100.0
    for param, status in diagnosis.items():
        weight = 2.0 if param == "ph" else 1.0
        if status == "low":
            score -= 10.0 * weight
        elif status == "high":
            score -= 5.0 * weight
    return round(max(0.0, min(100.0, score)), 1)


def _health_band(score: float) -> str:
    if score >= 80:
        return "good"
    if score >= 60:
        return "moderate"
    if score >= 40:
        return "poor"
    return "critical"


# --------------------------------------------------------------------------- #
# Degradation risk index
# --------------------------------------------------------------------------- #
def _degradation_risk(
    current_score: float, history: list[dict[str, float]] | None
) -> dict[str, Any]:
    """Degradation risk index in [0, 1] — higher means greater risk."""
    condition_risk = (100.0 - current_score) / 100.0

    if not history or len(history) < 2:
        return {
            "index": round(condition_risk, 3),
            "band": _risk_band(condition_risk),
            "basis": "current_condition_only",
            "trend_slope": None,
            "records_used": len(history) if history else 0,
            "note": (
                "At least two historical soil records for this field are required to "
                "measure a degradation trend. This index reflects current condition only."
            ),
        }

    scores = np.array([h["score"] for h in history], dtype=float)
    x = np.arange(len(scores), dtype=float)
    slope = float(np.polyfit(x, scores, 1)[0])
    trend_risk = float(np.clip(-slope / 10.0, 0.0, 1.0))
    index = float(np.clip(0.6 * condition_risk + 0.4 * trend_risk, 0.0, 1.0))

    return {
        "index": round(index, 3),
        "band": _risk_band(index),
        "basis": "current_condition_and_trend",
        "trend_slope": round(slope, 3),
        "records_used": len(history),
        "note": "Negative trend_slope indicates declining soil health across successive records.",
    }


def _risk_band(index: float) -> str:
    if index < 0.25:
        return "low"
    if index < 0.5:
        return "moderate"
    if index < 0.75:
        return "high"
    return "severe"


# --------------------------------------------------------------------------- #
# SHAP attribution
# --------------------------------------------------------------------------- #
def _shap_attributions(
    target: str,
    frame: pd.DataFrame,
    predicted_idx: int,
    feature_cols: list[str] | None = None,
) -> list[dict]:
    """Per-feature SHAP contributions toward the predicted class, largest first.

    `feature_cols` defaults to FEATURE_COLS (the 11 deficiency-model columns);
    pass CROP_FEATURE_COLS when explaining a crop-model prediction, since that
    model uses a different, 7-column feature frame.

    Raises ExplainabilityUnavailable (propagated from _explainers()) when
    SHAP itself can't be loaded -- callers catch this and degrade rather
    than letting it crash the request.
    """
    b = _bundle()
    target_frame = frame
    if target in b["deficiency_models"]:
        model = b["deficiency_models"][target]
        if hasattr(model, "n_features_in_") and model.n_features_in_ == len(FEATURE_COLS) - 1 and target in frame.columns:
            target_frame = frame.drop(columns=[target])
            cols = [c for c in (feature_cols or FEATURE_COLS) if c != target]
        else:
            cols = feature_cols or FEATURE_COLS
    else:
        cols = feature_cols or (CROP_FEATURE_COLS if target == "crop" else FEATURE_COLS)

    values = _explainers()[target].shap_values(target_frame)
    arr = np.asarray(values)
    if arr.ndim == 3:
        contrib = arr[0, :, predicted_idx]
    elif arr.ndim == 2:
        contrib = arr[0]
    else:  # pragma: no cover - defensive
        contrib = np.ravel(arr)

    out = [
        {
            "feature": f,
            "value": round(float(target_frame.iloc[0][f]), 3),
            "shap_value": round(float(c), 4),
            "direction": "increases" if c > 0 else "decreases",
        }
        for f, c in zip(cols, contrib)
    ]
    out.sort(key=lambda d: abs(d["shap_value"]), reverse=True)
    return out


def _crop_reason(attributions: list[dict]) -> str:
    """Turn the top SHAP contributor(s) into one plain-language sentence."""
    positive = [a for a in attributions if a["direction"] == "increases"][:2]
    if not positive:
        return "No single reading strongly favoured this crop; it fits the overall profile."
    parts = [f"{a['feature']} ({a['value']})" for a in positive]
    return f"Favoured mainly by {', and '.join(parts)}."


# --------------------------------------------------------------------------- #
# Per-parameter model annotation
# --------------------------------------------------------------------------- #
def _annotate(
    param: str, rule_status: str, frame: pd.DataFrame, explain: bool, disagreements: list[str]
) -> dict[str, Any]:
    """Attach model confidence (and optionally SHAP) to a rule-derived status."""
    b = _bundle()
    model = b["deficiency_models"][param]
    classes = b["deficiency_encoders"][param]
    sub_frame = (
        frame.drop(columns=[param])
        if (param in frame.columns and hasattr(model, "n_features_in_") and model.n_features_in_ == len(frame.columns) - 1)
        else frame
    )
    proba = model.predict_proba(sub_frame)[0]
    model_idx = int(np.argmax(proba))
    model_status = classes[model_idx]

    detail: dict[str, Any] = {
        "status": rule_status,
        "source": "threshold_rule",
        "model_status": model_status,
        "model_confidence": round(float(proba[model_idx]), 4),
    }
    if rule_status in classes:
        rule_idx = classes.index(rule_status)
        detail["model_confidence_in_rule_status"] = round(float(proba[rule_idx]), 4)

    if model_status != rule_status:
        disagreements.append(
            f"{param}: rule={rule_status} model={model_status} "
            "(reading is near a threshold boundary; rule applied)"
        )

    if explain:
        try:
            detail["explanation"] = _shap_attributions(param, frame, model_idx)
        except ExplainabilityUnavailable as e:
            detail["explanation"] = None
            detail["explanation_error"] = str(e)

    return detail


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def analyze(
    readings: dict[str, float],
    history: list[dict[str, float]] | None = None,
    explain: bool = False,
    thresholds_override: dict[str, dict[str, float]] | None = None,
    weather: dict[str, float] | None = None,
    recent_crops: list[str] | None = None,
) -> dict[str, Any]:
    """Diagnose one set of soil readings across all 11 parameters.

    Args:
        readings: dict with keys matching FEATURE_COLS (N, P, K, ph, EC, S, Cu,
            Fe, Mn, Zn, B). Missing values are imputed as 0.0 and reported in
            `imputed_features` (a real median-based imputer can replace this
            once training metadata is exported).
        history: [{"score": float}] for this field, oldest first, ending with
            the current reading.
        explain: attach SHAP attributions.
        thresholds_override: soil-type-adjusted threshold bands from
            app/ml/fusion.py (Weeks 3-4, Task A). When supplied, the
            diagnosis is judged against these bands instead of the fixed
            THRESHOLDS above. Falls back to THRESHOLDS when None (fusion
            not requested, or fusion's confidence gate did not fire).
        weather: optional dict with "temperature", "humidity", "rainfall" —
            only used by the crop-suitability model. Missing keys fall back
            to DEFAULT_TEMPERATURE / DEFAULT_HUMIDITY / DEFAULT_RAINFALL.
        recent_crops: this field's previously *recommended* crops, most
            recent first (see app/ml/rotation.py). Optional — when None,
            no rotation check runs and candidates carry no `rotation` key.

    Returns soil_health_score, diagnosis, degradation_risk and a crop
    suitability recommendation.
    """
    b = _bundle()

    imputed: list[str] = []
    row: dict[str, float] = {}
    for f in FEATURE_COLS:
        v = readings.get(f)
        if v is None:
            v = 0.0
            imputed.append(f)
        row[f] = float(v)

    frame = pd.DataFrame([[row[f] for f in FEATURE_COLS]], columns=FEATURE_COLS)

    # Separate feature frame for the crop model — different columns than
    # the deficiency models above (see CROP_FEATURE_COLS).
    weather = weather or {}
    crop_row = {
        "N": row["N"],
        "P": row["P"],
        "K": row["K"],
        "temperature": weather.get("temperature") or DEFAULT_TEMPERATURE,
        "humidity": weather.get("humidity") or DEFAULT_HUMIDITY,
        "ph": row["ph"],
        "rainfall": weather.get("rainfall") or DEFAULT_RAINFALL,
    }
    crop_frame = pd.DataFrame([[crop_row[f] for f in CROP_FEATURE_COLS]], columns=CROP_FEATURE_COLS)

    diagnosis: dict[str, str] = {}
    details: dict[str, Any] = {}
    disagreements: list[str] = []

    # pH is reported to callers using acidic/neutral/alkaline vocabulary
    # (the frontend's PH_STATUS map keys on these), while every other
    # parameter uses low/adequate/high. _annotate() still receives the
    # generic rule_status so it compares correctly against the deficiency
    # model's own low/adequate/high classes -- only the value written into
    # `diagnosis` (what callers actually read) is remapped for pH.
    PH_STATUS_MAP = {"low": "acidic", "adequate": "neutral", "high": "alkaline"}

    active_thresholds = thresholds_override or THRESHOLDS
    for param, bounds in active_thresholds.items():
        rule = _status_from_threshold(row[param], bounds["low"], bounds["high"])
        diagnosis[param] = PH_STATUS_MAP[rule] if param == "ph" else rule
        details[param] = _annotate(param, rule, frame, explain, disagreements)

    score = _health_score(diagnosis)
    risk = _degradation_risk(score, history)

    # --- Crop suitability (top 3) ---
    crop_model = b["crop_model"]
    crop_classes = b["crop_classes"]
    proba = crop_model.predict_proba(crop_frame)[0]
    order = np.argsort(proba)[::-1][:3]

    top_crops = []
    for i in order:
        entry = {"crop": str(crop_classes[i]), "confidence": round(float(proba[i]), 4)}
        if explain:
            try:
                attributions = _shap_attributions(
                    "crop", crop_frame, int(i), feature_cols=CROP_FEATURE_COLS
                )
                entry["explanation"] = attributions
                entry["reason"] = _crop_reason(attributions)
            except ExplainabilityUnavailable as e:
                entry["explanation"] = None
                entry["explanation_error"] = str(e)
        top_crops.append(entry)

    if recent_crops:
        from app.ml.rotation import apply_rotation_check
        top_crops = apply_rotation_check(top_crops, recent_crops)

    crop_recommendation = {
        "recommended": top_crops[0]["crop"],
        "recommended_detail": top_crops[0],
        "alternatives": top_crops[1:],
    }

    return {
        "soil_health_score": score,
        "health_band": _health_band(score),
        "diagnosis": diagnosis,
        "diagnosis_detail": details,
        "degradation_risk": risk,
        "crop_recommendation": crop_recommendation,
        "inputs_used": row,
        "imputed_features": imputed,
        "thresholds_used": active_thresholds,
        "model_agreement": {
            "rule_is_authoritative": True,
            "disagreements": disagreements,
        },
    }