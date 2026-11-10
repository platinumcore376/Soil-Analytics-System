/* next-i18next language detection (Next.js 16 replaces middleware.ts with proxy.ts).
 *
 * In `localeInPath: false` mode this does NOT redirect. It resolves the language from the
 * cookie, then the Accept-Language header, then the fallback, and exposes it to Server
 * Components via the `x-i18next-current-language` header.
 *
 * LOCATION: this file must sit beside `app/`, i.e. `src/proxy.ts` in this project (Next's
 * convention is "project root, or inside src if applicable"). At the repo root it is silently
 * ignored — no header, no cookie, every request falls back to English.
 *
 * `sw.js` and `manifest.webmanifest` are excluded from the matcher: the service worker must
 * be served from the origin root with its own scope, and running it through the proxy would
 * add a Vary header that breaks SW update checks.
 */
import { createProxy } from 'next-i18next/proxy';

import i18nConfig from '../i18n.config';

export const proxy = createProxy(i18nConfig);

export const config = {
  matcher: [
    '/((?!api|_next/static|_next/image|icons|favicon.ico|sw.js|manifest.webmanifest).*)',
  ],
};
