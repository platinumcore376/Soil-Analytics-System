"""Cross-account isolation.

The companion of the service-worker cache-leak fix on the frontend: no user
may see, modify, or even confirm the existence of another user's data. The
API's contract is 404 (not 403) for foreign resources — a 403 would leak that
the resource exists.
"""
from tests.conftest import HEALTHY_READINGS


def test_farms_listing_is_per_user(client, make_user, make_field):
    a, b = make_user(), make_user()
    make_field(a["headers"])
    assert len(client.get("/farms", headers=a["headers"]).json()) == 1
    assert client.get("/farms", headers=b["headers"]).json() == []


def test_foreign_fields_listing_404s(client, make_user, make_field):
    a, b = make_user(), make_user()
    farm, _ = make_field(a["headers"])
    r = client.get(f"/farms/{farm['id']}/fields", headers=b["headers"])
    assert r.status_code == 404


def test_cannot_create_field_on_foreign_farm(client, make_user, make_field):
    a, b = make_user(), make_user()
    farm, _ = make_field(a["headers"])
    r = client.post(
        "/fields",
        json={"farm_id": farm["id"], "name": "Squatter"},
        headers=b["headers"],
    )
    assert r.status_code == 404


def test_cannot_write_soil_record_to_foreign_field(client, make_user, make_field):
    a, b = make_user(), make_user()
    _, field = make_field(a["headers"])
    r = client.post(
        "/soil-records",
        json={"field_id": field["id"], **HEALTHY_READINGS},
        headers=b["headers"],
    )
    assert r.status_code == 404


def test_foreign_analysis_and_report_404(client, make_user, make_field):
    a, b = make_user(), make_user()
    _, field = make_field(a["headers"])
    analysis = client.post(
        "/analyze",
        json={"field_id": field["id"], **HEALTHY_READINGS, "persist": True},
        headers=a["headers"],
    )
    assert analysis.status_code == 201, analysis.text
    aid = analysis.json()["analysis_id"]

    # The owner can read it back; the other account gets 404 everywhere.
    assert client.get(f"/analysis-results/{aid}", headers=a["headers"]).status_code == 200
    assert client.get(f"/analysis-results/{aid}", headers=b["headers"]).status_code == 404
    assert client.get(f"/reports/{aid}", headers=b["headers"]).status_code == 404
    assert client.get(f"/recommendations/{aid}", headers=b["headers"]).status_code == 404


def test_foreign_trend_404(client, make_user, make_field):
    a, b = make_user(), make_user()
    _, field = make_field(a["headers"])
    assert client.get(f"/trends/{field['id']}", headers=b["headers"]).status_code == 404
