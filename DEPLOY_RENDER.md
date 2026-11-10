# Render Deployment Guide

The app runs as **two Render services** deployed from `render.yaml` in this repo:

| Service | What it is | Live URL |
|---|---|---|
| `soil-health-pwa` | The farmer-facing app (Next.js) | https://soil-health-pwa.onrender.com |
| `soil-health-api` | The FastAPI backend | https://soil-health-api-0cxm.onrender.com |

Data lives in **Supabase** (PostgreSQL, region `ap-south-1`) — not on Render.
This file has no secret values; wherever a value is needed, it tells you which key
to set and where to get its value.

---

## Part 1 — Deploying from scratch

Use this if the services were deleted and you need to recreate everything.

### Prepare two values first

**A. `DATABASE_URL`** — the Supabase *session pooler* string:

1. Supabase dashboard → your project → **Connect** (top bar) → **Session pooler** tab (port 5432).
2. Copy the URI shown there and make two edits:
   - Replace `[YOUR-PASSWORD]` with your database password (`DB_PASSWORD` in your local `.env`) — **URL-encoded**: any special characters must be encoded (`#`→`%23`, `&`→`%26`, `]`→`%5D`, `>`→`%3E`, `@`→`%40`).
   - Change the trailing database name to `/soil_analysis`.
3. Sanity-check the result has all three fingerprints:
   - host contains `pooler.supabase.com` (NOT `db.…supabase.co` — that host is IPv6-only and **unreachable from Render**; it works only on your PC)
   - username is the long form `postgres.<project-ref>` (the pooler rejects plain `postgres` with "Tenant or user not found")
   - ends with `/soil_analysis`

**B. `SARVAM_API_KEY`** (optional) — copy from your local `.env`. Leaving it empty
is fine: voice falls back to the phone's own speech.

### Deploy

1. https://render.com → sign in with GitHub. Ensure Render has access to the
   **`sasank-in/soil_test`** repository (it is private, so this grant is required).
2. **New → Blueprint** → select `sasank-in/soil_test`, branch `main`.
   Render reads `render.yaml` and lists both services, pre-configured (free plans,
   build commands, root directories).
3. Fill the prompts:

   | Prompt | What to enter |
   |---|---|
   | `DATABASE_URL` | The pooler string from step A |
   | `SARVAM_API_KEY` | Your key, or leave empty |
   | `BACKEND_URL` | Leave empty — set in the next step |

   (`JWT_SECRET` is not prompted — Render generates it.)
4. Name the blueprint anything (it's only a dashboard label) → **Apply**.
5. Wait for `soil-health-api` to show **Live** (~5 min). Its logs should end with
   `Uvicorn running…`. On first start it creates the database tables automatically.
6. Copy the API's **actual URL** from the top of its page. ⚠️ It may carry a random
   suffix (ours got `-0cxm`) if the bare name is taken — always copy, never guess.
7. `soil-health-pwa` → **Environment** → set `BACKEND_URL` to that URL
   (include `https://`, no trailing slash) → **Save**. The PWA redeploys itself.

### Verify

1. `https://<api-url>/health` → `{"status":"ok", …}`
2. `https://<api-url>/docs` → API documentation loads
3. `https://<pwa-url>/api/health` → same `ok` JSON (proves the PWA→API proxy works)
4. On a phone: open the PWA → sign up → add a plot → enter a reading → run the
   analysis → download the PDF report
5. Supabase → **Table Editor** → your new account appears in `users`

---

## Part 2 — Day-to-day operations

### Updating the app
Just `git push` to `main` — both services redeploy automatically (and CI runs on
GitHub). Rollback: service → **Events** → pick the previous deploy → **Rollback**.

### Stopping the app (e.g. after the evaluation)
1. `soil-health-pwa` → **Settings** → scroll to the bottom → **Suspend Service** → confirm
2. Repeat for `soil-health-api`

Suspended services cost nothing and keep all settings and env vars; their URLs just
stop responding. Suspend **both** — stopping only the PWA leaves the API reachable.
Data is untouched (it's in Supabase; to pause that too: Supabase → Project Settings
→ Pause project). Use **Suspend, never Delete** — Delete erases the service and its
env vars, forcing a full redeploy from Part 1. While suspended, pushes don't deploy.

### Bringing it back
Open each service → **Resume Service** banner → click. Live in ~2–3 minutes.

---

## Part 3 — Known behaviors (not bugs)

| Behavior | Explanation |
|---|---|
| First request after a pause takes 30–60 s | Free services sleep after ~15 idle minutes. Open the app a minute before demoing. |
| Soil-photo classification returns 503 | The CNN (torch) is deliberately excluded from the free-tier build — too large for 512 MB RAM. Everything else works. To enable: ≥2 GB instance, plain `pip install` in `render.yaml`, upload `models/cnn/soil_resnet50.pth`. |
| Old photos disappear from results | By design: image files are deleted once the PDF report is generated (24 h backstop sweep otherwise). Scores, readings, trends are in Supabase and permanent. |
| Voice sounds robotic | `SARVAM_API_KEY` empty or out of credits — on-device speech fallback kicked in. |

## Part 4 — Troubleshooting

| Symptom | Fix |
|---|---|
| API logs: `Cannot connect to PostgreSQL … Network is unreachable` (IPv6 address shown) | `DATABASE_URL` is using the direct `db.…supabase.co` host. Replace with the **pooler** string (Part 1, step A). This bit us twice — check the three fingerprints. |
| API logs: `Tenant or user not found` | Pooler username lost its suffix — must be `postgres.<project-ref>`, not plain `postgres`. |
| API logs: password/auth error | Password not URL-encoded inside the URL — re-do the encoding from step A. |
| App loads but every action fails | `BACKEND_URL` on the PWA is wrong — usually the missing random suffix (step 6) or a trailing slash. |
| PWA build fails | Service → Events → **Manual deploy** to retry; check logs if it repeats. |
