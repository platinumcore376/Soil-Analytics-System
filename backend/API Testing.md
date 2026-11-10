## Run

```bash
cd backend
uvicorn app.main:app --reload
```




1. POST /farms

json
{
  "name": "Green Acres",
  "owner_name": "Ramesh Kumar",
  "location": "Mandya, Karnataka"
}

2. GET /farms — no body

3. POST /fields

json
{
  "farm_id": 1,
  "name": "North Plot",
  "area_hectares": 2.5,
  "latitude": 12.5223,
  "longitude": 76.8956
}

4. GET /farms/{farm_id}/fields — no body, use farm_id from step 1

5. POST /soil-records (full submission)

json
{
  "field_id": 5,
  "nitrogen": 90,
  "phosphorus": 42,
  "potassium": 43,
  "ph": 6.5,
  "organic_matter": 3.2,
  "moisture": 22.4,
  "temperature": 20.9,
  "humidity": 82,
  "rainfall": 202.9,
  "sampled_at": "2026-07-20T09:30:00"
}

5b. POST /soil-records (minimal — NPK + pH only, to test optional fields)

json
{
  "field_id": 5,
  "nitrogen": 18,
  "phosphorus": 12,
  "potassium": 15,
  "ph": 5.4
}

6. GET /soil-records/{record_id} — no body, use id from step 5

7. GET /soil-records/by-field/{field_id} — no body

8. POST /images — multipart form, not JSON:

file: soil.jpg
field_id: 5
source: camera
remove_background: true

9. GET /images/{image_id} — no body, use id from step 8

10. POST /analyze (inline readings, matches the doc's own example)

json
{
  "field_id": <the id from POST /fields>,
  "nitrogen": 55,
  "phosphorus": 22,
  "potassium": 180,
  "ph": 5.9,
  "ec": 0.45,
  "s": 0.22,
  "cu": 8.5,
  "fe": 80,
  "mn": 45,
  "zn": 40,
  "b": 25,
  "temperature": 26,
  "humidity": 75,
  "rainfall": 150,
  "image_id": <the id from POST /images>,
  "explain": true,
  "fuse": true,
  "persist": true
}

10b. POST /analyze — via soil_record_id instead of inline values

json
{
  "field_id": 5,
  "soil_record_id": 9,
  "explain": true,
  "persist": true
}

10c. POST /analyze — crop model regression test #1 (to verify your weather= fix from earlier — pair this with 10d, keep N/P/K/ph identical, only change weather)

json
{
  "field_id": <the id from POST /fields>,
  "nitrogen": 55,
  "phosphorus": 22,
  "potassium": 180,
  "ph": 5.9,
  "ec": 0.45,
  "s": 0.22,
  "cu": 8.5,
  "fe": 80,
  "mn": 45,
  "zn": 40,
  "b": 25,
  "temperature": 26,
  "humidity": 75,
  "rainfall": 150,
  "image_id": <the id from POST /images>,
  "explain": true,
  "fuse": true,
  "persist": true
}

10d. POST /analyze — crop model regression test #2 (same N/P/K/ph as 10c, different weather — crop_recommendation.recommended should now differ if the fix worked)

json
{
  "field_id": <the id from POST /fields>,
  "nitrogen": 55,
  "phosphorus": 22,
  "potassium": 180,
  "ph": 5.9,
  "ec": 0.45,
  "s": 0.22,
  "cu": 8.5,
  "fe": 80,
  "mn": 45,
  "zn": 40,
  "b": 25,
  "temperature": 26,
  "humidity": 75,
  "rainfall": 150,
  "image_id": <the id from POST /images>,
  "explain": true,
  "fuse": true,
  "persist": true
}

10e. POST /analyze — error case, no readings at all (expect 422)

json
{
  "field_id": <the id from POST /fields>,
  "persist": false
}

11. GET /analysis-results/by-field/{field_id}?limit=10 — no body

12. GET /analysis-results/{analysis_id} — no body, use analysis_id from step 10

13. GET /models/info — no body