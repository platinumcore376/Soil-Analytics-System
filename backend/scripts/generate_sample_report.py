# -*- coding: utf-8 -*-
"""Produce a complete sample soil health report PDF from the running application."""
import json, pathlib, urllib.error, urllib.request, uuid

API = "http://127.0.0.1:8000"
ROOT = pathlib.Path(r"C:/Users/shash/AI-Based-Soil-Health-Assessment-System-for-Nutrient-Deficiency-Detection---Crop-Recommend-July-2026")
OUT = pathlib.Path(__file__).parent

def call(path, body=None, tok=None, raw=False):
    h, data = {}, None
    if body is not None:
        h["Content-Type"] = "application/json"; data = json.dumps(body).encode("utf-8")
    if tok: h["Authorization"] = "Bearer " + tok
    r = urllib.request.Request(API + path, data=data, headers=h)
    try:
        p = urllib.request.urlopen(r).read()
        return p if raw else json.loads(p)
    except urllib.error.HTTPError as e:
        raise SystemExit("%s -> %s %s" % (path, e.code, e.read().decode()[:300]))

tok = call("/auth/login", {"identifier": "9000000001", "password": "demofarmer123"})["access_token"]

# A dedicated plot so the report is clean and reproducible.
farms = call("/farms", tok=tok)
farm_id = farms[0]["id"]
field = call("/fields", {"farm_id": farm_id, "name": "North Field", "area_hectares": 1.6}, tok=tok)
print("plot:", field["id"])

# Upload a real soil photo -> gives soil type + Grad-CAM in the report.
img = sorted((ROOT / "inputs").glob("*.jpg"))[0]
b = "----R" + uuid.uuid4().hex
body = bytearray()
for k, v in (("field_id", str(field["id"])), ("source", "camera")):
    body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (b, k, v)).encode()
body += ("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\nContent-Type: image/jpeg\r\n\r\n" % (b, img.name)).encode()
body += img.read_bytes() + b"\r\n" + ("--%s--\r\n" % b).encode()
req = urllib.request.Request(API + "/images", data=bytes(body),
    headers={"Content-Type": "multipart/form-data; boundary=" + b, "Authorization": "Bearer " + tok})
image = json.loads(urllib.request.urlopen(req).read())
print("photo:", image["id"], img.name)

# A realistic degraded-soil reading: low N and P, acidic — gives a full advisory.
# On the INDEX scale the models use (N low<40, P/K low<30): genuinely deficient and acidic,
# so the chips, the score and the fertilizer plan all tell the same story.
rec = call("/soil-records", {"field_id": field["id"], "nitrogen": 55, "phosphorus": 22,
                             "potassium": 45, "ph": 5.9, "organic_matter": 0.68,
                             "moisture": 22}, tok=tok)
an = call("/analyze", {"field_id": field["id"], "soil_record_id": rec["id"],
                       "image_id": image["id"], "explain": True, "fuse": True}, tok=tok)
aid = an["analysis_id"]
stc = an.get("soil_type_classification") or {}
print("analysis:", aid, "| score", an.get("soil_health_score"),
      "| soil type", stc.get("soil_type"), stc.get("confidence"))

# Seed history so the TREND section appears too.
from datetime import datetime, timedelta
now = datetime.now()
# Prior seasons on the same index scale: healthy sliding to deficient.
for i, (n, p_, k, ph, om) in enumerate([
    (78, 55, 58, 6.9, 1.15), (62, 44, 47, 6.5, 0.94),
    (48, 33, 35, 6.1, 0.72), (38, 24, 28, 5.7, 0.54)]):
    call("/soil-records", {"field_id": field["id"],
        "sampled_at": (now - timedelta(days=120 * (4 - i))).isoformat(),
        "nitrogen": n, "phosphorus": p_, "potassium": k, "ph": ph,
        "organic_matter": om, "moisture": 24 - i}, tok=tok)
print("history seeded (4 prior seasons)")

# The deliverable: the PDF, with soil type AND the Grad-CAM overlay.
pdf = call("/reports/%d?include_soil_type=true&include_heatmap=true" % aid, tok=tok, raw=True)
path = OUT / "SAMPLE_soil_health_report.pdf"
path.write_bytes(pdf)
print("\nPDF written: %s  (%.1f kB)" % (path.name, len(pdf) / 1024))

from pypdf import PdfReader
r = PdfReader(path)
text = "\n".join(pg.extract_text() for pg in r.pages)
print("pages:", len(r.pages), "| embedded images:", sum(len(pg.images) for pg in r.pages))
print("sections:", [s for s in ("SOIL HEALTH REPORT", "NUTRIENT LEVELS", "SOIL TYPE",
                                "WHAT TO APPLY", "BEST-SUITED CROPS", "LONG-TERM TREND")
                    if s in text])
print("ANALYSIS_ID=%d" % aid)
