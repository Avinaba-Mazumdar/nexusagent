import type { NextConfig } from 'next';
import { buildSecurityHeaders } from './lib/security-headers';

if (process.env.NODE_ENV === 'production' && !process.env.NEXT_PUBLIC_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL must be set for production builds (it is compiled into the client bundle).');
}

const securityHeaders = buildSecurityHeaders({
    isProduction: process.env.NODE_ENV === 'production',
    hstsPreload: process.env.HSTS_PRELOAD === 'true'
});

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
