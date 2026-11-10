"""Fertilizer dosage calculator.

Turns a deficiency diagnosis into concrete application amounts and a
split schedule (basal + top-dress), matching standard agronomic practice.

These are illustrative rates based on common ICAR/extension guidance for
correcting a "low" status back toward "adequate" -- not calibrated against
a specific regional soil test correlation. State this caveat in any report.

Severity scaling: the flat correction rates below are the amount needed
for a reading *just* under the low threshold. A reading far below
threshold needs more product, not the same flat dose. Each application's
`total_kg` is scaled by a `severity_multiplier` in [1.0, 2.0]:

    severity_multiplier = 1.0 at the threshold boundary (mildly low)
    severity_multiplier = 2.0 at <=50% of the threshold (severely low)
    linearly interpolated in between

This is an editorial choice (double the flat rate at half-threshold), not
a fitted or literature-sourced curve -- documented here so it isn't
mistaken for calibrated agronomy. Replace with a real dose-response curve
if/when one is available.
"""
from __future__ import annotations

from typing import Any

# kg of product per hectare needed to correct a "low" status, by product.
# DAP (18-46-0) mainly supplies P; Urea (46-0-0) supplies N; MOP (0-0-60) supplies K.
# These are the BASE rates at severity_multiplier == 1.0 (mildly low, i.e.
# just under threshold) -- calculate_dosage() scales them up for readings
# that are further below threshold.
_CORRECTION_RATES = {
    "urea_low_n": 120.0,     # kg/ha urea when nitrogen is low
    "dap_low_p": 130.0,      # kg/ha DAP when phosphorus is low
    "mop_low_k": 80.0,       # kg/ha MOP when potassium is low
    "compost_om_low": 8000.0,  # kg/ha compost when organic matter is deficient
    "lime_acidic": 2000.0,   # kg/ha lime when pH is acidic
    "gypsum_alkaline": 1500.0,  # kg/ha gypsum when pH is alkaline
}

# Multiplier is 1.0 at the threshold boundary and MAX_SEVERITY_MULTIPLIER
# at or below FLOOR_RATIO of the threshold (or, for pH, at or beyond
# PH_SEVERITY_SPAN past the boundary).
MAX_SEVERITY_MULTIPLIER = 2.0
FLOOR_RATIO = 0.5
PH_SEVERITY_SPAN = 1.0  # pH units past the boundary that reach max severity


def _nutrient_severity_multiplier(value: float, low: float) -> float:
    """Scale factor for a low N/P/K/etc. reading.

    ratio = 1.0 right at the threshold (mildly low) -> multiplier 1.0
    ratio = FLOOR_RATIO or below (severely low)      -> multiplier MAX
    linear in between, clamped to [1.0, MAX_SEVERITY_MULTIPLIER].
    """
    if low <= 0:
        return 1.0
    ratio = value / low
    if ratio >= 1.0:
        return 1.0
    if ratio <= FLOOR_RATIO:
        return MAX_SEVERITY_MULTIPLIER
    # linear interpolation between (ratio=1.0 -> 1.0) and (ratio=FLOOR_RATIO -> MAX)
    span = 1.0 - FLOOR_RATIO
    frac = (1.0 - ratio) / span
    return round(1.0 + frac * (MAX_SEVERITY_MULTIPLIER - 1.0), 3)


def _ph_severity_multiplier(value: float, bound: float) -> float:
    """Scale factor for an out-of-range pH reading, based on distance past the bound."""
    distance = abs(value - bound)
    frac = min(distance / PH_SEVERITY_SPAN, 1.0)
    return round(1.0 + frac * (MAX_SEVERITY_MULTIPLIER - 1.0), 3)


def _scaled_total(base_rate: float, multiplier: float) -> float:
    return round(base_rate * multiplier, 1)


def calculate_dosage(
    diagnosis: dict[str, str],
    readings: dict[str, float] | None = None,
    thresholds: dict[str, dict[str, float]] | None = None,
) -> list[dict[str, Any]]:
    """Return a list of recommended applications based on the diagnosis.

    Args:
        diagnosis: {param: "low"|"adequate"|"high"}, as produced by
            structured.analyze() (e.g. diagnosis["N"] == "low").
        readings: the actual parameter values (structured.py's `row`), used
            to scale dosage by severity. When omitted, falls back to the
            flat rate at multiplier 1.0 for backward compatibility.
        thresholds: the threshold bands used to produce `diagnosis` --
            pass structured.THRESHOLDS, or the fusion-adjusted
            thresholds_override if that was used for this analysis, so
            severity is judged against the same bounds the diagnosis was.
            Falls back to structured.THRESHOLDS-shaped defaults being
            unavailable -> multiplier 1.0 if omitted.

    Each item: {product, total_kg, unit, severity_multiplier, schedule: [...], note}
    """
    readings = readings or {}
    thresholds = thresholds or {}
    applications: list[dict[str, Any]] = []

    def nutrient_multiplier(param: str) -> float:
        value = readings.get(param)
        bounds = thresholds.get(param)
        if value is None or bounds is None:
            return 1.0
        return _nutrient_severity_multiplier(float(value), float(bounds["low"]))

    if diagnosis.get("N") == "low":
        mult = nutrient_multiplier("N")
        total = _scaled_total(_CORRECTION_RATES["urea_low_n"], mult)
        applications.append({
            "product": "Urea",
            "total_kg": total,
            "unit": "kg/ha",
            "severity_multiplier": mult,
            "schedule": [
                {"stage": "basal day 0", "kg": round(total * 0.5, 1)},
                {"stage": "top dress day 30", "kg": round(total * 0.25, 1)},
                {"stage": "top dress day 60", "kg": round(total * 0.25, 1)},
            ],
            "note": "Split application reduces leaching loss versus a single basal dose.",
        })

    if diagnosis.get("P") == "low":
        mult = nutrient_multiplier("P")
        total = _scaled_total(_CORRECTION_RATES["dap_low_p"], mult)
        applications.append({
            "product": "DAP",
            "total_kg": total,
            "unit": "kg/ha",
            "severity_multiplier": mult,
            "schedule": [{"stage": "basal day 0", "kg": total}],
            "note": "Phosphorus is largely immobile in soil -- apply fully at planting.",
        })

    if diagnosis.get("K") == "low":
        mult = nutrient_multiplier("K")
        total = _scaled_total(_CORRECTION_RATES["mop_low_k"], mult)
        applications.append({
            "product": "MOP (Muriate of Potash)",
            "total_kg": total,
            "unit": "kg/ha",
            "severity_multiplier": mult,
            "schedule": [
                {"stage": "basal day 0", "kg": round(total * 0.6, 1)},
                {"stage": "top dress day 45", "kg": round(total * 0.4, 1)},
            ],
            "note": None,
        })

    ph_status = diagnosis.get("ph")
    ph_bounds = thresholds.get("ph")
    ph_value = readings.get("ph")

    if ph_status == "acidic" or ph_status == "low":
        if ph_value is not None and ph_bounds is not None:
            mult = _ph_severity_multiplier(float(ph_value), float(ph_bounds["low"]))
        else:
            mult = 1.0
        total = _scaled_total(_CORRECTION_RATES["lime_acidic"], mult)
        applications.append({
            "product": "Lime",
            "total_kg": total,
            "unit": "kg/ha",
            "severity_multiplier": mult,
            "schedule": [{"stage": "basal, 2-4 weeks before sowing", "kg": total}],
            "note": "Apply well before sowing to allow pH correction to take effect.",
        })
    elif ph_status == "alkaline" or ph_status == "high":
        if ph_value is not None and ph_bounds is not None:
            mult = _ph_severity_multiplier(float(ph_value), float(ph_bounds["high"]))
        else:
            mult = 1.0
        total = _scaled_total(_CORRECTION_RATES["gypsum_alkaline"], mult)
        applications.append({
            "product": "Gypsum",
            "total_kg": total,
            "unit": "kg/ha",
            "severity_multiplier": mult,
            "schedule": [{"stage": "basal, 2-4 weeks before sowing", "kg": total}],
            "note": None,
        })

    if not applications:
        applications.append({
            "product": "None required",
            "total_kg": 0.0,
            "unit": "kg/ha",
            "severity_multiplier": 1.0,
            "schedule": [],
            "note": "No parameters are in the 'low' range for the products this calculator covers.",
        })

    return applications 