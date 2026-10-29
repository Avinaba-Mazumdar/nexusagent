import type { NextConfig } from 'next';

// Content-Security-Policy is set per request in proxy.ts (it needs a fresh nonce).
const securityHeaders = [
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
