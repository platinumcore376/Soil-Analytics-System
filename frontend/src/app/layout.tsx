import type { Metadata, Viewport } from 'next';
import { I18nProvider } from 'next-i18next/client';
import { getResources, getT, initServerI18next } from 'next-i18next/server';

import { AuthProvider } from '@/lib/AuthProvider';
import { AppChrome } from '@/components/AppChrome';

import i18nConfig from '../../i18n.config';

import './globals.css';

/* Once, at module scope — this registers the catalogues and the resource loader with the
 * server-side i18next instance that `getT()` reads from. */
initServerI18next(i18nConfig);

export const metadata: Metadata = {
  title: 'Soil Health',
  description:
    'Photograph your soil or enter lab readings to get a soil health report, fertilizer advice and crop suggestions.',
  manifest: '/manifest.webmanifest',
  appleWebApp: { capable: true, statusBarStyle: 'default', title: 'Soil Health' },
  /* Size-specific favicons rather than one large icon.
   *
   * Previously this declared only `/icons/icon-192.png`, so the browser downscaled a 192px app
   * icon to fill a 16px tab. The 16/32px files are drawn at their own size with a simplified
   * mark (single soil band, larger sprout) — three soil strata average into one flat brown
   * smear at 16px. `favicon.ico` carries all seven frames for contexts that ask for it
   * (bookmarks bar, Windows pinned sites, older browsers).
   */
  icons: {
    icon: [
      { url: '/favicon.ico', sizes: 'any' },
      { url: '/icons/favicon-16.png', sizes: '16x16', type: 'image/png' },
      { url: '/icons/favicon-32.png', sizes: '32x32', type: 'image/png' },
      { url: '/icons/favicon-48.png', sizes: '48x48', type: 'image/png' },
      { url: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
    ],
    apple: '/icons/apple-touch-icon.png',
  },
};

export const viewport: Viewport = {
  themeColor: '#2f9e44',
  width: 'device-width',
  initialScale: 1,
  // Zoom is deliberately NOT disabled: pinch-zoom is an accessibility necessity, and
  // locking it would fail a Lighthouse accessibility audit.
  maximumScale: 5,
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  /* Language comes from the proxy's header (cookie > Accept-Language > fallback), not from a
   * URL segment — see the `localeInPath: false` note in i18n.config.ts. `getResources`
   * serialises the loaded catalogue so client components hydrate with it rather than
   * re-fetching, which is what keeps the first paint translated and works offline. */
  const { i18n, lng } = await getT();
  const resources = getResources(i18n);

  return (
    <html lang={lng}>
      <body className="min-h-dvh">
        <I18nProvider language={lng} resources={resources}>
          <AuthProvider>
            <AppChrome>{children}</AppChrome>
          </AuthProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
