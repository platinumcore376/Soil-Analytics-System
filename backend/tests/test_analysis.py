"""The analysis pipeline: /analyze, recommendations, crop suitability, trends, PDF report.

These run the real XGBoost artifacts from models/structured (no mocks) — if the
artifacts are missing or incompatible, these tests fail, which is exactly the
signal a deploy needs.
"""
from tests.conftest import DEPLETED_READINGS, HEALTHY_READINGS


def _analyze(client, headers, field_id, readings, **extra):
    return client.post(
        "/analyze",
        json={"field_id": field_id, **readings, "persist": True, **extra},
        headers=headers,
    )


def test_analyze_healthy_soil(client, make_user, make_field):
    u = make_user()
    _, field = make_field(u["headers"])
    r = _analyze(client, u["headers"], field["id"], HEALTHY_READINGS)
    assert r.status_code == 201, r.text
    body = r.json()

    assert body["analysis_id"] is not None  # persisted
    assert 0 <= body["soil_health_score"] <= 100
    assert isinstance(body["diagnosis"], dict)
    assert 0 <= body["degradation_risk"]["index"] <= 100
    assert body["fertilizer_recommendation"]["recommended"]


def test_healthy_scores_above_depleted(client, make_user, make_field):
    u = make_user()
    _, field = make_field(u["headers"])
    healthy = _analyze(client, u["headers"], field["id"], HEALTHY_READINGS).json()
    depleted = _analyze(client, u["headers"], field["id"], DEPLETED_READINGS).json()
    assert healthy["soil_health_score"] > depleted["soil_health_score"]


def test_analyze_requires_some_reading(client, make_user, make_field):
    u = make_user()
    _, field = make_field(u["headers"])
    r = client.post("/analyze", json={"field_id": field["id"]}, headers=u["headers"])
    assert r.status_code == 422


def _analyze_stored_record(client, headers, field_id, readings):
    """The full real flow: store the lab values, then analyse the stored record.

    Advisory endpoints (recommendations, reports) need the original readings, so
    they only work for analyses linked to a soil record.
    """
    rec = client.post(
        "/soil-records", json={"field_id": field_id, **readings}, headers=headers
    )
    assert rec.status_code == 201, rec.text
    r = client.post(
        "/analyze",
        json={"field_id": field_id, "soil_record_id": rec.json()["id"], "persist": True},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["analysis_id"]


def test_stored_analysis_and_recommendations(client, make_user, make_field):
    u = make_user()
    _, field = make_field(u["headers"])
    aid = _analyze_stored_record(client, u["headers"], field["id"], DEPLETED_READINGS)

    stored = client.get(f"/analysis-results/{aid}", headers=u["headers"])
    assert stored.status_code == 200
    assert stored.json()["field_id"] == field["id"]

    recs = client.get(f"/recommendations/{aid}", headers=u["headers"])
    assert recs.status_code == 200, recs.text


def test_inline_analysis_cannot_produce_advisory(client, make_user, make_field):
    """Deliberate contract: inline readings are never stored, so advisory
    endpoints refuse with 409 and tell the caller the recoverable path."""
    u = make_user()
    _, field = make_field(u["headers"])
    aid = _analyze(client, u["headers"], field["id"], HEALTHY_READINGS).json()["analysis_id"]

    for path in (f"/recommendations/{aid}", f"/reports/{aid}"):
        r = client.get(path, headers=u["headers"])
        assert r.status_code == 409, f"{path}: {r.text}"
        assert "soil_record_id" in r.text


def test_crop_suitability_ranked_and_truncated(client, make_user, make_field):
    u = make_user()
    _, field = make_field(u["headers"])
    client.post(
        "/soil-records",
        json={"field_id": field["id"], **HEALTHY_READINGS},
        headers=u["headers"],
    )
    r = client.get(f"/crop-suitability/{field['id']}?top_k=5", headers=u["headers"])
    assert r.status_code == 200, r.text
    ranked = r.json()["ranked_crops"]
    assert 0 < len(ranked) <= 5
    scores = [c["suitability"] for c in ranked]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 1 for s in scores)


def test_trend_insufficient_below_three_records(client, make_user, make_field):
    u = make_user()
    _, field = make_field(u["headers"])
    client.post(
        "/soil-records",
        json={"field_id": field["id"], **HEALTHY_READINGS},
        headers=u["headers"],
    )
    body = client.get(f"/trends/{field['id']}", headers=u["headers"]).json()
    assert body["sufficient"] is False
    assert body["records_required"] == 3
    assert body["projection"] == []


def test_trend_detects_decline(client, make_user, make_field):
    u = make_user()
    _, field = make_field(u["headers"])
    # Four records, each visibly worse than the last, timestamped in order.
    for i, n in enumerate((110, 80, 45, 15)):
        r = client.post(
            "/soil-records",
            json={
                "field_id": field["id"],
                "nitrogen": n,
                "phosphorus": max(5, 45 - i * 12),
                "potassium": max(5, 45 - i * 12),
                "ph": 6.5,
                "sampled_at": f"2026-0{i + 1}-01T00:00:00",
            },
            headers=u["headers"],
        )
        assert r.status_code == 201, r.text

    body = client.get(f"/trends/{field['id']}", headers=u["headers"]).json()
    assert body["sufficient"] is True
    assert body["verdict"] == "declining"
    assert body["model"]["type"] == "ridge_regression"
    assert body["model"]["slope_per_record"] < 0
    assert body["projection"], "a sufficient trend must include a forward projection"


def test_report_is_a_pdf(client, make_user, make_field):
    u = make_user()
    _, field = make_field(u["headers"])
    aid = _analyze_stored_record(client, u["headers"], field["id"], HEALTHY_READINGS)

    r = client.get(f"/reports/{aid}?language=en", headers=u["headers"])
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:5] == b"%PDF-"
    assert b"%%EOF" in r.content[-1024:]  # complete document, not a truncated stream


def test_report_language_validated(client, make_user, make_field):
    u = make_user()
    _, field = make_field(u["headers"])
    aid = _analyze(client, u["headers"], field["id"], HEALTHY_READINGS).json()["analysis_id"]
    assert client.get(f"/reports/{aid}?language=xx", headers=u["headers"]).status_code == 422
