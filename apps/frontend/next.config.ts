import type { NextConfig } from 'next';

const apiOrigin = process.env.NEXT_PUBLIC_API_URL
    ? (() => {
          try {
              return new URL(process.env.NEXT_PUBLIC_API_URL).origin;
          } catch {
              return '';
          }
      })()
    : '';

const cspHeader = `
    default-src 'self';
    script-src 'self' 'unsafe-inline' 'unsafe-eval' https://accounts.google.com https://apis.google.com;
    style-src 'self' 'unsafe-inline' https://accounts.google.com;
    img-src 'self' data: blob: https://lh3.googleusercontent.com https://accounts.google.com;
    font-src 'self' data:;
    object-src 'none';
    base-uri 'self';
    form-action 'self';
    frame-ancestors 'none';
    frame-src 'self' https://accounts.google.com;
    connect-src 'self' ${apiOrigin} https://nexusagent-oss.onrender.com https://*.onrender.com https://nexusagent.avinaba.com https://*.avinaba.com https://accounts.google.com https://generativelanguage.googleapis.com https://openrouter.ai http://localhost:* http://127.0.0.1:* ws: wss:;
    upgrade-insecure-requests;
`
    .replace(/\s{2,}/g, ' ')
    .trim();

const securityHeaders = [
    {
        key: 'Content-Security-Policy',
        value: cspHeader
    },
    {
        key: 'X-Frame-Options',
        value: 'DENY'
    },
    {
        key: 'X-Content-Type-Options',
        value: 'nosniff'
    },
    {
        key: 'Referrer-Policy',
        value: 'strict-origin-when-cross-origin'
    },
    {
        key: 'Strict-Transport-Security',
        value: 'max-age=63072000; includeSubDomains; preload'
    },
    {
        key: 'Permissions-Policy',
        value: 'camera=(), microphone=(), geolocation=()'
    }
];

const nextConfig: NextConfig = {
    reactCompiler: true,
    async headers() {
        return [
            {
                source: '/(.*)',
                headers: securityHeaders
            }
        ];
    }
};

export default nextConfig;
