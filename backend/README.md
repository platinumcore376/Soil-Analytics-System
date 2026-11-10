# Backend — FastAPI Service

Soil image + lab-test ingestion (Phase 1) and the structured-data analysis engine
(Phase 2), backed by PostgreSQL.

Full API reference: [API_documentation.md](API_documentation.md)

## Prerequisites

- Python 3.11+ (developed on 3.13, conda `base`)
- **A running PostgreSQL server.** There is no SQLite fallback — the app aborts at startup
  if `DATABASE_URL` is missing, invalid, or unreachable.

## Setup

```bash
# from the repo root
pip install -r requirements.txt

# create the database
psql -U postgres -c "CREATE DATABASE soil_health;"

# configure
cp .env.example .env        # then set DATABASE_URL to your credentials
```

Config loads from the repo-root `.env`, with an optional `backend/.env` overriding it.

```
DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/soil_health
```

## Run

```bash
cd backend
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for interactive API docs.

## Endpoints

### Phase 1 — Ingestion

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness check |
| POST · GET | `/farms` | Create / list farms |
| POST | `/fields` | Create a field |
| GET | `/farms/{id}/fields` | List a farm's fields |
| POST | `/soil-records` | Submit lab values (N, P, K, pH, organic matter, moisture) |
| GET | `/soil-records/{id}` | One soil record |
| GET | `/soil-records/by-field/{id}` | Field history, chronological (trend-ready) |
| POST | `/images` | Upload JPEG/PNG **or** camera capture → validate → preprocess → store |
| GET | `/images/{id}` | Image metadata |

### Phase 2 — Analysis

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/analyze` | Soil health score, deficiency diagnosis, degradation risk, fertilizer advisory |
| GET | `/analysis-results/by-field/{id}` | Stored analyses for a field, newest first |
| GET | `/analysis-results/{id}` | One stored analysis |
| GET | `/models/info` | Loaded model metadata, metrics and caveats |

**Image upload** — `POST /images` (multipart): `file` (required), `field_id`, `source`
(`upload`|`camera`), `remove_background` (bool). Validates type/size/decodability, stores the
original, then writes a preprocessed copy (resize → colour-correct → optional GrabCut
background removal).

**Analysis** — `POST /analyze` accepts readings inline or via `soil_record_id`. Set
`explain: true` for SHAP feature attributions. Requires the trained artifacts (below).

## Model artifacts

The analysis endpoints load from `models/structured/`, produced by
[notebooks/train_structured.ipynb](../notebooks/train_structured.ipynb):

```bash
jupyter nbconvert --to notebook --execute notebooks/train_structured.ipynb --inplace
```

Artifacts load lazily and are cached, so a missing model does not stop the service from
starting — ingestion keeps working and only the analysis endpoints return `503`.

## Layout

```
backend/
├── app/
│   ├── main.py            # app + router wiring
│   ├── config.py          # env-driven settings (Pydantic), Postgres-only validation
│   ├── database.py        # engine/session/Base, startup connection probe
│   ├── models.py          # farms, fields, soil_records, images, analysis_results
│   ├── schemas.py         # Pydantic request/response
│   ├── preprocessing.py   # OpenCV pipeline + augmentation
│   ├── ml/
│   │   └── structured.py  # inference: score, diagnosis, risk index, SHAP
│   └── routers/           # farms, images, soil_records, analysis
├── storage/               # uploads + processed images (git-ignored)
├── API_documentation.md
└── README.md
```

Dependencies live in the repo-root [requirements.txt](../requirements.txt).

## Database

Five tables: `farms → fields → {soil_records, images, analysis_results}`. Missing tables are
created at startup; existing ones are never altered — use **Alembic** for schema changes.

A non-PostgreSQL `DATABASE_URL` (e.g. `sqlite://`) is rejected by config validation, so the
service can never silently write to a local file database.

## Notes

- Camera capture (`source=camera`) uses the same endpoint as file upload — the PWA posts the
  captured frame as a multipart file. Browser side (MediaDevices/getUserMedia) is Phase 3.
- Cloud object storage (S3/GCS) replaces local disk in Phase 3, along with replacing absolute
  filesystem paths in `stored_path` with opaque storage keys.
- No authentication on any endpoint yet — do not expose this service publicly.
