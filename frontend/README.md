# Frontend — Farmer-Facing PWA

Mobile-first Progressive Web App (Weeks 5–6, Module 3). Next.js 16 App Router,
TypeScript, Tailwind. Installable on Android Chrome without an app store.

## Run

The backend must be running first — see [../backend/README.md](../backend/README.md).

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

```bash
npm run build && npm run start   # production
npm run typecheck                # catalogue parity check + tsc --noEmit
npm run check-locales            # catalogue parity only
```

The backend URL defaults to `http://127.0.0.1:8000`. Override with `BACKEND_URL`.

## Why the API is proxied

`next.config.mjs` rewrites `/api/*` to the backend. Two reasons:

1. **Single origin** — no CORS configuration, and no preflight round-trip on a slow link.
2. **Secure context** — `getUserMedia` requires one. `localhost` counts, so the camera
   works in development without setting up TLS.

## Screens

| Route | Purpose |
|---|---|
| `/signin` | Sign in with phone **or** email / create account (the only public route) |
| `/` | Plot picker, add a plot (creates the farm row behind the scenes) |
| `/capture` | Choose input path |
| `/capture/camera` | MediaDevices capture, with native-camera fallback |
| `/capture/manual` | NPK/pH numeric entry → triggers `POST /analyze` |
| `/results/[analysisId]` | Score, diagnosis, fertilizer plan, top crops, read-aloud |
| `/results/[analysisId]/crops` | Full 22-crop ranking with limiting factors |
| `/results/[analysisId]/trend` | History sparkline + forward projection |

A soil photo alone cannot produce a diagnosis — the score comes from lab chemistry — so
the camera screen carries its `image_id` into the manual form rather than analysing
directly. That attaches the photo to the analysis and lets the fusion model use the
predicted soil type.

## Layout

```
src/
├── app/                      routes (App Router)
├── components/
│   ├── AppChrome.tsx         header, language switch, offline banner, SW registration
│   ├── ScoreDial.tsx         the headline 0–100 gauge
│   ├── SpeakButton.tsx       Sarvam TTS with on-device fallback
│   └── ui.tsx                Card, BigButton, StatusChip, Spinner, ErrorNote
├── lib/
│   ├── api.ts                typed client for all 23 endpoints
│   ├── types.ts              response shapes
│   ├── i18n.ts               locale constants, speech tags, error-key map
│   ├── tkey.ts               TKey — valid translation keys (build-time safety)
│   ├── LocaleProvider.tsx    typed useLocale() over next-i18next + LocaleSync
│   ├── status.ts             status → colour + icon + label
│   └── useField.ts           selected field from localStorage
public/
├── manifest.webmanifest
├── sw.js                     service worker (hand-written)
├── favicon.ico              7 frames, each drawn at its own size
└── icons/                    favicon 16/32/48, 192, 512, maskable-512, apple-touch
```

## Authentication

`/signin` handles both sign-in and sign-up behind one mode toggle — the fields overlap
almost entirely, and a farmer on the wrong one should not have to navigate.

**Sign-in takes one field** that accepts either a mobile number or an email address; the
backend distinguishes them by looking for an "@", so the farmer never picks a field type.
The keyboard follows suit — numeric until an "@" is typed, then text. Sign-up shows both
as separate optional inputs, because there the values mean different things and at least
one must be stored.

The token lives in `localStorage`, not a cookie: the service worker replays queued writes
from its own context, where a cookie would not be attached. Acceptable exposure here since
the app renders no user-supplied HTML.

`AuthProvider` validates a stored token against `/auth/me` on startup rather than trusting
it — it may have expired while the app was closed, and finding out on the first data request
would dump the farmer onto an error screen. `AppChrome` guards every route except `/signin`
and withholds children until the session is known, so no protected screen ever flashes.

Two endpoints need special handling because the browser will not attach an `Authorization`
header for them: **image binaries** are fetched as blob URLs, and the **PDF report** is
fetched then handed to a synthetic `<a download>`.

Any `401` clears the token and the selected field — leaving the field would show another
user's plot name after a switch.

## Accessibility and low-literacy design

Every finding carries **three** redundant signals — a colour, an icon, and a number or
word — so meaning survives greyscale printing, colour-vision deficiency, and limited
literacy. `src/lib/status.ts` is the single place that mapping lives; components never
hardcode a colour.

Touch targets are ≥ 48 px, base font is bumped above the Tailwind default for outdoor
one-handed use, and pinch-zoom is deliberately left enabled.

## Offline behaviour

`public/sw.js` is hand-written rather than generated by `next-pwa`, which has no Next 16
support.

| Asset | Strategy |
|---|---|
| App shell, icons | Cache-first, precached on install |
| Navigations | Network-first, falling back to the cached shell |
| `GET /api/…` reads | Stale-while-revalidate — the last diagnosis stays readable offline |
| `POST` soil-records / images / farms / fields | Queued in IndexedDB, replayed on reconnect |
| `POST /api/analyze` | Never cached, never queued — must run server-side, live |

**The data cache is per-device, not per-account — so it is wiped on every account change.**
Reproduced before fixing: the SW caches `GET /api/...` responses keyed by URL, `/api/farms` is
the same URL for every account, and stale-while-revalidate serves the cached copy *to the page*.
User A's full plot list rendered on user B's home screen after B signed in on the same phone,
and stayed there. `clearDataCaches()` in `api.ts` deletes every `data-*` cache — awaited inside
`login()`/`register()` so B's first navigation cannot race the deletion, and fire-and-forget in
`clearToken()` (sign-out and 401). Verified through the real sign-in flow: after the switch, B
sees only their own empty state.

The IndexedDB write queue is intentionally NOT wiped on sign-out: queued requests are stored
with the token they were made under, so a replay writes to the ORIGINAL account — never the new
one. Wiping it would silently discard a signed-out farmer's unsent readings.

A queued write returns `202` with `{ queued: true }`. On reconnect the worker replays the
queue and notifies the page **only when something was actually sent**.

Items receiving a `4xx` on replay are dropped rather than retried forever — a validation
error will never succeed, and retrying would wedge the queue behind it.

## Voice read-aloud

The spec requires Sarvam AI for reading generated diagnoses aloud. `SpeakButton` tries two
tiers:

1. `POST /api/tts` — backend proxy to Sarvam (**implemented**, `backend/app/routers/tts.py`).
   The proxy exists so the API key stays server-side; calling Sarvam from the browser would
   ship it to every device. Requires `SARVAM_API_KEY`; without it the endpoint returns `503`
   with `reason: "tts_not_configured"` and the client falls through to tier 2. The request
   carries the user's bearer token — TTS is billed per call, so it must not be an open relay.
2. Web Speech API — built into Android Chrome, works offline, needs no key.

**Status: working.** Verified against the live API — a Telugu request returned `200 audio/wav`,
22050 Hz mono 16-bit, 1.53 s, and the browser decoded and played it. Tier 2 was separately
confirmed by exhausting credits: tier 1 → `503`, tier 2 → `en-IN` utterance spoken, button flips
to "Stop". Both paths are proven. See
[../backend/README.md](../backend/README.md#sarvam-text-to-speech--working) for per-screen costs.

Tier 2 means the feature works with or without a key, and degrades rather than disappearing.
Hindi, Kannada and Telugu voice availability varies by device — often absent on low-end
Android, which is exactly the target hardware — so configuring Sarvam is what makes voice
dependable. The button reports when neither tier can speak instead of silently doing nothing.

## Languages

English, Hindi, Kannada and Telugu via **next-i18next**, as the spec requires
("Implement next-i18next for static UI strings in Hindi and Kannada").

| Piece | File |
|---|---|
| Catalogues | `src/app/i18n/locales/<lng>/common.json` — 170 keys x 4 languages |
| Config | `i18n.config.ts` |
| Language detection | `src/proxy.ts` |
| Server init + hydration | `src/app/layout.tsx` (`initServerI18next`, `getT`, `getResources`, `I18nProvider`) |
| Typed access | `src/lib/LocaleProvider.tsx` (`useLocale`), key type in `src/lib/tkey.ts` |
| Parity guard | `scripts/check-locales.mjs`, wired into `build` and `typecheck` |

Three decisions worth knowing:

**`localeInPath: false`.** URLs stay `/capture`, not `/en/capture`. Locale-prefixed routes would
mean moving everything under `app/[lng]/`, which multiplies the service worker's precached shell
paths by four and breaks its `caches.match('/')` offline fallback. Language comes from a cookie
instead.

**A typed wrapper over `useT()`.** i18next resolves keys at runtime and returns the key itself on
a miss, so a typo or a key missing from the Telugu catalogue would render the literal text
`helpNitrogen` to a farmer. `TKey` is derived from the English JSON, making that a build error.
`scripts/check-locales.mjs` covers what types cannot see — a key present in English but missing
from another language, an empty value, or a placeholder mismatch (`{{min}}` vs `{min}`). Both run
in `npm run build`.

**`LocaleSync` for offline.** next-i18next renders the shell server-side from the cookie, but the
service worker caches `/` as HTML frozen in one language and offline there is no server to
re-render it. `LocaleSync` (mounted once in `AppChrome`) re-applies the stored preference on the
client. Verified: after switching to Telugu and going fully offline, a reload still shows
`<html lang="te">` and a Telugu header.

Placeholders use i18next syntax — `{{min}}`, not `{min}`.

## Icons

Generated by `scripts/generate-icons.py` (Pillow) — committed so they are reproducible rather
than opaque binaries. Re-run after a palette or mark change:

```bash
python scripts/generate-icons.py
```

The mark is a sprout over layered soil in the app's theme green (`#2f9e44`).

**Small sizes are a different drawing, not a scaled-down large one.** Below 24px the icon uses
a single soil band and a larger, all-white sprout: three soil strata average into one flat brown
smear at 16px, and the light-green leaf sits too close to the green background to separate. The
previous icons were a flat rectangle with a hairline stem — at 16px the stem vanished entirely
and the tab showed an unidentifiable brown block.

`favicon.ico` is written by hand rather than by Pillow's ICO writer, which downscales one source
image for every frame (reintroducing the 16px mush) and silently dropped `append_images`. All
seven frames — 16/24/32/48/64/128/256 — are drawn at their native size.

`layout.tsx` declares each size explicitly. It previously pointed only at `icon-192.png`, so the
browser downscaled a 192px app icon into a 16px tab.

## Plots, not farms-then-fields

The database models `farm -> field`, and it should: a farmer can work several plots, and soil
history has to attach per plot. But that hierarchy was leaking into the UI as **two forms filled
in order** — five inputs before a farmer could photograph anything:

| Old | New |
|---|---|
| Add farm: name, owner name, village | **Add plot:** plot name, village *(optional)*, area *(optional)* |
| then Add field: field name, area | — |

Two of those inputs earned nothing. **`owner_name` was collected, stored, and read by no code
at all** — not the PDF, not any advisory; the account already knows the farmer's name, so it was
asking them to type it twice. And a separate *farm name* is a real grouping for someone with
plots in several villages, but noise for the smallholder this targets.

The farm row is still created — the schema and every ownership check depend on it — but the
farmer never sees the concept. **The village decides grouping:** plots in the same village share
a farm row, a different village starts a new one. That is the only meaning "farm" carries from
the farmer's side.

All three fields are **always shown**, with the village prefilled from the existing farm. An
earlier version hid it once a farm existed, on an "ask once, inherit after" theory — which made
the form change shape depending on state the farmer could not see, and left someone with plots in
two villages no way to enter the second. Prefilling keeps the common case a single tap while
staying editable. Village comparison is case- and whitespace-insensitive, so `"warangal "` does
not silently fragment a farmer's plots away from `"Warangal"`.

Verified: same village → 1 farm, 2 plots; different village → 2 farms, correctly labelled.

**One bug this surfaced.** The service worker's `staleWhileRevalidate` served the *previous*
(empty) `/farms/{id}/fields` response straight after a write, so a newly created plot did not
appear — the POST returned 201 and the screen still said "No plots yet". Writes now invalidate
the data cache (`sw.js` v5).

## The trend screen is offered only when it works

A projection needs **3+ soil records** for the field (backend `trends.MIN_RECORDS`) — two points
always fit a line exactly, so fewer carries no information and the API returns
`sufficient: false`.

The results screen used to render the "Long-term trend" link **unconditionally**, so a farmer
with one reading tapped it, waited for a page load, and hit a dead end telling them to come back
later. The link is now gated on the record count, and when it is not available the same space
states the requirement instead:

> 📈 **Long-term trend** — Add more soil tests to see a trend. 1 of 3 recorded.

Non-tappable, so nothing invites a wasted tap. `recordCount === null` (count not yet known)
renders the link optimistically rather than hiding a feature on missing data.

`TREND_MIN_RECORDS` in `results/[analysisId]/page.tsx` mirrors the backend constant; the trend
page still guards itself, so the two are belt and braces rather than a single point of failure.

To see the populated screen, seed history with
[`backend/scripts/seed_demo_history.py`](../backend/README.md#seeing-the-trend-screen-demo-data).

## Progressive loading on the results screen

The results screen previously held a full-page spinner until every call settled — and the
slowest, crop suitability, can take seconds on a cold server because the backend re-runs the
soil-type CNN for it. The farmer's diagnosis sat ready in memory while they watched a spinner.

Now the score, risk and nutrient sections render the moment `getStoredAnalysis` returns
(measured: ~0.4 s), and the advisory area holds an `aria-busy` skeleton until the fertilizer
and crop calls settle. On failure of an advisory call, its section simply doesn't render —
the diagnosis is never hostage to the advisory.

Server-side, `/crop-suitability` caches the photo-derived soil type per image id
(`_soil_type_cache` in `advisory.py`) — an uploaded image is immutable, so its classification
never changes, yet it was being re-classified on every call. Only the verdict string is
cached, never `cnn.classify()`'s result dict, because callers elsewhere mutate that dict and
a shared cached copy would be poisoned.

One trap found on the way: `Card` does not forward extra props, so `aria-busy` placed on
`<Card>` was silently dropped. It sits on an inner `div`.

## Design system

One place per decision, so screens cannot drift apart:

| Concern | Source of truth |
|---|---|
| Status -> colour + icon + label | `src/lib/status.ts` (incl. `BAND_HEX` for SVG strokes) |
| Palette | `tailwind.config.ts` |
| Panels | `Card` (outer), `Subpanel` (nested — smaller radius/padding) |
| Headings | `PageTitle` (one `<h1>` per route), `SectionTitle` (`<h2>`) |
| Actions | `BigButton`, `BackLink` |
| Field messages | `FieldNote`, `HelpNote`, `ErrorNote` |

**Fill colours and text colours are separate tokens.** A Lighthouse audit put `text-ok` at
3.21:1 and `text-low` at 4.08:1 — both below WCAG AA's 4.5:1. Darkening `ok` itself would have
dulled every chip, dial and bar, so `ok-text` / `low-text` / `caution-text` are the same hues
darkened until they pass (5.04 / 6.04 / 5.36 on `surface`). Use `bg-*` for fills, `text-*-text`
for coloured text. Contrast now scores 100.

**Touch targets are opt-out, not opt-in.** `globals.css` sets `min-height: 3rem` on
`button:not([data-compact])`. Previously the rule was unconditional, so anything needing to be
smaller fought it with `style={{ minHeight: 'auto' }}` — and that pattern leaked onto real
buttons, leaving the show/hide-password control and the banner dismiss ✕ well under 48px.
`data-compact` gives an explicit, greppable 44px, and a plain `<button>` can no longer lose its
touch target by accident. Measured: **zero interactive controls under 44px on any route.**

**Every status carries a non-colour signal.** The crop-suitability ranking used to convey its
band by bar colour alone; it now shows an icon and the band in words, like the rest of the app.

## Responsive layout

Mobile-first, with two breakpoints so a 10-inch tablet is not a 28 rem strip of content:

| Breakpoint | Change |
|---|---|
| `sm:` (≥ 640 px) | Shell widens to `max-w-xl`; field picker, capture chooser, NPK form and crop list go two-column; page padding increases |
| `lg:` (≥ 1024 px) | Shell widens to `max-w-3xl` |

Measured: at a 412 px viewport the field buttons are one per row and the NPK form is 6 rows;
at 834 px the buttons pair up and the form is 3 rows.

## Camera constraints

| Constraint | Handling |
|---|---|
| `getUserMedia` needs a secure context | Checked up front; falls back with an explanation rather than showing a dead preview |
| Android Chrome 60+ | Falls back to `<input capture="environment">`, which opens the native camera |
| Low-end devices | Canvas grab downscaled to 1024 px before upload — a 12 MP frame would time out on rural 4G |
| Dark or blurred photos | Checked on-device before upload; the farmer is warned and offered a retake |
| Releasing the camera | Stream stopped on unmount, on `pagehide`, and when the tab is backgrounded |

### Releasing the camera

The camera indicator staying on after leaving the capture screen was a real leak with three
causes, all fixed in `capture/camera/page.tsx`:

1. **The effect re-ran on every language change.** `startCamera` closes over `t`, so listing it
   as a dependency re-fired the effect; its cleanup stopped the *old* stream while a second
   `getUserMedia` had already overwritten `streamRef`, orphaning the first with no reference
   left to stop it. The effect is now mount-only, and `startCamera` stops any existing stream
   before requesting a new one.
2. **`getUserMedia` could resolve after unmount**, storing a live stream nothing would release.
   An `unmountedRef` check stops such a stream immediately.
3. **Unmount cleanup does not run when a tab is discarded** (bfcache eviction, Android killing a
   backgrounded tab). `pagehide` and `visibilitychange` listeners release the camera in those
   cases; returning to the tab restarts the preview, and only the preview — the photo on the
   confirm step is never discarded.

Verified by wrapping `getUserMedia` and counting tracks whose `readyState` is still `live`:
switching language three times leaves **1** live track (not 4), leaving the screen leaves
**0**, backgrounding leaves **0**, and returning restores **1**.

### Photo quality check

The CNN returns a confident-looking soil type for a photo a human could not classify, so a
dark or motion-blurred frame produces a plausible but meaningless result. `assessQuality()`
in `capture/camera/page.tsx` screens the captured frame before it is uploaded:

| Signal | Method | Threshold |
|---|---|---|
| Too dark | Mean Rec. 601 luma | `< 40` |
| Blurred | Variance of a 4-neighbour Laplacian, subsampled every 2nd pixel | `< 60` |

Both run on the already-downscaled canvas, so the cost is a few milliseconds. Measured on
the repo's own soil images: **10/10 real photos pass; 12/12 synthetically blurred or darkened
variants are caught.** The margin is wide — the softest real photo scores 349 against a
threshold of 60, and blurred ones land at 0.7–2.9.

The warning is **advisory, not blocking**: it is a heuristic, and a farmer photographing
genuinely dark clay must still be able to proceed, so the confirm button becomes "Use anyway".
Photos chosen from the gallery are not checked — they never touch the canvas, and a wrong
warning is worse than none.

## Sign-up form

Client-side rules now mirror the server exactly (`backend/app/auth.py`), because the previous
version enabled the button on any non-empty value: a mistyped number produced a round trip that
came back as a raw `422` the farmer only saw *after* submitting — slow and confusing on a rural
connection. The server still validates; this is a fast path, not a replacement.

| Field | Rule | Behaviour |
|---|---|---|
| Mobile | `^(?:\+?91)?[6-9]\d{9}$`, spaces/dashes stripped | blocks + inline error |
| Email | `^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$` | blocks + inline error |
| Password | 8 chars min, 72 **bytes** max (bcrypt truncates beyond it) | blocks + inline error |
| Name | 200 chars max, `maxLength` on the input | blocks + inline error |
| Identifier | at least one of mobile/email | blocks with an explanation |

Errors appear on **blur**, not while typing — flagging a half-typed number is noise. Limits live
in named constants at the top of the file so they cannot drift from the server through a bare
literal.

Two additions beyond validation:

* **Report/voice language selector.** `preferred_language` was previously taken silently from the
  UI locale, so a farmer browsing in English could never receive a Telugu PDF or read-aloud. It is
  now an explicit field, stored on the account, so it follows them to another device.
* **Password reveal toggle.** Typing blind on a phone keyboard is the most common cause of a failed
  sign-in. A length-based strength hint is shown and labelled as such — it is not a dictionary check.

## Input validation

The manual entry form carries two range pairs per parameter, which do different jobs:

- **`min`/`max`** — the backend's hard limits. Outside these it returns 422, so submission is
  blocked client-side and the farmer gets a readable inline message instead of an opaque
  server error. pH 99 cannot be submitted.
- **`lo`/`hi`** — the range ordinary Indian readings fall in. Outside these the value is
  *allowed but flagged*, because it is far more often a misplaced decimal point than a real
  measurement. pH 9.2 warns and still submits.

Blocking errors set `aria-invalid` and disable the Analyse button; advisory warnings do
neither. Every parameter also shows its typical range unprompted and a `<details>` disclosure
explaining what the nutrient does — a `<details>`, not a hover tooltip, because hover does not
exist on a phone.

## Known gaps

| Gap | Note |
|---|---|
| **No password reset** | A farmer who forgets their password cannot recover the account — needs an OTP flow. |
| `POST /tts` not implemented | Voice falls back to on-device synthesis. |
| No pagination | `GET /farms` returns all farms; the picker loads everything. |
| Lighthouse measured on the **production** build | Performance **92** (3-run median), Accessibility **100**, Best practices **100** on mobile / simulated slow-4G. Spec target is ≥ 75. Auditing `next dev` instead scores ~68 — the dev bundle ships a 245 kB devtools chunk and is unminified, so always measure `next build && next start`. |
| **Backend prose is not translated** | Crop names, `limiting_factor`, `interpretation`, `caveat` and fertilizer product names come from the API in English and render as-is in every locale. These are exactly the strings `SpeakButton` reads aloud, so a farmer on Telugu hears English product names. Fixing it means translating on the backend (it owns the agronomy vocabulary), not in the dictionaries. |
| Icons are generated, not designed | Drawn programmatically by `scripts/generate-icons.py`; a designer's mark would be better, but these are correctly sized and legible at every size. |
