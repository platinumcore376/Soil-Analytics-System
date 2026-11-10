"""Hybrid fusion: soil-type prediction (CNN) adjusts nutrient thresholds
used by the structured deficiency diagnosis (Weeks 3-4, Task A).
"""
from __future__ import annotations
from typing import Any

# Multipliers applied to the structured.py THRESHOLDS bands.
# Keys must match the CNN's actual class names (see app/ml/train_cnn.py's
# class_names output — includes the "_Soil" suffix).
# pH is intentionally never adjusted -- soil type doesn't change what
# pH means chemically. Classes with no agronomic basis for adjustment
# (Arid, Mountain, Yellow) are omitted rather than guessed.
SOIL_TYPE_ADJUSTMENTS: dict[str, dict[str, float]] = {
    "Alluvial_Soil": {"N": 0.90, "P": 0.90, "K": 0.95},
    "Black_Soil":    {"N": 1.10, "P": 1.15, "K": 0.80},
    "Red_Soil":      {"N": 1.15, "P": 1.15, "K": 1.00},
    "Laterite_Soil": {"N": 1.20, "P": 1.25, "K": 1.10},
}

MIN_CONFIDENCE = 0.70
MIN_RECALL = 0.90

# Real per-class recall, measured from app/ml/train_cnn.py's classification
# report on the held-out validation set (7-class run, 1189 images).
# NOTE: Alluvial_Soil (0.62) and Laterite_Soil (0.82) fall below MIN_RECALL,
# so fusion will not apply for those classes even at high CNN confidence —
# this is the confidence gate working as intended, not a bug. Only
# Black_Soil currently clears the recall bar.
PER_CLASS_RECALL: dict[str, float] = {
    "Alluvial_Soil": 0.62,
    "Black_Soil": 0.95,
    "Red_Soil": 0.89,
    "Laterite_Soil": 0.82,
}


def apply_fusion(
    soil_type: str,
    cnn_confidence: float,
    baseline_thresholds: dict[str, dict[str, float]],
    per_class_recall: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Decide whether to adjust nutrient thresholds based on the CNN's
    soil-type prediction, and produce the adjusted bands if so.

    Returns a dict with `applied` (bool). If False, `reason` explains why
    and `thresholds_used` falls back to the unmodified baseline -- callers
    should always read `thresholds_used`, not `baseline_thresholds`, when
    re-checking the diagnosis.
    """
    recall_table = per_class_recall or PER_CLASS_RECALL
    reason = None

    if soil_type not in SOIL_TYPE_ADJUSTMENTS:
        reason = f"no threshold adjustment defined for soil type '{soil_type}'"
    elif cnn_confidence < MIN_CONFIDENCE:
        reason = f"CNN confidence {cnn_confidence:.2f} below minimum {MIN_CONFIDENCE}"
    elif recall_table.get(soil_type, 0.0) < MIN_RECALL:
        reason = (
            f"'{soil_type}' class recall "
            f"{recall_table.get(soil_type, 0.0):.2f} below minimum {MIN_RECALL}"
        )

    if reason:
        return {
            "applied": False,
            "reason": reason,
            "soil_type": soil_type,
            "cnn_confidence": round(float(cnn_confidence), 4),
            "thresholds_used": baseline_thresholds,
        }

    mult = SOIL_TYPE_ADJUSTMENTS[soil_type]
    adjusted: dict[str, dict[str, float]] = {}
    for param, band in baseline_thresholds.items():
        if param == "ph":
            adjusted[param] = band
            continue
        m = mult.get(param, 1.0)
        adjusted[param] = {"low": band["low"] * m, "high": band["high"] * m}

    return {
        "applied": True,
        "soil_type": soil_type,
        "cnn_confidence": round(float(cnn_confidence), 4),
        "threshold_multipliers": mult,
        "thresholds_baseline": baseline_thresholds,
        "thresholds_used": adjusted,
    }