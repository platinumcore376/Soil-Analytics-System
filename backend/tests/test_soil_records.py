"""Soil record CRUD and the NPK scale guard.

The scale guard exists because of a real bug: N/P/K here are a soil-test INDEX
(N 0-140, P 5-145, K 5-205 — the ranges the models were trained on), and a Soil
Health Card figure in kg/ha (often 200-400 for nitrogen) once slipped through
and was diagnosed as HIGH next to a CRITICAL health score.
"""
from tests.conftest import HEALTHY_READINGS


def _create(client, headers, field_id, **overrides):
    return client.post(
        "/soil-records",
        json={"field_id": field_id, **HEALTHY_READINGS, **overrides},
        headers=headers,
    )


def test_create_and_read_back(client, make_user, make_field):
    u = make_user()
    _, field = make_field(u["headers"])
    r = _create(client, u["headers"], field["id"])
    assert r.status_code == 201, r.text
    assert r.json()["nitrogen"] == HEALTHY_READINGS["nitrogen"]

    listing = client.get(f"/soil-records/by-field/{field['id']}", headers=u["headers"])
    assert [rec["id"] for rec in listing.json()] == [r.json()["id"]]


def test_kg_per_ha_scale_rejected(client, make_user, make_field):
    u = make_user()
    _, field = make_field(u["headers"])
    r = _create(client, u["headers"], field["id"], nitrogen=400)  # kg/ha-scale value
    assert r.status_code == 422
    assert "index" in r.text.lower()  # the error must say WHY, not just reject


def test_index_scale_boundaries(client, make_user, make_field):
    u = make_user()
    _, field = make_field(u["headers"])
    # Exactly at the trained maximum is legal…
    assert _create(client, u["headers"], field["id"], nitrogen=140).status_code == 201
    assert _create(client, u["headers"], field["id"], potassium=205).status_code == 201
    # …one unit above is not.
    assert _create(client, u["headers"], field["id"], nitrogen=140.5).status_code == 422
    assert _create(client, u["headers"], field["id"], phosphorus=146).status_code == 422


def test_implausible_ph_rejected(client, make_user, make_field):
    u = make_user()
    _, field = make_field(u["headers"])
    assert _create(client, u["headers"], field["id"], ph=12).status_code == 422
    assert _create(client, u["headers"], field["id"], ph=1.0).status_code == 422


def test_patch_updates_value_and_guard_still_applies(client, make_user, make_field):
    u = make_user()
    _, field = make_field(u["headers"])
    rec = _create(client, u["headers"], field["id"]).json()

    ok = client.patch(
        f"/soil-records/{rec['id']}", json={"nitrogen": 60}, headers=u["headers"]
    )
    assert ok.status_code == 200 and ok.json()["nitrogen"] == 60

    # The update path must enforce the same scale guard as create.
    bad = client.patch(
        f"/soil-records/{rec['id']}", json={"potassium": 500}, headers=u["headers"]
    )
    assert bad.status_code == 422


def test_analyze_inline_readings_also_guarded(client, make_user, make_field):
    """/analyze accepts inline readings — historically the UNCHECKED path."""
    u = make_user()
    _, field = make_field(u["headers"])
    r = client.post(
        "/analyze",
        json={"field_id": field["id"], "nitrogen": 300, "ph": 6.5},
        headers=u["headers"],
    )
    assert r.status_code == 422
    assert "index" in r.text.lower()
