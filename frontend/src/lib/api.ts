/* Typed client for the FastAPI backend.
 *
 * Bypasses the Next.js proxy by pointing directly to the FastAPI server 
 * to prevent ECONNRESET socket hang-ups during heavy multipart image uploads.
 */

import type {
  Analysis,
  CropSuitability,
  Farm,
  Field,
  ImageMeta,
  Recommendations,
  SoilRecord,
  Trend,
} from './types';

// Connects to the backend via Next.js proxy rewrite (/api/*) by default,
// ensuring same-origin service worker caching, background sync, and CORS safety.
const BASE = process.env.NEXT_PUBLIC_API_URL || '/api';

/* ------------------------------------------------------------------ auth token --- */
/* Stored in localStorage rather than a cookie: the service worker replays queued writes
 * from its own context, where a cookie would not be attached automatically, and this keeps
 * the token available to that replay. The trade-off is XSS exposure — acceptable here
 * because the app renders no user-supplied HTML. */

const TOKEN_KEY = 'soil-health-token';

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

/* Delete the service worker's API-response caches.
 *
 * THE LEAK THIS PLUGS — reproduced before fixing
 * The SW caches GET /api/... responses (stale-while-revalidate) keyed by URL, and
 * `/api/farms` is the SAME URL for every account. Nothing cleared that cache on an account
 * change, and stale-while-revalidate serves the cached copy TO THE PAGE — the fresh fetch
 * only updates the cache for next time. Measured result: user A's full plot list rendered on
 * user B's home screen after B signed in on the same device, and stayed there.
 *
 * Called awaited from login/register (so B's first navigation cannot race the deletion) and
 * fire-and-forget from clearToken. Cache names are matched by prefix because the page does
 * not know the SW's VERSION suffix.
 */
export async function clearDataCaches(): Promise<void> {
  try {
    if (typeof caches === 'undefined') return; // no Cache Storage (SSR, old browser)
    const keys = await caches.keys();
    await Promise.all(
      keys.filter((k) => k.startsWith('data-')).map((k) => caches.delete(k)),
    );
  } catch {
    /* Cache API can throw in private browsing; the SW then has nothing cached either. */
  }
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  // The selected field belongs to the previous account; leaving it would show another
  // user's field name after a switch.
  window.localStorage.removeItem('soil-health-field');
  // As does every cached API response — see clearDataCaches. Fire-and-forget here (this
  // runs in sync 401 paths); the next login awaits a second clear regardless.
  void clearDataCaches();
}

/* Stable identifiers for the errors this layer generates itself (as opposed to a message
 * relayed from the backend). This module cannot call `t()` — it is not a React component and
 * has no locale — so it tags the error and lets the UI translate it. `message` stays as an
 * English fallback for logs and for any caller that renders it directly.
 */
export type ApiErrorCode = 'offline' | 'session-expired' | 'image-failed' | 'report-failed';

/** Error carrying the HTTP status so callers can distinguish 409 from 503. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    /** Set only for errors raised here; absent when `message` came from the backend. */
    readonly code?: ApiErrorCode,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/** Maps an ApiError to a translation key, or null when the backend's own text should show. */
export function apiErrorKey(err: unknown): ApiErrorCode | null {
  return err instanceof ApiError && err.code ? err.code : null;
}

/** FastAPI returns `detail` as a string for app errors and an array for 422 validation. */
function extractDetail(body: unknown, status: number): string {
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          const loc = Array.isArray(d?.loc) ? d.loc.slice(1).join('.') : '';
          return loc ? `${loc}: ${d?.msg ?? 'invalid'}` : (d?.msg ?? 'invalid');
        })
        .join('; ');
    }
  }
  return `Request failed (${status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers = new Headers(init?.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, 'No connection. Check your network and try again.', 'offline');
  }

  // A stale or expired token must not leave the app in a half-signed-in state.
  if (response.status === 401) {
    clearToken();
    throw new ApiError(401, 'Your session has expired. Please sign in again.', 'session-expired');
  }

  // 202 is the service worker acknowledging a queued offline write.
  if (response.status === 202) {
    return (await response.json()) as T;
  }

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, extractDetail(body, response.status));
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function json(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  };
}

/* ------------------------------------------------------------------------- auth */

export interface AuthUser {
  id: number;
  /** Either identifier may be null — an account needs only one of the two. */
  phone: string | null;
  email: string | null;
  name: string;
  preferred_language: string;
  created_at: string;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

export async function register(data: {
  /** Supply a phone number, an email address, or both. */
  phone?: string;
  email?: string;
  name: string;
  password: string;
  preferred_language?: string;
}): Promise<AuthUser> {
  const result = await request<TokenResponse>('/auth/register', json('POST', data));
  setToken(result.access_token);
  // Awaited: the previous account's cached API responses must be gone BEFORE the caller
  // navigates and the home screen fetches /api/farms, or the old data races back in.
  await clearDataCaches();
  return result.user;
}

/** `identifier` is a phone number or an email address — the backend tells them apart. */
export async function login(identifier: string, password: string): Promise<AuthUser> {
  const result = await request<TokenResponse>(
    '/auth/login',
    json('POST', { identifier, password }),
  );
  setToken(result.access_token);
  // Awaited for the same reason as in register().
  await clearDataCaches();
  return result.user;
}

export const me = () => request<AuthUser>('/auth/me');

export function logout(): void {
  clearToken();
}

/* ------------------------------------------------------------------ farms & fields */

export const listFarms = () => request<Farm[]>('/farms');

export const createFarm = (data: {
  name: string;
  owner_name?: string;
  location?: string;
}) => request<Farm>('/farms', json('POST', data));

export const listFields = (farmId: number) =>
  request<Field[]>(`/farms/${farmId}/fields`);

export const createField = (data: {
  farm_id: number;
  name: string;
  area_hectares?: number;
}) => request<Field>('/fields', json('POST', data));

/* -------------------------------------------------------------------- soil records */

export const createSoilRecord = (data: {
  field_id: number;
  nitrogen?: number;
  phosphorus?: number;
  potassium?: number;
  ph?: number;
  organic_matter?: number;
  moisture?: number;
}) => request<SoilRecord>('/soil-records', json('POST', data));

export const updateSoilRecord = (
  recordId: number,
  data: Partial<Record<string, number>>,
) => request<SoilRecord>(`/soil-records/${recordId}`, json('PATCH', data));

export const listSoilRecords = (fieldId: number) =>
  request<SoilRecord[]>(`/soil-records/by-field/${fieldId}`);

/* -------------------------------------------------------------------------- images */

export async function uploadImage(
  file: Blob,
  opts: { field_id?: number; source?: 'upload' | 'camera'; filename?: string } = {},
): Promise<ImageMeta> {
  const form = new FormData();
  form.append('file', file, opts.filename ?? 'capture.jpg');
  if (opts.field_id !== undefined) form.append('field_id', String(opts.field_id));
  form.append('source', opts.source ?? 'camera');
  // Content-Type is deliberately unset: the browser must add the multipart boundary.
  return request<ImageMeta>('/images', { method: 'POST', body: form });
}

/** Fetch an image binary as an object URL.
 *
 * The endpoint now requires a bearer token, so a bare `<img src>` would 401 — the browser
 * does not attach Authorization headers to image requests. Callers must revoke the
 * returned URL when the element unmounts.
 */
export async function fetchImageObjectUrl(
  imageId: number,
  variant: 'original' | 'processed' = 'original',
): Promise<string> {
  const token = getToken();
  const response = await fetch(`${BASE}/images/${imageId}/file?variant=${variant}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!response.ok) throw new ApiError(response.status, 'Could not load the image.', 'image-failed');
  return URL.createObjectURL(await response.blob());
}

/* ------------------------------------------------------------------------ analysis */

export const analyze = (data: {
  field_id: number;
  soil_record_id?: number;
  image_id?: number;
  nitrogen?: number;
  phosphorus?: number;
  potassium?: number;
  ph?: number;
  organic_matter?: number;
  moisture?: number;
  explain?: boolean;
  fuse?: boolean;
}) => request<Analysis>('/analyze', json('POST', data));

export const classifySoil = (imageId: number) =>
  request<Record<string, unknown>>(`/classify-soil/${imageId}`, { method: 'POST' });

export const explainImage = (imageId: number) =>
  request<{ overlay_png: string; focus_region: string; explained_class: string }>(
    `/explain-image/${imageId}`,
    { method: 'POST' },
  );

/** One stored analysis row. `diagnosis` is a JSON-encoded string, not an object. */
export interface StoredAnalysis {
  id: number;
  field_id: number;
  soil_record_id: number | null;
  image_id: number | null;
  soil_health_score: number;
  diagnosis: string;
  degradation_risk_index: number | null;
  recommended_crop: string | null;
  created_at: string;
}

export const getStoredAnalysis = (analysisId: number) =>
  request<StoredAnalysis>(`/analysis-results/${analysisId}`);

/* ------------------------------------------------------------------------ advisory */

export const getRecommendations = (analysisId: number) =>
  request<Recommendations>(`/recommendations/${analysisId}`);

export const getCropSuitability = (fieldId: number, topK = 8) =>
  request<CropSuitability>(`/crop-suitability/${fieldId}?top_k=${topK}`);

export const getTrend = (fieldId: number) => request<Trend>(`/trend/${fieldId}`);

/** Download the PDF report.
 *
 * Fetched with the bearer token then handed to a synthetic <a download>, because an
 * ordinary link cannot carry an Authorization header.
 */
export async function downloadReport(
  analysisId: number,
  language = 'en',
  heatmap = false,
): Promise<void> {
  const token = getToken();
  const query = `language=${language}${heatmap ? '&include_heatmap=true' : ''}`;
  const response = await fetch(`${BASE}/reports/${analysisId}?${query}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!response.ok) throw new ApiError(response.status, 'Could not generate the report.', 'report-failed');

  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = `soil-health-report-${analysisId}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** Download the standalone multi-panel trend PDF report using field ID. */
export async function downloadTrendPdf(fieldId: number): Promise<void> {
  const token = getToken();
  const response = await fetch(`${BASE}/trend/${fieldId}/pdf`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!response.ok) throw new ApiError(response.status, 'Could not generate the trend report.', 'report-failed');
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = `soil-health-trend-${fieldId}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}