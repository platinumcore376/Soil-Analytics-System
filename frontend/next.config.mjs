/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // The PWA talks to the FastAPI backend. In dev we proxy through Next so the browser
  // sees one origin — this sidesteps CORS entirely and, more importantly, means
  // getUserMedia's secure-context requirement is satisfied by localhost alone.
  async rewrites() {
    const api = process.env.BACKEND_URL ?? 'http://127.0.0.1:8000';
    return [{ source: '/api/:path*', destination: `${api}/:path*` }];
  },

  // Service worker and manifest must never be cached stale, or an install-time update
  // can strand a device on an old shell.
  async headers() {
    return [
      {
        source: '/sw.js',
        headers: [
          { key: 'Cache-Control', value: 'no-cache, no-store, must-revalidate' },
          { key: 'Service-Worker-Allowed', value: '/' },
        ],
      },
      {
        source: '/manifest.webmanifest',
        headers: [{ key: 'Cache-Control', value: 'no-cache' }],
      },
    ];
  },
};

export default nextConfig;
