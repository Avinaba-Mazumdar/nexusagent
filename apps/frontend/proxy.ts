import { NextResponse, type NextRequest } from 'next/server';
import { apiOriginFromEnv, buildCsp } from '@/lib/csp';

/** Issues a fresh CSP nonce per request; Next.js applies it to its own scripts automatically. */
export function proxy(request: NextRequest) {
    const nonce = Buffer.from(crypto.randomUUID()).toString('base64');
    const csp = buildCsp({
        nonce,
        isDev: process.env.NODE_ENV === 'development',
        apiOrigin: apiOriginFromEnv(process.env.NEXT_PUBLIC_API_URL)
    });

    const requestHeaders = new Headers(request.headers);
    requestHeaders.set('x-nonce', nonce);
    requestHeaders.set('Content-Security-Policy', csp);

    const response = NextResponse.next({ request: { headers: requestHeaders } });
    response.headers.set('Content-Security-Policy', csp);
    return response;
}

export const config = {
    matcher: [
        {
            source: '/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:png|svg|ico|webmanifest|js)$).*)',
            missing: [
                { type: 'header', key: 'next-router-prefetch' },
                { type: 'header', key: 'purpose', value: 'prefetch' }
            ]
        }
    ]
};
