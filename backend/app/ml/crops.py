"""Crop suitability ranking (Weeks 5-6, deliverable 2).

Documentation requirement (page 2):
    "Develop a crop suitability ranking module that matches soil health profiles to a
     curated crop-soil compatibility database."

THE COMPATIBILITY DATABASE
--------------------------
models/structured/crop_compatibility.json — 22 crops x 4 parameters (N, P, K, pH),
generated from data/crop_recommendation.csv (100 samples per crop).

Bands are the 10th-90th percentile of observed values, not min/max: the extremes include
outliers that would make every band look permissive and every crop look suitable.

These are OBSERVED ranges from a dataset, not published agronomic optima. Good enough to
rank crops relative to one another; not a substitute for regional ICAR guidance.

WHY NOT REUSE THE PHASE 2 XGBOOST CROP MODEL
--------------------------------------------
That model returns a single best crop with a probability. The requirement asks for a
RANKING, and a farmer needs to know *why* a crop scored badly. A transparent distance
score gives both: every crop gets a score, and the limiting parameter is named
("potassium 45 kg/ha, but apple needs 196-205").
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = REPO_ROOT / "models" / "structured" / "crop_compatibility.json"

PARAMETERS = ("nitrogen", "phosphorus", "potassium", "ph")

# pH is weighted double: it gates nutrient availability regardless of how much nutrient
# is present. A crop can tolerate slightly low potassium; it cannot tolerate a pH that
# locks phosphorus out of solution.
WEIGHTS = {"nitrogen": 1.0, "phosphorus": 1.0, "potassium": 1.0, "ph": 2.0}

SUITABILITY_BANDS = (
    (0.85, "excellent"),
    (0.70, "good"),
    (0.50, "moderate"),
    (0.30, "marginal"),
)


class CompatibilityUnavailable(RuntimeError):
    """Raised when the crop compatibility database is missing."""


@lru_cache(maxsize=1)
def _database() -> dict[str, Any]:
    if not DB_PATH.is_file():
        raise CompatibilityUnavailable(
            f"Crop compatibility database not found at {DB_PATH}. "
            "Regenerate it from data/crop_recommendation.csv."
        )
    return json.loads(DB_PATH.read_text(encoding="utf-8"))


def database_available() -> bool:
    try:
        _database()
        return True
    except (CompatibilityUnavailable, OSError):
        return False


def database_info() -> dict[str, Any]:
    db = _database()
    return {
        "source": db.get("source"),
        "method": db.get("method"),
        "crops": db.get("crops"),
        "parameters": db.get("parameters"),
        "note": db.get("note"),
    }


def _score_parameter(reading: float, band: dict[str, float]) -> float:
    """Score one parameter against a crop's tolerance band, in [0, 1].

    Inside the band scores 1.0. Outside, the score falls linearly with distance from the
    nearest edge, reaching 0 one band-width away. Using band width as the scale means a
    crop with a wide tolerance is penalised gently and a fussy crop is penalised sharply,
    which is the behaviour we want.
    """
    low, high = band["low"], band["high"]
    if low <= reading <= high:
        return 1.0

    width = high - low
    if width <= 0:  # degenerate band — fall back to a proportional tolerance
        width = max(abs(low), 1.0) * 0.1

    distance = (low - reading) if reading < low else (reading - high)
    return max(0.0, 1.0 - distance / width)


def _band_label(score: float) -> str:
    for threshold, label in SUITABILITY_BANDS:
        if score >= threshold:
            return label
    return "poor"


def _limiting_factor(
    crop: str, scores: dict[str, float], readings: dict[str, float],
    bands: dict[str, Any],
) -> str | None:
    """Name the worst-scoring parameter in farmer-readable terms."""
    off = {p: s for p, s in scores.items() if s < 0.999}
    if not off:
        return None

    worst = min(off, key=lambda p: off[p])
    band = bands[worst]
    reading = readings[worst]
    unit = "" if worst == "ph" else " kg/ha"
    direction = "below" if reading < band["low"] else "above"
    return (
        f"{worst} {reading}{unit} is {direction} the {band['low']}-{band['high']}"
        f"{unit} range {crop} prefers"
    )



# --------------------------------------------------------------------------- #
# Soil-type affinity (uses the CNN's output)
# --------------------------------------------------------------------------- #
# WHY THIS EXISTS
# The compatibility bands above come from N/P/K/pH only, so before this the crop ranking
# ignored soil type entirely — the CNN's prediction reached the nutrient thresholds in
# fusion.py and nowhere else. That is a real omission: soil type governs drainage, depth and
# water-holding capacity, which decide crop choice at least as much as nutrient levels do.
# Cotton on Black (regur) cotton soil and cotton on shallow Laterite are not the same
# proposition at identical N/P/K.
#
# WHAT THESE NUMBERS ARE — AND ARE NOT
# Multipliers on the nutrient-derived score, expressing the classical Indian soil-type/crop
# associations (ICAR / state agriculture department extension guidance): Black soil for
# cotton and pulses, Alluvial for rice and wheat, Laterite for plantation and tree crops,
# Red for millets, groundnut and pulses.
#
# They are EDITORIAL, not fitted from data — the crop dataset carries no soil-type column, so
# there is nothing here to train on. They are deliberately gentle (0.85-1.15, i.e. +/-15%)
# so they re-order crops of similar nutrient fit without ever promoting a crop the chemistry
# rules out. Anything absent scores 1.0 (neutral) rather than being penalised for absence.
SOIL_TYPE_AFFINITY: dict[str, dict[str, float]] = {
    "Alluvial": {
        # Deep, fertile, well-watered — the Indo-Gangetic staple belt.
        "rice": 1.15, "maize": 1.10, "jute": 1.15, "banana": 1.10,
        "muskmelon": 1.05, "watermelon": 1.05, "papaya": 1.05,
        "lentil": 1.05, "chickpea": 1.05,
        "coffee": 0.85,  # needs slope and shade, not river plain
    },
    "Black": {
        # Regur: high clay, swells when wet, retains moisture — classic cotton soil.
        "cotton": 1.15, "pigeonpeas": 1.10, "chickpea": 1.10, "blackgram": 1.10,
        "mungbean": 1.05, "mothbeans": 1.05, "grapes": 1.05, "orange": 1.05,
        "rice": 0.90,     # drainage works against paddy outside bunded fields
        "coconut": 0.85,  # poor drainage is bad for palm roots
    },
    "Red": {
        # Light-textured, low in nitrogen, drains freely — millets and pulses country.
        "mothbeans": 1.15, "blackgram": 1.10, "mungbean": 1.10, "pigeonpeas": 1.10,
        "groundnut": 1.15, "mango": 1.05, "pomegranate": 1.05,
        "rice": 0.90, "jute": 0.85,
    },
    "Laterite": {
        # Leached, acidic, often shallow — plantation and hardy tree crops.
        "coffee": 1.15, "coconut": 1.15, "cashew": 1.15, "mango": 1.05,
        "pomegranate": 1.05, "banana": 1.05,
        "rice": 0.85, "chickpea": 0.85, "lentil": 0.85,  # poor on leached acidic ground
    },
}

# Bound on the adjustment, so a soil-type note can never override the chemistry.
AFFINITY_MIN, AFFINITY_MAX = 0.85, 1.15


def soil_type_affinity(crop: str, soil_type: str | None) -> float:
    """Multiplier for `crop` on `soil_type`; 1.0 when unknown or not listed."""
    if not soil_type:
        return 1.0
    factor = SOIL_TYPE_AFFINITY.get(soil_type, {}).get(crop, 1.0)
    return max(AFFINITY_MIN, min(AFFINITY_MAX, factor))


def rank(
    readings: dict[str, float | None],
    top_k: int | None = None,
    soil_type: str | None = None,
) -> dict[str, Any]:
    """Rank every crop in the database against one soil profile.

    Args:
        readings: soil values. Only nitrogen, phosphorus, potassium and ph are used;
            anything else is ignored. Missing parameters are excluded from scoring and
            reported, rather than imputed — imputing would invent a match.
        top_k: truncate the ranked list. None returns all crops.

    Returns the ranked list, each entry carrying its per-parameter scores and the
    limiting factor when it is not a clean match.
    """
    db = _database()
    compat = db["compatibility"]

    usable = {p: float(readings[p]) for p in PARAMETERS if readings.get(p) is not None}
    missing = [p for p in PARAMETERS if p not in usable]

    if not usable:
        return {
            "ranked_crops": [],
            "top_crops": [],
            "parameters_used": [],
            "parameters_missing": list(PARAMETERS),
            "error": (
                "No usable soil parameters supplied. At least one of "
                f"{', '.join(PARAMETERS)} is required."
            ),
            "database": database_info(),
        }

    ranked: list[dict[str, Any]] = []
    for crop, bands in compat.items():
        scores = {p: _score_parameter(usable[p], bands[p]) for p in usable}

        weight_total = sum(WEIGHTS[p] for p in scores)
        weighted = sum(scores[p] * WEIGHTS[p] for p in scores) / weight_total

        # Soil-type nudge, applied AFTER the nutrient score and clamped to [0, 1]. Both the
        # pre-adjustment score and the factor are reported so a reviewer can see exactly what
        # the photo changed — a hidden multiplier would make the ranking unfalsifiable.
        factor = soil_type_affinity(crop, soil_type)
        adjusted = max(0.0, min(1.0, weighted * factor))

        ranked.append(
            {
                "crop": crop,
                "suitability": round(adjusted, 4),
                "band": _band_label(adjusted),
                "suitability_from_nutrients": round(weighted, 4),
                "soil_type_factor": round(factor, 3),
                "parameter_scores": {p: round(s, 3) for p, s in scores.items()},
                "limiting_factor": _limiting_factor(crop, scores, usable, bands),
                "optimal_bands": {
                    p: {"low": bands[p]["low"], "high": bands[p]["high"]} for p in scores
                },
            }
        )

    # Ties broken alphabetically so the ordering is deterministic across calls.
    ranked.sort(key=lambda r: (-r["suitability"], r["crop"]))
    if top_k is not None:
        ranked = ranked[:top_k]

    return {
        "ranked_crops": ranked,
        "top_crops": [r["crop"] for r in ranked[:3]],
        "parameters_used": sorted(usable),
        "parameters_missing": missing,
        "weights": {p: WEIGHTS[p] for p in usable},
        "readings_used": usable,
        "method": (
            "weighted_distance_from_optimal_band"
            + ("_with_soil_type_affinity" if soil_type else "")
        ),
        "soil_type_used": soil_type,
        "notes": [
            "pH is weighted double — it gates nutrient availability regardless of "
            "nutrient concentration.",
            "Missing parameters are excluded from scoring rather than imputed; imputing "
            "would fabricate a match the soil data does not support.",
            *(
                [
                    f"Soil type '{soil_type}' applied a +/-15% affinity nudge on top of the "
                    "nutrient score. `suitability_from_nutrients` is the unadjusted value and "
                    "`soil_type_factor` the multiplier, so the effect is auditable. These "
                    "factors express classical Indian soil-type/crop associations and are "
                    "editorial, not fitted — the crop dataset has no soil-type column."
                ]
                if soil_type
                else []
            ),
        ],
        "caveat": (
            "Bands are observed ranges from crop_recommendation.csv, not published "
            "agronomic optima. Use for relative ranking, not absolute planting advice."
        ),
        "database": database_info(),
    }
