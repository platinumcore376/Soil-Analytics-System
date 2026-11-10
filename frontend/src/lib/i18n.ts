/* Locale constants and error-code mapping.
 *
 * The translation STRINGS no longer live here — they are next-i18next JSON catalogues at
 * `src/app/i18n/locales/<lng>/common.json`, per the spec's "Implement next-i18next for
 * static UI strings in Hindi and Kannada". `i18n.config.ts` loads them; `LocaleProvider.tsx`
 * exposes a typed `t()` over them.
 *
 * What remains here is everything that is not a translated string: the supported-language
 * list, the labels shown in the switcher (deliberately each in its own script, never
 * translated), the BCP-47 tags for speech synthesis, and the API-error-to-key mapping.
 */

export const LOCALES = ['en', 'hi', 'kn', 'te'] as const;
export type Locale = (typeof LOCALES)[number];

/* Endonyms — each language names itself. A farmer looking for Kannada scans for ಕನ್ನಡ, not
 * for the word "Kannada" rendered in whatever language the UI currently happens to be in. */
export const LOCALE_LABELS: Record<Locale, string> = {
  en: 'English',
  hi: 'हिंदी',
  kn: 'ಕನ್ನಡ',
  te: 'తెలుగు',
};

/* BCP-47 tags for the Web Speech API and the Sarvam proxy. Indian variants throughout:
 * `en-IN` reads digits and place names the way the listener expects. */
export const SPEECH_LANG: Record<Locale, string> = {
  en: 'en-IN',
  hi: 'hi-IN',
  kn: 'kn-IN',
  te: 'te-IN',
};

/* Errors raised inside api.ts carry a stable `code` (that module has no locale, so it cannot
 * translate itself). This maps the code to a catalogue key; `tError` in LocaleProvider does
 * the lookup. A backend-supplied message is shown verbatim instead, since it is already
 * specific — "pH 99 is outside the typical soil range" beats a generic apology.
 */
const ERROR_KEYS: Record<string, string> = {
  offline: 'noConnection',
  'session-expired': 'sessionExpired',
  'image-failed': 'imageFailed',
  'report-failed': 'reportFailed',
};

/** Catalogue key for a caught error, or null when the error's own message should be shown. */
export function errorKeyFor(err: unknown): string | null {
  const code =
    typeof err === 'object' && err !== null && 'code' in err
      ? (err as { code?: string }).code
      : undefined;
  return code && ERROR_KEYS[code] ? ERROR_KEYS[code] : null;
}
