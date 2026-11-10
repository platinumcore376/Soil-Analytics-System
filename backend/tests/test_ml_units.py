"""Unit tests for the pure-ML helpers — no HTTP, no database."""
import pytest

from app.ml import crops, trend as trends
from app.schemas import NUTRIENT_INDEX_MAX, _check_nutrient_scale

READINGS = {"nitrogen": 90, "phosphorus": 45, "potassium": 45, "ph": 6.5}


# ---------------------------------------------------------------- trends ----
def test_ridge_fit_matches_closed_form():
    # For x=[0,1,2,3], y=[10,12,14,16]: Sxy=10, Sxx=5, alpha=1 → slope 10/6.
    slope, intercept = trends._ridge_fit([0, 1, 2, 3], [10, 12, 14, 16], alpha=1.0)
    assert slope == pytest.approx(10 / 6)
    # Intercept re-centres on the means: 13 - (10/6) * 1.5 = 10.5
    assert intercept == pytest.approx(10.5)


def test_predict_refuses_short_history():
    out = trends.predict([{"score": 80}, {"score": 70}])
    assert out["sufficient"] is False
    assert out["records_required"] == trends.MIN_RECORDS
    assert out["projection"] == []


def test_predict_flags_decline_with_diagnostics():
    out = trends.predict([{"score": s} for s in (82, 75, 70, 64, 57)])
    assert out["sufficient"] is True
    assert out["verdict"] == "declining"
    assert out["model"]["slope_per_record"] < 0
    assert 0 <= out["model"]["r_squared"] <= 1
    assert out["projection"]


def test_predict_stable_is_not_declining():
    out = trends.predict([{"score": s} for s in (70, 70.4, 69.8, 70.2, 70.1)])
    assert out["sufficient"] is True
    assert out["verdict"] != "declining"


# ----------------------------------------------------------------- crops ----
def test_rank_orders_and_truncates():
    out = crops.rank(READINGS, top_k=5)
    ranked = out["ranked_crops"]
    assert len(ranked) == 5
    scores = [c["suitability"] for c in ranked]
    assert scores == sorted(scores, reverse=True)


def test_soil_type_factor_neutral_without_soil_type():
    out = crops.rank(READINGS, top_k=None, soil_type=None)
    assert all(c["soil_type_factor"] == 1.0 for c in out["ranked_crops"])


def test_soil_type_factor_stays_within_clamp():
    for soil_type in ("Alluvial", "Black", "Laterite", "Red"):
        out = crops.rank(READINGS, top_k=None, soil_type=soil_type)
        for c in out["ranked_crops"]:
            assert 0.85 <= c["soil_type_factor"] <= 1.15, (soil_type, c["crop"])
            # suitability must stay a probability-like score after the multiplier
            assert 0 <= c["suitability"] <= 1


def test_unknown_soil_type_is_neutral_not_crash():
    out = crops.rank(READINGS, top_k=3, soil_type="Martian")
    assert all(c["soil_type_factor"] == 1.0 for c in out["ranked_crops"])


# --------------------------------------------------------------- schemas ----
class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_nutrient_scale_guard_boundaries():
    for name, limit in NUTRIENT_INDEX_MAX.items():
        _check_nutrient_scale(_Obj(**{name: limit}))  # at the limit: fine
        with pytest.raises(ValueError, match="INDEX"):
            _check_nutrient_scale(_Obj(**{name: limit + 1}))


def test_nutrient_scale_guard_ignores_missing_values():
    _check_nutrient_scale(_Obj(nitrogen=None))
    _check_nutrient_scale(_Obj())  # no attributes at all
