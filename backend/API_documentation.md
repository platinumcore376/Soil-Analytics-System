# Soil Health Assessment API

**AI-Based Soil Health Assessment System for Nutrient Deficiency Detection and Crop Recommendation**

| | |
|---|---|
| **Version** | `0.2.0` |
| **Base URL** | `http://127.0.0.1:8000` |
| **Stack** | FastAPI · Uvicorn · PostgreSQL 16 |
| **Spec** | OpenAPI 3.1.0 — [`/openapi.json`](http://127.0.0.1:8000/openapi.json) |
| **Interactive** | [`/docs`](http://127.0.0.1:8000/docs) (Swagger UI) · [`/redoc`](http://127.0.0.1:8000/redoc) |
| **Auth** | None — do not expose publicly |

**Phase 1** ingests soil images and lab readings. **Phase 2** turns those readings into a
soil health score, deficiency diagnosis, degradation risk index and fertilizer advisory.

---

## Contents

[1. Quick Start](#1-quick-start) · [2. Endpoints](#2-endpoints) · [3. Conventions](#3-conventions) ·
[4. Data Model](#4-data-model) · [5. Farms & Fields](#5-farms--fields) ·
[6. Soil Records](#6-soil-records) · [7. Images](#7-images) · [8. Analysis](#8-analysis) ·
[9. Parameter Reference](#9-parameter-reference) · [10. Errors](#10-errors) ·
[11. Operations](#11-operations) · [12. Roadmap](#12-roadmap)

---

## 1. Quick Start

Complete flow — register a farm, add a field, submit readings, get a diagnosis.

```bash
BASE=http://127.0.0.1:8000

# 1. Create a farm
curl -X POST http://127.0.0.1:8000/farms -H "Content-Type: application/json" \
  -d '{"name":"Green Acres","owner_name":"Ramesh Kumar","location":"Mandya, Karnataka"}'
# -> {"id": 6, ...}

# 2. Create a field inside it
curl -X POST $BASE/fields -H "Content-Type: application/json" \
  -d '{"farm_id":6,"name":"North Plot","area_hectares":2.5}'
# -> {"id": 5, ...}

# 3. Submit lab readings
curl -X POST $BASE/soil-records -H "Content-Type: application/json" \
  -d '{"field_id":5,"nitrogen":90,"phosphorus":42,"potassium":43,"ph":6.5}'

# 4. Diagnose
curl -X POST $BASE/analyze -H "Content-Type: application/json" \
  -d '{"field_id":5,"nitrogen":28,"phosphorus":22,"potassium":33,"ph":5.9,
       "organic_matter":0.6,"moisture":30}'
```

**Health check**

```bash
curl $BASE/health
```
```json
{ "status": "ok", "phase": "1 - data ingestion, 2 - analysis engine" }
```

---

## 2. Endpoints

| # | Method | Path | Purpose | OK |
|---|---|---|---|---|
| 1 | `GET` | `/` | Service metadata | `200` |
| 2 | `GET` | `/health` | Liveness probe | `200` |
| 3 | `POST` | `/farms` | Create farm | `201` |
| 4 | `GET` | `/farms` | List farms | `200` |
| 5 | `POST` | `/fields` | Create field | `201` |
| 6 | `GET` | `/farms/{farm_id}/fields` | List a farm's fields | `200` |
| 7 | `POST` | `/soil-records` | Submit lab readings | `201` |
| 8 | `GET` | `/soil-records/{record_id}` | One record | `200` |
| 9 | `GET` | `/soil-records/by-field/{field_id}` | Field history, oldest first | `200` |
| 10 | `POST` | `/images` | Upload + preprocess soil image | `201` |
| 11 | `GET` | `/images/{image_id}` | Image metadata | `200` |
| 12 | `POST` | `/analyze` | **Diagnose soil** | `201` |
| 13 | `GET` | `/analysis-results/by-field/{field_id}` | Stored analyses, newest first | `200` |
| 14 | `GET` | `/analysis-results/{analysis_id}` | One analysis | `200` |
| 15 | `GET` | `/models/info` | Model metadata + metrics | `200` |

---

## 3. Conventions

| Aspect | Value |
|---|---|
| Content type | `application/json`; `multipart/form-data` for `POST /images` |
| Timestamps | ISO 8601, microsecond precision, **naive local server time** |
| Numbers | Measurements always return as floats (`90` → `90.0`) |
| Trailing slash | Omit it. `POST /images/` returns `307` and some clients drop the body on redirect. |

---

## 4. Data Model

```
Farm 1──* Field 1──* SoilRecord
                1──* Image
                1──* AnalysisResult
```

| Table | Contents |
|---|---|
| `farms` | Farm identity and owner |
| `fields` | Plots within a farm — area, geolocation |
| `soil_records` | Lab readings over time |
| `images` | Uploaded photos + preprocessing metadata |
| `analysis_results` | Diagnoses written by `POST /analyze` |

Deleting a farm cascades to its fields; deleting a field cascades to its records, images and
analyses. `analysis_results` uses `ON DELETE SET NULL` for its record/image links, so a
diagnosis survives deletion of its source.

---

## 5. Farms & Fields

### `POST /farms`

| Field | Type | Req | Example |
|---|---|---|---|
| `name` | string | ✅ | `"Green Acres"` |
| `owner_name` | string | — | `"Ramesh Kumar"` |
| `location` | string | — | `"Mandya, Karnataka"` |

```json
{
  "id": 6,
  "name": "Green Acres",
  "owner_name": "Ramesh Kumar",
  "location": "Mandya, Karnataka",
  "created_at": "2026-08-05T09:30:31.522065"
}
```

`GET /farms` returns an array of the same shape, ordered by `id`.

### `POST /fields`

| Field | Type | Req | Example | Notes |
|---|---|---|---|---|
| `farm_id` | int | ✅ | `6` | `404` if absent |
| `name` | string | ✅ | `"North Plot"` | |
| `area_hectares` | float | — | `2.5` | |
| `latitude` | float | — | `12.5223` | Bounds not validated |
| `longitude` | float | — | `76.8956` | Bounds not validated |

```json
{
  "id": 5,
  "farm_id": 6,
  "name": "North Plot",
  "area_hectares": 2.5,
  "latitude": 12.5223,
  "longitude": 76.8956,
  "created_at": "2026-08-05T09:30:31.723329"
}
```

`GET /farms/{farm_id}/fields` returns an array; `[]` if the farm has no fields, `404` if the
farm does not exist.

---

## 6. Soil Records

One set of lab readings for a field at a point in time. Successive records build the series
the degradation trend uses.

### `POST /soil-records`

Only `field_id` is mandatory — partial soil test reports are accepted.

| Field | Type | Req | Range | Unit | Example |
|---|---|---|---|---|---|
| `field_id` | int | ✅ | must exist | — | `5` |
| `nitrogen` | float | — | ≥ 0 | kg/ha | `90` |
| `phosphorus` | float | — | ≥ 0 | kg/ha | `42` |
| `potassium` | float | — | ≥ 0 | kg/ha | `43` |
| `ph` | float | — | 0–14 | pH | `6.5` |
| `organic_matter` | float | — | 0–100 | % | `3.2` |
| `moisture` | float | — | 0–100 | % | `22.4` |
| `temperature` | float | — | — | °C | `20.9` |
| `humidity` | float | — | 0–100 | % | `82` |
| `rainfall` | float | — | ≥ 0 | mm | `202.9` |
| `sampled_at` | datetime | — | ISO 8601 | — | `"2026-07-20T09:30:00"` |

> `temperature`, `humidity` and `rainfall` are environmental context, not soil chemistry.
> They are stored for the Phase 3 crop model and are **not** used by the analysis engine.

**Complete submission**

```bash
curl -X POST $BASE/soil-records -H "Content-Type: application/json" \
  -d '{"field_id":5,"nitrogen":90,"phosphorus":42,"potassium":43,"ph":6.5,
       "organic_matter":3.2,"moisture":22.4,"temperature":20.9,"humidity":82,
       "rainfall":202.9,"sampled_at":"2026-07-20T09:30:00"}'
```
```json
{
  "id": 9,
  "field_id": 5,
  "nitrogen": 90.0,
  "phosphorus": 42.0,
  "potassium": 43.0,
  "ph": 6.5,
  "organic_matter": 3.2,
  "moisture": 22.4,
  "temperature": 20.9,
  "humidity": 82.0,
  "rainfall": 202.9,
  "sampled_at": "2026-07-20T09:30:00",
  "created_at": "2026-08-05T09:30:52.070049"
}
```

**Minimal submission** — NPK + pH only, as on a basic Soil Health Card. Omitted analytes
return `null`; `sampled_at` defaults to now.

```bash
curl -X POST $BASE/soil-records -H "Content-Type: application/json" \
  -d '{"field_id":5,"nitrogen":18,"phosphorus":12,"potassium":15,"ph":5.4}'
```
```json
{
  "id": 10,
  "field_id": 5,
  "nitrogen": 18.0,
  "phosphorus": 12.0,
  "potassium": 15.0,
  "ph": 5.4,
  "organic_matter": null,
  "moisture": null,
  "temperature": null,
  "humidity": null,
  "rainfall": null,
  "sampled_at": "2026-08-05T09:30:52.297746",
  "created_at": "2026-08-05T09:30:52.297746"
}
```

### `GET /soil-records/by-field/{field_id}`

Array ordered by **ascending `sampled_at`** — feed it straight to time-series analysis
without re-sorting. `[]` if empty, `404` if the field does not exist.

---

## 7. Images

### `POST /images`

`multipart/form-data`. Same endpoint for file picker and camera capture.

| Field | Type | Req | Default | Notes |
|---|---|---|---|---|
| `file` | binary | ✅ | — | JPEG or PNG |
| `field_id` | int | — | `null` | `404` if absent |
| `source` | string | — | `upload` | `upload` or `camera`; other values coerce to `upload` |
| `remove_background` | bool | — | `true` | GrabCut isolation — slower |

**Pipeline** — validate → store original → resize (longest side 1024 px) → gray-world white
balance + CLAHE → optional GrabCut background removal → store derivative.

```bash
curl -X POST $BASE/images \
  -F "file=@soil.jpg" -F "field_id=5" -F "source=camera" -F "remove_background=true"
```
```json
{
  "id": 5,
  "field_id": 5,
  "original_filename": "Red_Soil_208.jpg",
  "stored_path": "<...>/backend/storage/uploads/a502edc9506d45c1a01e4666a51afd4d.jpg",
  "processed_path": "<...>/backend/storage/processed/a502edc9506d45c1a01e4666a51afd4d_proc.jpg",
  "content_type": "image/jpeg",
  "source": "camera",
  "file_size": 23275,
  "width": 256,
  "height": 256,
  "created_at": "2026-08-05T09:30:52.496303"
}
```

> `file_size` describes the **original**; `width`/`height` describe the **processed**
> derivative. Different artefacts.

**Browser (Phase 3 PWA)**

```javascript
const form = new FormData();
form.append("file", blob, "capture.jpg");   // blob from a canvas capture
form.append("field_id", "5");
form.append("source", "camera");
await fetch(`${BASE}/images`, { method: "POST", body: form });
// Do not set Content-Type — the browser adds the multipart boundary.
```

**Validation**

| Condition | Status |
|---|---|
| Not JPEG/PNG | `415` |
| Empty or undecodable | `400` |
| Over `MAX_UPLOAD_MB` (10) | `413` |
| `field_id` not found | `404` |

`GET /images/{image_id}` returns metadata only — **no endpoint serves the image binary yet.**

---

## 8. Analysis

Implements the Weeks 3–4 requirement: *"Serve the model via a FastAPI endpoint returning soil
health scores, deficiency diagnoses, and degradation risk indices."*

| Output | Produced by |
|---|---|
| Deficiency status | **Threshold rule (authoritative)** — models annotate only |
| Soil health score | Weighted deduction from 100 |
| Degradation risk | Current condition + OLS trend over field history |
| Fertilizer advisory | XGBoost, 10 classes, 97.9% accuracy |

> **Why the rule decides.** No dataset carries ground-truth deficiency labels, so the
> gradient-boosted models were trained on labels derived from the same threshold bands — they
> score ~99% by relearning a rule, not by discovering agronomy. They contribute calibrated
> probabilities and SHAP attributions. On disagreement the rule wins and the conflict appears
> in `model_agreement.disagreements`, flagging a near-boundary reading.

### `POST /analyze`

Readings inline **or** by `soil_record_id`. Inline wins field-by-field when both are given.

| Field | Type | Req | Default | Example |
|---|---|---|---|---|
| `field_id` | int | ✅ | — | `5` |
| `soil_record_id` | int | — | `null` | `10` |
| `nitrogen` `phosphorus` `potassium` | float | — | `null` | `28` `22` `33` |
| `ph` | float | — | `null` | `5.9` |
| `organic_matter` `moisture` | float | — | `null` | `0.6` `30` |
| `include_history` | bool | — | `true` | Trend term |
| `explain` | bool | — | `false` | SHAP attributions |
| `persist` | bool | — | `true` | Write to `analysis_results` |

At least one reading must resolve, inline or via the record, else `422`. Blanks are imputed
from the training median and listed in `imputed_features`.

```bash
curl -X POST $BASE/analyze -H "Content-Type: application/json" \
  -d '{"field_id":5,"nitrogen":28,"phosphorus":22,"potassium":33,"ph":5.9,
       "organic_matter":0.6,"moisture":30,"explain":true}'
```

```json
{
  "analysis_id": 3,
  "field_id": 5,
  "soil_record_id": null,
  "persisted": true,
  "soil_health_score": 36.0,
  "health_band": "critical",
  "diagnosis": {
    "nitrogen": "low",
    "phosphorus": "low",
    "potassium": "adequate",
    "ph": "acidic"
  },
  "diagnosis_detail": {
    "nitrogen": {
      "status": "low",
      "source": "threshold_rule",
      "model_status": "low",
      "model_confidence": 0.9846,
      "model_confidence_in_rule_status": 0.9846,
      "explanation": [
        { "feature": "nitrogen", "value": 28.0, "shap_value": 4.3296, "direction": "increases" },
        { "feature": "ph", "value": 5.9, "shap_value": 0.3884, "direction": "increases" }
      ]
    }
  },
  "degradation_risk": {
    "index": 0.784,
    "band": "severe",
    "basis": "current_condition_and_trend",
    "trend_slope": -28.0,
    "records_used": 3,
    "note": "Negative trend_slope indicates declining soil health across successive records."
  },
  "fertilizer_recommendation": {
    "recommended": "Urea",
    "advisory": "Provides high nitrogen, ideal for rapid leafy growth. Prefer this for nitrogen-deficient soils as it supports vegetative growth.",
    "alternatives": [
      { "fertilizer": "DAP", "confidence": 0.0043, "advisory": "Rich in phosphorus, essential for root development..." }
    ],
    "explanation": [
      { "feature": "nitrogen", "value": 28.0, "shap_value": 5.7782, "direction": "increases" }
    ]
  },
  "inputs_used": {
    "nitrogen": 28.0, "phosphorus": 22.0, "potassium": 33.0,
    "ph": 5.9, "organic_matter": 0.6, "moisture": 30.0
  },
  "imputed_features": [],
  "model_agreement": { "rule_is_authoritative": true, "disagreements": [] }
}
```

`diagnosis_detail` carries one block per nutrient — `phosphorus`, `potassium` and `ph` follow
the same shape, trimmed here.

**Response fields**

| Field | Meaning |
|---|---|
| `analysis_id` | Stored row id; `null` when `persist: false` |
| `soil_health_score` | 0–100 composite |
| `health_band` | `good` ≥ 80 · `moderate` ≥ 60 · `poor` ≥ 40 · `critical` < 40 |
| `diagnosis` | NPK: `low`/`adequate`/`high` · pH: `acidic`/`neutral`/`alkaline` |
| `…low_training_support` | Present when a class had too few training rows to trust |
| `degradation_risk.index` | 0–1, higher is worse |
| `degradation_risk.band` | `low` < 0.25 · `moderate` < 0.5 · `high` < 0.75 · `severe` |
| `degradation_risk.trend_slope` | Score change per record. **Negative = declining.** `null` with < 2 records |
| `imputed_features` | Parameters filled from the training median |

**Degradation trend** — OLS slope over the health scores of *all* the field's records,
**including** the one under analysis, so the line terminates at present condition. Scores are
recomputed each call, never read back from `analysis_results`, so a scoring-model change
cannot produce a mixed-vintage series. Under 2 records: `trend_slope: null`,
`basis: "current_condition_only"`.

> **Potassium `low` has ~2 training rows** out of 2,870 — the dataset's K values rarely fall
> below the threshold. The rule detects it correctly; model confidence for that class is
> unreliable, so the response sets `low_training_support: true`.

### `GET /analysis-results/by-field/{field_id}`

Newest first. Query: `limit` (default `50`, max `500`).

```bash
curl "$BASE/analysis-results/by-field/5?limit=10"
```
```json
[
  {
    "id": 3,
    "field_id": 5,
    "soil_record_id": null,
    "image_id": null,
    "soil_health_score": 36.0,
    "diagnosis": "{\"nitrogen\": \"low\", \"phosphorus\": \"low\", \"potassium\": \"adequate\", \"ph\": \"acidic\"}",
    "degradation_risk_index": 0.784,
    "recommended_crop": "Urea",
    "created_at": "2026-08-05T09:31:09.047076"
  }
]
```

> Two quirks: `diagnosis` is a **JSON-encoded string**, not a nested object — parse it
> client-side. And `recommended_crop` currently holds the **fertilizer** name; the column is
> repurposed when Phase 3 adds crop suitability.

### `GET /models/info`

```bash
curl $BASE/models/info
```
```json
{
  "available": true,
  "feature_order": ["nitrogen", "phosphorus", "potassium", "ph", "organic_matter", "moisture"],
  "feature_units": { "nitrogen": "kg/ha", "ph": "0-14", "organic_matter": "%", "moisture": "%" },
  "thresholds": {
    "nitrogen":   { "low": 40.0, "high": 80.0 },
    "phosphorus": { "low": 30.0, "high": 60.0 },
    "potassium":  { "low": 30.0, "high": 60.0 }
  },
  "ph_bands": { "acidic": "< 6.0", "neutral": "6.0 - 7.5", "alkaline": "> 7.5" },
  "training_data": {
    "source": "fertilizer_recommendation.csv",
    "rows_raw": 3100,
    "rows_after_cleaning": 2870,
    "rows_dropped": 230,
    "drop_reason": "negative nutrient/carbon values or out-of-range pH/moisture"
  },
  "metrics": {
    "deficiency_nitrogen":   { "accuracy": 0.9948, "f1_macro": 0.9724 },
    "deficiency_phosphorus": { "accuracy": 0.9983, "f1_macro": 0.9988 },
    "deficiency_potassium":  { "accuracy": 0.9983, "f1_macro": 0.6655 },
    "deficiency_ph":         { "accuracy": 0.9983, "f1_macro": 0.9966 },
    "fertilizer":            { "accuracy": 0.9791, "f1_macro": 0.9204 }
  },
  "caveats": ["Deficiency labels are DERIVED from the threshold bands above ..."]
}
```

> Read `deficiency_potassium`: accuracy `0.9983` but macro-F1 `0.6655`. The gap is the
> untrained `low` class — exactly why macro-F1 is reported alongside accuracy.

---

## 9. Parameter Reference

| Parameter | Unit | Accepted | Interpretation bands |
|---|---|---|---|
| `nitrogen` | kg/ha | ≥ 0 | low < 40 · adequate 40–80 · high > 80 |
| `phosphorus` | kg/ha | ≥ 0 | low < 30 · adequate 30–60 · high > 60 |
| `potassium` | kg/ha | ≥ 0 | low < 30 · adequate 30–60 · high > 60 |
| `ph` | pH | 0–14 | acidic < 6.0 · neutral 6.0–7.5 · alkaline > 7.5 |
| `organic_matter` | % | 0–100 | score penalty < 0.75 |
| `moisture` | % | 0–100 | score penalty < 20 or > 80 |

**Score deductions from 100** — nutrient `low` −18, `high` −8 · pH out of band −22 · organic
matter < 0.5% −12 or < 0.75% −6 · moisture out of range −8. pH carries the heaviest single
penalty because it gates nutrient availability.

> Bands are **provisional**. Calibrate against ICAR Soil Health Card reference ranges for the
> target region before producing real farmer advisories.

---

## 10. Errors

Two response shapes. Application errors put a **string** in `detail`; validation errors put an
**array**. Client handlers must check the type.

```json
{ "detail": "Field 9999 not found." }
```

```json
{
  "detail": [
    {
      "type": "less_than_equal",
      "loc": ["body", "ph"],
      "msg": "Input should be less than or equal to 14",
      "input": 99,
      "ctx": { "le": 14.0 }
    }
  ]
}
```

| Status | Meaning | Example trigger → response |
|---|---|---|
| `400` | Bad payload | Record/field mismatch → `"Soil record 3 belongs to field 3, not field 5."` |
| `404` | Not found | Unknown field → `"Field 9999 not found."` · unknown image → `"Image not found."` |
| `413` | Too large | 30 MB upload → `"File exceeds 10 MB limit."` |
| `415` | Wrong type | `.txt` upload → `"Unsupported type 'text/plain'. Allowed: JPEG, PNG."` |
| `422` | Validation | `ph: 99` → field-level array · no readings → `"No soil readings supplied. Provide at least one of ..."` |
| `503` | Models absent | `"Trained model artifacts are unavailable. Run the training notebook ..."` |

---

## 11. Operations

### Configuration

Loaded from the repo-root `.env`; an optional `backend/.env` overrides it.

| Variable | Req | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | PostgreSQL only — other schemes rejected at startup |
| `UPLOAD_DIR` | — | `./storage/uploads` | Originals |
| `PROCESSED_DIR` | — | `./storage/processed` | Derivatives |
| `MAX_UPLOAD_MB` | — | `10` | Upload ceiling |
| `TARGET_IMAGE_SIZE` | — | `1024` | Longest-side resize, px |
| `CORS_ORIGINS` | — | `localhost:3000` | Comma-separated |

```
DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/soil_health
```

### Startup

A `SELECT 1` probe runs at boot; the app **aborts with a diagnostic** if PostgreSQL is
unreachable. There is no fallback datastore. Missing tables are created; existing tables are
never altered — use **Alembic** for migrations.

### Model artifacts

Analysis endpoints load from `models/structured/`, generated by:

```bash
jupyter nbconvert --to notebook --execute notebooks/train_structured.ipynb --inplace
```

Artifacts load lazily and cache for the process lifetime. A missing model does not block
startup — ingestion keeps working and only analysis returns `503`.

### Known limitations

| Area | Limitation |
|---|---|
| Auth | None on any endpoint |
| Pagination | `GET /farms` and history endpoints return full result sets |
| Mutation | No `PUT`/`PATCH`/`DELETE` — records cannot be corrected via the API |
| Image retrieval | No endpoint serves image binaries |
| Path disclosure | `stored_path` exposes absolute server paths |
| Timezone | Naive local time; standardise on UTC before multi-region deployment |
| Geo validation | `latitude`/`longitude` bounds unenforced |
| Concurrency | GrabCut runs synchronously and blocks the worker |
| Trend cost | `POST /analyze` rescores every record of the field — O(n) per call |
| Deficiency models | Trained on rule-derived labels; accuracy ≠ agronomic skill |
| Image inference | Structured data only — `image_id` on analyses is always `null` |

---

## 12. Roadmap

**Phase 2 delivered** — `POST /analyze`, `/analysis-results/*`, `/models/info`, SHAP via
`explain: true`.

**Phase 2 outstanding**

| Item | Blocker |
|---|---|
| CNN image inference | Retrain first — current checkpoint has train/val leakage and targets 5 generic classes, not the 4 Indian agricultural soils |
| Grad-CAM heatmaps | Needs the CNN served |
| Hybrid fusion model | Needs the CNN; image and tabular datasets share no sample IDs, so late fusion at inference is the practical path |

**Phase 3 — Weeks 5–6**

| Endpoint | Purpose |
|---|---|
| `GET /recommendations/{analysis_id}` | Dosage and application schedule (fertilizer type already ships in `/analyze`) |
| `GET /crop-suitability/{field_id}` | Ranked crop recommendations |
| `GET /trends/{field_id}` | Forward-looking degradation projection |
| `GET /reports/{field_id}` | Downloadable PDF soil health report |

Also Phase 3: migrate image storage to S3/GCS, replacing absolute paths with opaque keys.

---

<sub>API `0.2.0` · Updated 5 August 2026 · All examples captured from a live instance against
PostgreSQL 16.10 · Source of truth: [`/openapi.json`](http://127.0.0.1:8000/openapi.json)</sub>
