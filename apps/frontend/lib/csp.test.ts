import { describe, expect, it } from 'vite-plus/test';
import { apiOriginFromEnv, buildCsp } from './csp';

const directive = (csp: string, name: string) => csp.split('; ').find((d) => d.startsWith(`${name} `)) ?? '';

describe('buildCsp', () => {
    const prod = buildCsp({ nonce: 'abc123', isDev: false, apiOrigin: 'https://api.example.com' });

    it('allows scripts only through the nonce, never unsafe-inline or unsafe-eval in production', () => {
        const script = directive(prod, 'script-src');
        expect(script).toContain("'nonce-abc123'");
        expect(script).toContain("'strict-dynamic'");
        expect(script).not.toContain("'unsafe-inline'");
        expect(script).not.toContain("'unsafe-eval'");
    });

    it('permits eval only in development', () => {
        expect(directive(buildCsp({ nonce: 'n', isDev: true, apiOrigin: '' }), 'script-src')).toContain("'unsafe-eval'");
    });

    it('limits connections to self, the API origin and Google', () => {
        const connect = directive(prod, 'connect-src');
        expect(connect).toContain('https://api.example.com');
        expect(connect).not.toContain('localhost');
    });

    it('locks down framing, objects and base URI', () => {
        expect(prod).toContain("frame-ancestors 'none'");
        expect(prod).toContain("object-src 'none'");
        expect(prod).toContain("base-uri 'self'");
        expect(prod).toContain('upgrade-insecure-requests');
    });
});

describe('apiOriginFromEnv', () => {
    it('extracts the origin and tolerates bad input', () => {
        expect(apiOriginFromEnv('https://api.example.com/v1')).toBe('https://api.example.com');
        expect(apiOriginFromEnv('not a url')).toBe('');
        expect(apiOriginFromEnv(undefined)).toBe('');
    });
});
