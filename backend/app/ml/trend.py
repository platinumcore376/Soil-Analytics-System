"""Long-term soil degradation trend predictor."""
from __future__ import annotations

import base64
import io
import datetime as dt_module
from datetime import datetime
from typing import Any

import numpy as np

MIN_RECORDS_FOR_TREND = 3
MIN_RECORDS = MIN_RECORDS_FOR_TREND  
RIDGE_ALPHA = 1.0         
DEFAULT_HORIZON_DAYS = 90  
DEFAULT_HORIZON_POINTS = 3  

def _ridge_fit(x: list[float] | np.ndarray, y: list[float] | np.ndarray, alpha: float = RIDGE_ALPHA) -> tuple[float, float]:
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    x_mean, y_mean = x_arr.mean(), y_arr.mean()
    xc, yc = x_arr - x_mean, y_arr - y_mean
    denom = (xc @ xc) + alpha
    slope = float((xc @ yc) / denom) if denom else 0.0
    intercept = float(y_mean - slope * x_mean)
    return slope, intercept

def _r_squared(y: np.ndarray, fitted: np.ndarray) -> float:
    ss_res = float(np.sum((y - fitted) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    if ss_tot == 0: return 0.0
    return round(max(0.0, 1.0 - ss_res / ss_tot), 3)

def _parse_date(dt_val: Any) -> datetime | None:
    if isinstance(dt_val, datetime): return dt_val
    if isinstance(dt_val, str):
        try:
            return datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
        except ValueError:
            try: return datetime.strptime(dt_val.split("T")[0], "%Y-%m-%d")
            except ValueError: return None
    return None

def predict(
    records: list[dict[str, Any]],
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    horizon_points: int = DEFAULT_HORIZON_POINTS,
) -> dict[str, Any]:
    """Analyze historical score trends and return decline diagnostics."""
    valid_records = []
    for i, r in enumerate(records):
        dt = _parse_date(r.get("date") or r.get("sampled_at") or r.get("created_at"))
        if dt is None:
            dt = dt_module.datetime.now() + dt_module.timedelta(days=i * 30)
        
        score = r.get("score") if r.get("score") is not None else r.get("soil_health_score")
        if score is not None:
            valid_records.append({"date": dt, "score": float(score)})

    n = len(valid_records)
    if n < MIN_RECORDS_FOR_TREND:
        return {
            "fitted": False,
            "sufficient": False,
            "records_required": MIN_RECORDS_FOR_TREND,
            "records_used": n,
            "reason": f"At least {MIN_RECORDS_FOR_TREND} records required.",
            "history": [{"score": r["score"], "date": r["date"].isoformat()} for r in valid_records],
            "projection": [],
            "chart_png": None,
        }

    valid_records.sort(key=lambda x: x["date"])
    x = np.array([(r["date"] - valid_records[0]["date"]).total_seconds() / 86400.0 for r in valid_records], dtype=float)
    y = np.array([r["score"] for r in valid_records], dtype=float)

    slope, intercept = _ridge_fit(x, y, alpha=RIDGE_ALPHA)
    declining = slope < -0.01  
    
    fitted_line = (slope * x + intercept).tolist()
    r2 = _r_squared(y, np.array(fitted_line))
    
    current_score = float(y[-1]) if len(y) > 0 else 50.0

    last_x = x[-1] if len(x) > 0 else 0.0
    projection = []
    for step in range(1, horizon_points + 1):
        future_day = last_x + (step * (horizon_days / horizon_points))
        pred_score = max(0.0, min(100.0, round(slope * future_day + intercept, 1)))
        margin = max(5.0, round(10.0 * (1.0 - r2), 1))
        projection.append({
            "horizon": f"horizon_{step}",
            "seasons_ahead": step,
            "day": int(future_day),
            "predicted_score": pred_score,
            "range": [max(0.0, round(pred_score - margin, 1)), min(100.0, round(pred_score + margin, 1))]
        })

    history_payload = [{"score": r["score"], "date": r["date"].isoformat()} for r in valid_records]

    return {
        "fitted": True,
        "sufficient": True,
        "current_score": current_score,
        "verdict": "declining" if declining else "stable",
        "declining": declining,
        "model": {
            "type": "ridge_regression",
            "slope_per_record": slope,
            "r_squared": r2
        },
        "slope": slope,
        "intercept": intercept,
        "records_used": n,
        "history": history_payload,
        "projection": projection,
        "interpretation": (
            "Soil health shows a declining trend over recorded seasons. Projections indicate ongoing nutrient depletion."
            if declining
            else "Soil health score is currently stable across recorded seasons."
        ),
        "caveat": "Projections are statistical extrapolations and should be calibrated against local agronomic conditions.",
        "chart_png": _render_chart(x, y, fitted_line, projection)
    }

def predict_trend(
    records: list[dict[str, Any]],
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    horizon_points: int = DEFAULT_HORIZON_POINTS,
) -> dict[str, Any]:
    """Fit Ridge Regression to a field's score history and project forward."""
    return predict(records, horizon_days=horizon_days, horizon_points=horizon_points)

def _render_chart(x: np.ndarray, y: np.ndarray, fitted_line: list[float], projection: list[dict[str, Any]]) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6, 3.2), dpi=150)
        ax.plot(x, y, "o-", color="#4A6B37", label="Actual")
        ax.plot(x, fitted_line, "--", color="#6B5E50", label="Ridge fit")
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("ascii")
    except Exception:
        return ""