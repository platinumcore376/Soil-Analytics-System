"""Crop rotation awareness (extension of Weeks 5-6 crop recommendation).

Checks the crop-suitability model's ranked candidates against what was
*recommended* for this field in recent analyses, and flags repeats of
nutrient-depleting crop families rather than silently repeating them.

Important honesty note, matching fusion.py's confidence-gate discipline:
`recent_crops` here means "what this system previously recommended", not
"what was actually planted" -- the schema has no planting-confirmation
field. The flag says so explicitly so it isn't mistaken for verified
rotation history.

Editorial, not fitted: the demand groupings below are documented general
agronomy (legumes fix nitrogen; cereals/fruit crops are comparatively
heavy N/K feeders), not learned from the crop-suitability training data,
which carries no rotation or depletion labels.
"""
from __future__ import annotations

from typing import Any

# Kaggle Crop_recommendation.csv's 22 classes, grouped by rotation-relevant
# demand. Legumes are nitrogen-fixing and improve soil for the next crop;
# the rest are grouped by which nutrient they draw down most.
NITROGEN_FIXING = {
    "chickpea", "kidneybeans", "pigeonpeas", "mothbeans",
    "mungbean", "blackgram", "lentil",
}
HEAVY_N_FEEDERS = {"rice", "maize", "cotton", "jute", "banana"}
HEAVY_K_FEEDERS = {"banana", "watermelon", "muskmelon"}


def apply_rotation_check(
    candidates: list[dict[str, Any]],
    recent_crops: list[str],
) -> list[dict[str, Any]]:
    """Annotate each crop candidate with a rotation flag; does not re-rank.

    `recent_crops`: this field's last recommended crops, most recent first
    (typically the last 1-2 persisted analyses). Confidence values are left
    untouched -- this only adds a `rotation` block per candidate.
    """
    last = recent_crops[0] if recent_crops else None

    for c in candidates:
        crop = c["crop"]
        flags: list[str] = []

        if last and crop == last:
            is_heavy = crop in HEAVY_N_FEEDERS or crop in HEAVY_K_FEEDERS
            if is_heavy:
                flags.append(
                    "Same as the last recommended crop for this field -- "
                    "repeating a heavy feeder can compound the deficiency it's meant to fix."
                )
            elif last not in NITROGEN_FIXING:
                flags.append("Same as the last recommended crop for this field.")

        if last in HEAVY_N_FEEDERS and crop in NITROGEN_FIXING:
            flags.append(
                f"Good rotation fit: nitrogen-fixing, follows a heavy nitrogen feeder ({last})."
            )

        c["rotation"] = {
            "flags": flags,
            "basis": "previously recommended crops for this field, not confirmed planting",
        }
    return candidates