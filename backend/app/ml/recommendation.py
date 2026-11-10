"""Knowledge-based fertilizer recommendation engine (Weeks 5-6, deliverable 1).

Documentation requirement (page 2):
    "Build a knowledge-based recommendation engine mapping diagnosed deficiencies to
     specific fertilizer formulations, dosages, and application schedules."

WHY DOSAGES ARE COMPUTED, NOT LOOKED UP
---------------------------------------
Phase 2 already returns a fertilizer NAME and advisory text from the XGBoost model. This
deliverable additionally needs dosages and schedules, and neither dataset contains them —
verified: 0 of 3,100 `Remark` strings in fertilizer_recommendation.csv mention a kg/ha
figure.

So dosage is derived by nutrient budgeting, the standard agronomic method:

    deficit (kg/ha)     = target - current_reading
    nutrient needed     = deficit x area_hectares
    product mass (kg)   = nutrient needed / nutrient_content_fraction

Product nutrient contents below are fixed chemistry (Urea is 46% N by formula), not
estimates. The uncertain input is the TARGET level, which is why targets are taken from
the same threshold bands the diagnosis uses — so a "low" verdict and its dose always agree.
"""
from __future__ import annotations

from typing import Any

# --------------------------------------------------------------------------- #
# Product catalogue — nutrient content as a mass fraction
# --------------------------------------------------------------------------- #
# Values are standard commercial analyses. P and K are expressed as elemental P and K
# (not P2O5 / K2O) so they can be compared directly against soil-test readings, which
# Indian Soil Health Cards report elementally.
#
#   P2O5 -> P  x 0.436        K2O -> K  x 0.830
PRODUCTS: dict[str, dict[str, Any]] = {
    "Urea": {
        "content": {"nitrogen": 0.46},
        "kind": "nutrient",
        "note": "46% N. Highest-analysis straight nitrogen fertilizer.",
    },
    "DAP": {
        # 18-46-0 -> N 0.18, P 0.46 * 0.436
        "content": {"nitrogen": 0.18, "phosphorus": 0.201},
        "kind": "nutrient",
        "note": "Di-ammonium phosphate, 18-46-0. Supplies P with starter N.",
    },
    "SSP": {
        # 0-16-0
        "content": {"phosphorus": 0.070},
        "kind": "nutrient",
        "note": "Single super phosphate, 0-16-0. Also supplies sulphur and calcium.",
    },
    "Muriate of Potash": {
        # 0-0-60
        "content": {"potassium": 0.498},
        "kind": "nutrient",
        "note": "MOP (KCl), 0-0-60. Standard potassium source.",
    },
    "Balanced NPK Fertilizer": {
        # 10-26-26
        "content": {"nitrogen": 0.10, "phosphorus": 0.113, "potassium": 0.216},
        "kind": "nutrient",
        "note": "Complex 10-26-26. Use when two or more nutrients are low.",
    },
    "Compost": {
        "content": {"nitrogen": 0.005, "phosphorus": 0.002, "potassium": 0.005},
        "kind": "organic",
        "note": "Bulk organic amendment. Raises organic matter and structure.",
    },
    "Organic Fertilizer": {
        "content": {"nitrogen": 0.015, "phosphorus": 0.007, "potassium": 0.012},
        "kind": "organic",
        "note": "Processed organic source. Slower release than mineral fertilizer.",
    },
    # Amendments correct pH; they supply no NPK and are dosed by area, not deficit.
    "Lime": {
        "content": {},
        "kind": "amendment",
        "note": "Raises pH in acidic soils. Apply 2-4 weeks before sowing.",
    },
    "Gypsum": {
        "content": {},
        "kind": "amendment",
        "note": "Lowers pH / reclaims sodic soils. Supplies calcium and sulphur.",
    },
}

# Split-application schedules. Nitrogen leaches and is never applied in one dose;
# phosphorus is immobile so all of it goes in at sowing.
SCHEDULES: dict[str, list[dict[str, Any]]] = {
    "nitrogen": [
        {"stage": "basal", "day": 0, "share": 0.50},
        {"stage": "top_dress_1", "day": 30, "share": 0.25},
        {"stage": "top_dress_2", "day": 60, "share": 0.25},
    ],
    "phosphorus": [
        {"stage": "basal", "day": 0, "share": 1.00},
    ],
    "potassium": [
        {"stage": "basal", "day": 0, "share": 0.50},
        {"stage": "top_dress_1", "day": 40, "share": 0.50},
    ],
}

# Lime / gypsum rates by pH severity, tonnes per hectare converted to kg.
# Indicative rates for a medium-textured soil; clay soils need more.
AMENDMENT_RATES = {
    "lime": [
        (5.0, 5000.0, "strongly acidic"),
        (5.5, 3000.0, "moderately acidic"),
        (6.0, 2000.0, "slightly acidic"),
    ],
    "gypsum": [
        (8.5, 4000.0, "strongly alkaline"),
        (8.0, 2500.0, "moderately alkaline"),
        (7.5, 1500.0, "slightly alkaline"),
    ],
}

# Which single product to prefer for one deficient nutrient.
PREFERRED: dict[str, str] = {
    "nitrogen": "Urea",
    "phosphorus": "DAP",
    "potassium": "Muriate of Potash",
}


def _target_level(nutrient: str, thresholds: dict[str, dict[str, float]]) -> float:
    """Target = midpoint of the adequate band.

    Aiming at the band's lower edge would leave the soil one rainfall away from being
    deficient again; aiming at the top wastes fertilizer and risks runoff.
    """
    band = thresholds[nutrient]
    return (band["low"] + band["high"]) / 2.0


def _schedule_for(nutrient: str, total_kg: float | None) -> list[dict[str, Any]]:
    """Expand a split schedule, with per-split masses when the total is known.

    The last split absorbs any rounding remainder so the splits always sum to exactly
    the stated total — a farmer told "63.0 kg" must not be handed instalments adding to
    63.1.
    """
    splits = SCHEDULES[nutrient]
    out = []
    running = 0.0
    for i, split in enumerate(splits):
        entry = dict(split)
        if total_kg is None:
            entry["kg"] = None
        elif i == len(splits) - 1:
            entry["kg"] = round(total_kg - running, 1)
        else:
            kg = round(total_kg * split["share"], 1)
            running += kg
            entry["kg"] = kg
        out.append(entry)
    return out


def _schedule_nutrient(content: dict[str, float], fallback: str, kind: str) -> str:
    """Pick which nutrient's split schedule a product should follow.

    A MINERAL product containing nitrogen must be split across the season — nitrogen
    leaches, so a single basal dose of a complex fertilizer wastes the N it carries
    regardless of which nutrient sized the dose.

    ORGANIC sources are exempt: their nitrogen is bound in organic matter and mineralises
    slowly over months, so it does not leach. Splitting a 12-tonne compost application
    into three trips would also be absurd in practice. They go in whole, pre-sowing.
    """
    if kind == "organic":
        return "phosphorus"  # single 100% basal dose
    if content.get("nitrogen"):
        return "nitrogen"
    return fallback if fallback in SCHEDULES else "phosphorus"


def _amendment(ph: float | None) -> dict[str, Any] | None:
    """Lime or gypsum recommendation from pH, or None when pH is in range."""
    if ph is None:
        return None

    if ph < 6.0:
        for limit, rate, severity in AMENDMENT_RATES["lime"]:
            if ph < limit:
                return {
                    "product": "Lime",
                    "reason": f"pH {ph} is {severity}",
                    "kg_per_hectare": rate,
                    "timing": "2-4 weeks before sowing",
                    "note": PRODUCTS["Lime"]["note"],
                }
    elif ph > 7.5:
        for limit, rate, severity in AMENDMENT_RATES["gypsum"]:
            if ph > limit:
                return {
                    "product": "Gypsum",
                    "reason": f"pH {ph} is {severity}",
                    "kg_per_hectare": rate,
                    "timing": "2-4 weeks before sowing",
                    "note": PRODUCTS["Gypsum"]["note"],
                }
    return None


def _deficits(
    deficient: list[str],
    readings: dict[str, float],
    thresholds: dict[str, dict[str, float]],
) -> dict[str, float]:
    """Per-nutrient shortfall against the target level, in kg/ha."""
    out: dict[str, float] = {}
    for nutrient in deficient:
        reading = readings.get(nutrient)
        if reading is None:
            continue
        deficit = _target_level(nutrient, thresholds) - float(reading)
        if deficit > 0:
            out[nutrient] = round(deficit, 1)
    return out


def recommend(
    diagnosis: dict[str, str],
    readings: dict[str, float],
    thresholds: dict[str, dict[str, float]],
    area_hectares: float | None = None,
    advisories: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the fertilizer plan for one diagnosis.

    Args:
        diagnosis: per-nutrient status from the analysis (`low`/`adequate`/`high`, and
            `acidic`/`neutral`/`alkaline` for pH).
        readings: the lab values the diagnosis was based on.
        thresholds: the NPK bands actually used — the fused, soil-type-specific bands
            when fusion applied, so dose and verdict cannot disagree.
        area_hectares: field area. When None, only per-hectare rates are returned.
        advisories: optional fertilizer -> farmer-facing text, from the trained model.

    Returns products with dosages and split schedules, plus any pH amendment.
    """
    advisories = advisories or {}
    deficient = [
        n for n in ("nitrogen", "phosphorus", "potassium") if diagnosis.get(n) == "low"
    ]
    excessive = [
        n for n in ("nitrogen", "phosphorus", "potassium") if diagnosis.get(n) == "high"
    ]

    products: list[dict[str, Any]] = []
    deficits = _deficits(deficient, readings, thresholds)

    def _add(product_name: str, targets: list[str], kg_per_ha: float, basis: str,
             supplies: dict[str, float], advisory: str | None = None) -> None:
        spec = PRODUCTS[product_name]
        total = None if area_hectares is None else round(kg_per_ha * area_hectares, 1)
        # Schedule follows nitrogen whenever the product contains any, so a complex
        # fertilizer's N is not dumped in one basal dose and lost to leaching.
        sched_nutrient = _schedule_nutrient(spec["content"], basis, spec["kind"])
        products.append(
            {
                "product": product_name,
                "kind": spec["kind"],
                "targets": targets,
                "nutrient_deficit_kg_per_ha": {n: deficits[n] for n in targets if n in deficits},
                "product_analysis": spec["content"],
                "supplies_kg_per_ha": supplies,
                "kg_per_hectare": round(kg_per_ha, 1),
                "total_product_kg": total,
                "schedule": _schedule_for(
                    sched_nutrient, total if total is not None else round(kg_per_ha, 1)
                ),
                "schedule_basis": sched_nutrient,
                "dose_limited_by": basis,
                "advisory": advisory or advisories.get(product_name, spec["note"]),
            }
        )

    if len(deficits) >= 2:
        # Two or more deficiencies: one complex fertilizer is fewer bags to buy and
        # carry. Size it on the LIMITING nutrient — the one needing the least product —
        # so nothing is over-applied, then top up the remainder with straight
        # fertilizers. Sizing on the largest requirement (a max()) would overshoot the
        # other nutrients, which is wasteful and a runoff risk.
        complex_content = PRODUCTS["Balanced NPK Fertilizer"]["content"]
        covered = [n for n in deficits if n in complex_content]

        limiting = min(covered, key=lambda n: deficits[n] / complex_content[n])
        complex_kg = deficits[limiting] / complex_content[limiting]
        supplied = {n: round(complex_kg * complex_content[n], 1) for n in covered}

        _add("Balanced NPK Fertilizer", covered, complex_kg, limiting, supplied)

        # Whatever the complex under-delivers gets a straight fertilizer.
        for nutrient in covered:
            shortfall = deficits[nutrient] - supplied[nutrient]
            if shortfall <= 1.0:  # within rounding — not worth another bag
                continue
            straight = PREFERRED[nutrient]
            kg = shortfall / PRODUCTS[straight]["content"][nutrient]
            _add(
                straight,
                [nutrient],
                kg,
                nutrient,
                {nutrient: round(shortfall, 1)},
                advisory=(
                    f"Top-up: the complex fertilizer supplies {supplied[nutrient]} kg/ha "
                    f"of {nutrient}, leaving {round(shortfall, 1)} kg/ha to make up."
                ),
            )
    else:
        for nutrient, deficit in deficits.items():
            straight = PREFERRED[nutrient]
            kg = deficit / PRODUCTS[straight]["content"][nutrient]
            _add(straight, [nutrient], kg, nutrient, {nutrient: deficit})

    # Low organic matter is an amendment case, not a nutrient deficit. Compost is dosed
    # by area at a bulk rate, and goes in whole before sowing — its nitrogen is bound in
    # organic matter and mineralises slowly, so it does not leach like urea.
    organic_matter = readings.get("organic_matter")
    if organic_matter is not None and organic_matter < 0.75:
        _add(
            "Compost",
            ["organic_matter"],
            5000.0,
            "phosphorus",  # single basal dose
            {},
            advisory=(
                f"Organic matter is {organic_matter}%, below the 0.75% guideline. "
                "Compost improves structure, water holding and nutrient retention."
            ),
        )

    amendment = _amendment(readings.get("ph"))

    return {
        "field_area_hectares": area_hectares,
        "deficient_nutrients": deficient,
        "excessive_nutrients": excessive,
        "products": products,
        "amendments": [amendment] if amendment else [],
        "targets_used": {
            n: round(_target_level(n, thresholds), 1)
            for n in ("nitrogen", "phosphorus", "potassium")
        },
        "thresholds_used": thresholds,
        "warnings": (
            [
                f"{n} is already high; applying more risks runoff and lock-out of "
                "other nutrients."
                for n in excessive
            ]
        ),
        "notes": [
            "Nitrogen is split across the season because it leaches; phosphorus goes in "
            "entirely at sowing because it is immobile in soil.",
            "Dosages are computed from the nutrient deficit using standard product "
            "analyses, since no dosage figures exist in the source datasets.",
        ],
        "caveat": (
            "Rates are indicative and assume a medium-textured soil. Calibrate against "
            "local ICAR / Soil Health Card recommendations before advising farmers."
        ),
        "method": "deficit_based_nutrient_budgeting",
    }
