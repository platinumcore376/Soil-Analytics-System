"""Image file lifecycle: upload, retention sweep, and report-completion deletion.

The contract under test everywhere: deleting a FILE never harms the DATA.
Analyses, scores and trends live in PostgreSQL; the file endpoints answer 410
for a deleted file and the frontend handles that.
"""
import io
import os

import app.database as database
from app import storage
from app.config import settings
from app.models import AnalysisResult


def _jpeg_bytes(size=(64, 64), color=(120, 90, 60)) -> bytes:
    from PIL import Image as PILImage

    buf = io.BytesIO()
    PILImage.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


def _upload(client, headers, field_id):
    r = client.post(
        "/images",
        files={"file": ("soil.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"field_id": str(field_id), "source": "camera"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------------------- upload ----
def test_upload_and_serve(client, make_user, make_field):
    u = make_user()
    _, field = make_field(u["headers"])
    body = _upload(client, u["headers"], field["id"])

    served = client.get(f"/images/{body['id']}/file?variant=original", headers=u["headers"])
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/jpeg"
    processed = client.get(f"/images/{body['id']}/file?variant=processed", headers=u["headers"])
    assert processed.status_code == 200


def test_foreign_image_file_is_404(client, make_user, make_field):
    a, b = make_user(), make_user()
    _, field = make_field(a["headers"])
    image_id = _upload(client, a["headers"], field["id"])["id"]
    assert client.get(f"/images/{image_id}/file", headers=b["headers"]).status_code == 404


# ---------------------------------------------------- report-completion delete ----
def test_report_generation_deletes_image_files(client, make_user, make_field):
    """The pipeline's last stop: once the PDF exists, the photo's files go."""
    u = make_user()
    _, field = make_field(u["headers"])
    image = _upload(client, u["headers"], field["id"])
    assert os.path.isfile(image["stored_path"])
    assert os.path.isfile(image["processed_path"])

    # Real flow: stored record -> analysis. The image is attached to the analysis
    # row directly (going through /analyze with image_id would require torch).
    rec = client.post(
        "/soil-records",
        json={"field_id": field["id"], "nitrogen": 90, "ph": 6.5},
        headers=u["headers"],
    ).json()
    analysis = client.post(
        "/analyze",
        json={"field_id": field["id"], "soil_record_id": rec["id"], "persist": True},
        headers=u["headers"],
    ).json()
    with database.SessionLocal() as db:
        row = db.get(AnalysisResult, analysis["analysis_id"])
        row.image_id = image["id"]
        db.commit()

    # Generating the report succeeds AND removes the files.
    report = client.get(f"/reports/{analysis['analysis_id']}", headers=u["headers"])
    assert report.status_code == 200, report.text
    assert report.content[:5] == b"%PDF-"
    assert not os.path.exists(image["stored_path"])
    assert not os.path.exists(image["processed_path"])

    # Data untouched: metadata row, analysis, and a report RE-download all work.
    assert client.get(f"/images/{image['id']}", headers=u["headers"]).status_code == 200
    again = client.get(f"/reports/{analysis['analysis_id']}", headers=u["headers"])
    assert again.status_code == 200
    assert again.content[:5] == b"%PDF-"
    # Only the file endpoint reports the deletion, honestly.
    gone = client.get(f"/images/{image['id']}/file", headers=u["headers"])
    assert gone.status_code == 410


# ----------------------------------------------------------- retention sweep ----
def test_retention_sweep_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "up"))
    monkeypatch.setattr(settings, "processed_dir", str(tmp_path / "proc"))
    old = settings.upload_path / "ancient.jpg"
    old.write_bytes(b"x")
    os.utime(old, (0, 0))  # epoch — as old as a file can be
    assert storage.sweep_expired() == 0  # retention 0 -> keep everything
    assert old.exists()


def test_retention_sweep_removes_only_expired(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "up"))
    monkeypatch.setattr(settings, "processed_dir", str(tmp_path / "proc"))
    monkeypatch.setattr(settings, "image_retention_hours", 1.0)

    expired = settings.upload_path / "old.jpg"
    expired.write_bytes(b"x")
    os.utime(expired, (0, 0))
    fresh = settings.processed_path / "new_proc.jpg"
    fresh.write_bytes(b"y")

    assert storage.sweep_expired() == 1
    assert not expired.exists()
    assert fresh.exists()  # inside the retention window — untouched


def test_swept_image_returns_410_but_analysis_survives(
    client, make_user, make_field, monkeypatch
):
    u = make_user()
    _, field = make_field(u["headers"])
    up = _upload(client, u["headers"], field["id"])

    analysis = client.post(
        "/analyze",
        json={"field_id": field["id"], "nitrogen": 90, "ph": 6.5, "persist": True},
        headers=u["headers"],
    ).json()

    # Expire everything, sweep.
    for d in (settings.upload_path, settings.processed_path):
        for f in d.iterdir():
            os.utime(f, (0, 0))
    monkeypatch.setattr(settings, "image_retention_hours", 1.0)
    assert storage.sweep_expired() >= 2

    # File gone -> honest 410; metadata row and the analysis still fine.
    assert client.get(f"/images/{up['id']}/file", headers=u["headers"]).status_code == 410
    assert client.get(f"/images/{up['id']}", headers=u["headers"]).status_code == 200
    r = client.get(f"/analysis-results/{analysis['analysis_id']}", headers=u["headers"])
    assert r.status_code == 200
