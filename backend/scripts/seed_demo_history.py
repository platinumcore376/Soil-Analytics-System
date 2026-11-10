"""Seed a plot with several seasons of soil history, so the trend screen has something to show.

WHY THIS EXISTS
The degradation trend predictor refuses to project from fewer than three soil records
(`trends.MIN_RECORDS`), and that refusal is correct — two points always fit a line exactly, so
a regression over two records reports a slope it has no evidence for. The consequence is that
a fresh account cannot see the trend screen at all: there is nothing to plot.

This creates the history rather than lowering the bar. Records are backdated one per season
(~120 days apart) with a declining nutrient profile, which is the case worth looking at — a
farmer whose soil is quietly degrading is exactly who the projection is for.

USAGE
    python backend/scripts/seed_demo_history.py --phone 9876543210 --password yourpassword

    # or against an existing plot, if you know its id
    python backend/scripts/seed_demo_history.py --phone ... --password ... --field-id 12

    --seasons N   how many records to write (default 5)
    --trend       declining | stable | improving   (default declining)
    --api URL     defaults to http://127.0.0.1:8000

It talks to the running API rather than the database directly, so every write goes through the
same validation and ownership checks a real client would.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta

DAYS_PER_SEASON = 120


def call(api: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    headers = {}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(api + path, data=data, headers=headers)
    try:
        return json.loads(urllib.request.urlopen(request).read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:400]
        raise SystemExit(f"{path} -> HTTP {exc.code}\n{detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"Cannot reach {api}. Start the backend first:\n"
            "    cd backend && uvicorn app.main:app --reload\n"
            f"({exc.reason})"
        ) from exc


def profile(step: int, total: int, trend: str) -> dict[str, float]:
    """Readings for one season, interpolated between a start and an end profile.

    WHY NOT JUST NEGATE THE DECLINE
    The first version of this did exactly that, and produced a plot whose verdict came back
    "declining" while claiming to improve. The reason is a real property of the scorer, not a
    bug in it: soil health is scored against an OPTIMUM BAND, not on "more is better".
    Mirroring the decline pushed nitrogen to 390 kg/ha and pH to 8.5 — excessive and alkaline
    — so the score fell at both ends.

    So each direction is defined by where it starts and where it ends. Improving begins
    depleted and acidic and rises toward the middle of the band; declining does the reverse.
    """
    # 0.0 at the oldest record, 1.0 at the newest.
    t = step / max(1, total - 1)

    # (start, end) per parameter. Healthy target sits mid-band, never beyond it.
    healthy = {
        "nitrogen": 280.0, "phosphorus": 48.0, "potassium": 210.0,
        "ph": 6.8, "organic_matter": 1.15, "moisture": 26.0,
    }
    depleted = {
        "nitrogen": 150.0, "phosphorus": 28.0, "potassium": 120.0,
        "ph": 5.5, "organic_matter": 0.45, "moisture": 19.0,
    }

    if trend == "declining":
        start, end = healthy, depleted
    elif trend == "improving":
        start, end = depleted, healthy
    else:  # stable — hold the healthy profile flat
        start, end = healthy, healthy

    precision = {"ph": 2, "organic_matter": 2}
    return {
        key: round(start[key] + (end[key] - start[key]) * t, precision.get(key, 1))
        for key in healthy
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--phone", required=True, help="account identifier (phone or email)")
    ap.add_argument("--password", required=True)
    ap.add_argument("--field-id", type=int, default=None, help="plot to seed; default first")
    ap.add_argument("--seasons", type=int, default=5)
    ap.add_argument(
        "--trend", choices=("declining", "stable", "improving"), default="declining"
    )
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument(
        "--new-plot",
        metavar="NAME",
        help=(
            "Create a fresh plot with this name and seed that instead of an existing one. "
            "Use it to compare trends: re-running against the same plot APPENDS records, so "
            "a second run mixes both profiles and the verdict reflects the combination."
        ),
    )
    args = ap.parse_args()

    api = args.api.rstrip("/")

    if args.seasons < 3:
        print("Note: fewer than 3 seasons will not produce a projection.", file=sys.stderr)

    token = call(
        api, "/auth/login", {"identifier": args.phone, "password": args.password}
    ).get("access_token")
    if not token:
        raise SystemExit("Login failed — check the phone/email and password.")
    print(f"Signed in as {args.phone}")

    # Resolve the plot: an explicit id, a brand-new plot, or the first existing one.
    field_id = args.field_id
    if field_id is None and args.new_plot:
        farms = call(api, "/farms", token=token)
        farm_id = (
            farms[0]["id"]
            if farms
            else call(api, "/farms", {"name": args.new_plot}, token=token)["id"]
        )
        created = call(
            api,
            "/fields",
            {"farm_id": farm_id, "name": args.new_plot, "area_hectares": 1.5},
            token=token,
        )
        field_id = created["id"]
        print(f"Created plot '{args.new_plot}' (id {field_id})")
    if field_id is None:
        farms = call(api, "/farms", token=token)
        if not farms:
            raise SystemExit(
                "This account has no plots. Add one in the app first, then re-run."
            )
        for farm in farms:
            fields = call(api, f"/farms/{farm['id']}/fields", token=token)
            if fields:
                field_id = fields[0]["id"]
                print(f"Using plot '{fields[0]['name']}' (id {field_id}) on '{farm['name']}'")
                break
        if field_id is None:
            raise SystemExit("Found farms but no plots. Add a plot in the app first.")

    now = datetime.now()
    print(f"\nWriting {args.seasons} records, {args.trend}, ~{DAYS_PER_SEASON} days apart:")
    print(f"  {'sampled':<12} {'N':>6} {'P':>6} {'K':>6} {'pH':>5} {'OM':>5}")

    record_ids = []
    for step in range(args.seasons):
        # Oldest first, so the series reads chronologically.
        seasons_ago = args.seasons - 1 - step
        sampled = now - timedelta(days=DAYS_PER_SEASON * seasons_ago)
        values = profile(step, args.seasons, args.trend)

        record = call(
            api,
            "/soil-records",
            {"field_id": field_id, "sampled_at": sampled.isoformat(), **values},
            token=token,
        )
        record_ids.append(record["id"])
        print(
            f"  {sampled.date()!s:<12} {values['nitrogen']:>6} {values['phosphorus']:>6} "
            f"{values['potassium']:>6} {values['ph']:>5} {values['organic_matter']:>5}"
        )

    # Analyse each record so the results screens have something to open, and so the trend is
    # computed from the same scoring path the app uses.
    print("\nAnalysing each record…")
    analysis_ids = []
    for record_id in record_ids:
        result = call(
            api,
            "/analyze",
            {"field_id": field_id, "soil_record_id": record_id},
            token=token,
        )
        if result.get("analysis_id"):
            analysis_ids.append(result["analysis_id"])
            print(f"  record {record_id} -> analysis {result['analysis_id']}, "
                  f"score {result.get('soil_health_score')}")

    trend = call(api, f"/trends/{field_id}", token=token)
    print("\nTrend:")
    if not trend.get("sufficient"):
        print("  not sufficient:", trend.get("reason"))
        return 1

    # Fit statistics live under `model`, not at the top level.
    model = trend.get("model") or {}
    print(f"  verdict              {trend.get('verdict')}")
    print(f"  current score        {trend.get('current_score')}")
    print(f"  records used         {trend.get('records_used')}")
    print(f"  slope / record       {model.get('slope_per_record')}")
    print(f"  r_squared            {model.get('r_squared')}")
    print(f"  confidence           {trend.get('projection_confidence')}")
    print(f"  seasons to critical  {trend.get('seasons_to_critical')}")
    for step in trend.get("projection") or []:
        print(
            f"    +{step['seasons_ahead']} season(s): {step['predicted_score']}"
            f"  range {step['range'][0]}-{step['range'][1]}"
        )

    if analysis_ids:
        print(f"\nOpen in the app:  /results/{analysis_ids[-1]}/trend")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
