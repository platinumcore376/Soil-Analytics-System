/* next-i18next configuration (Weeks 5-6).
 *
 * Spec requirement (page 2):
 *     "Implement next-i18next for static UI strings in Hindi and Kannada"
 *
 * Telugu was added at the user's request, and English is the fallback.
 *
 * WHY `localeInPath: false`
 * The default mode prefixes every URL with the locale (`/en/capture`, `/hi/capture`), which
 * would mean moving every route under `app/[lng]/`. Two concrete costs here:
 *   1. `public/sw.js` precaches the shell by path and the offline navigation fallback matches
 *      on '/'. Locale-prefixed routes multiply those paths by four and break the fallback.
 *   2. The app stores a selected field and a token per origin, not per locale; a farmer who
 *      switches language mid-flow should stay on the same screen, not be redirected.
 * Cookie-based detection keeps the existing URLs and the existing service worker intact.
 *
 * WHY `resourceLoader`
 * Dynamic `import()` is traceable by the bundler, so the catalogues are compiled into the
 * JS payload rather than read from disk at runtime. That is what keeps language switching
 * working offline — the whole reason this app is a PWA.
 */
import type { I18nConfig } from 'next-i18next/proxy';

const i18nConfig: I18nConfig = {
  supportedLngs: ['en', 'hi', 'kn', 'te'],
  fallbackLng: 'en',
  defaultNS: 'common',
  ns: ['common'],
  localeInPath: false,
  resourceLoader: (language: string, namespace: string) =>
    import(`./src/app/i18n/locales/${language}/${namespace}.json`),
};

export default i18nConfig;
