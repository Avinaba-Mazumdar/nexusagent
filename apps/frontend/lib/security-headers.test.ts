import { describe, expect, it } from 'vite-plus/test';
import { buildSecurityHeaders } from './security-headers';

const hsts = (headers: ReturnType<typeof buildSecurityHeaders>) => headers.find((h) => h.key === 'Strict-Transport-Security')?.value;

describe('buildSecurityHeaders', () => {
    it('sends no HSTS outside production', () => {
        expect(hsts(buildSecurityHeaders({ isProduction: false, hstsPreload: true }))).toBeUndefined();
    });

    it('sends a plain one-year HSTS in production by default', () => {
        expect(hsts(buildSecurityHeaders({ isProduction: true, hstsPreload: false }))).toBe('max-age=31536000');
    });

    it('adds includeSubDomains and preload only when opted in', () => {
        expect(hsts(buildSecurityHeaders({ isProduction: true, hstsPreload: true }))).toBe('max-age=63072000; includeSubDomains; preload');
    });

    it('always sends the framing and sniffing protections', () => {
        const keys = buildSecurityHeaders({ isProduction: false, hstsPreload: false }).map((h) => h.key);
        expect(keys).toEqual(expect.arrayContaining(['X-Frame-Options', 'X-Content-Type-Options', 'Referrer-Policy', 'Permissions-Policy']));
    });
});
