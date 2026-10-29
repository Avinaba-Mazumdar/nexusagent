import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiClient, setAuthTokenGetter, setOnUnauthorizedCallback } from './api-client';

describe('apiClient', () => {
    beforeEach(() => {
        vi.restoreAllMocks();
        // Reset auth token getter and unauthorized callback
        setAuthTokenGetter(() => null);
        setOnUnauthorizedCallback(() => {});
    });

    describe('apiClient', () => {
        it('performs successful GET request and parses JSON', async () => {
            const mockData = { id: 1, name: 'NexusAgent' };
            vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
                new Response(JSON.stringify(mockData), {
                    status: 200,
                    headers: { 'Content-Type': 'application/json' }
                })
            );

            const result = await apiClient<typeof mockData>('/api/test');
            expect(result).toEqual(mockData);
            expect(globalThis.fetch).toHaveBeenCalledWith(
                expect.stringContaining('/api/test'),
                expect.objectContaining({
                    headers: expect.any(Headers)
                })
            );
        });

        it('injects Authorization header when token is present', async () => {
            setAuthTokenGetter(() => 'valid-bearer-token');

            vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200 }));

            await apiClient('/api/secure-endpoint');

            const fetchCalls = vi.mocked(globalThis.fetch).mock.calls;
            const headers = fetchCalls[0][1]?.headers as Headers;
            expect(headers.get('Authorization')).toBe('Bearer valid-bearer-token');
        });

        it('appends query parameters when params option is provided', async () => {
            vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }));

            await apiClient('/api/search', {
                params: { query: 'benchmarks', limit: 5 }
            });

            const fetchCalls = vi.mocked(globalThis.fetch).mock.calls;
            const url = String(fetchCalls[0][0]);
            expect(url).toContain('query=benchmarks');
            expect(url).toContain('limit=5');
        });

        it('triggers unauthorized callback on 401 response and throws', async () => {
            const onUnauthorized = vi.fn();
            setOnUnauthorizedCallback(onUnauthorized);

            vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
                new Response(JSON.stringify({ detail: 'Token has expired' }), {
                    status: 401,
                    statusText: 'Unauthorized'
                })
            );

            await expect(apiClient('/api/protected')).rejects.toThrow('Token has expired');
            expect(onUnauthorized).toHaveBeenCalledTimes(1);
        });

        it('formats FastAPI array validation errors cleanly into string', async () => {
            vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
                new Response(
                    JSON.stringify({
                        detail: [{ msg: 'Password must be at least 8 characters long' }, { msg: 'Invalid email format' }]
                    }),
                    {
                        status: 422,
                        statusText: 'Unprocessable Entity'
                    }
                )
            );

            await expect(apiClient('/api/auth/register')).rejects.toThrow('Password must be at least 8 characters long, Invalid email format');
        });

        it('handles request timeout gracefully', async () => {
            const abortError = new Error('The operation was aborted');
            abortError.name = 'AbortError';

            vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(abortError);

            await expect(apiClient('/api/slow-operation')).rejects.toThrow('Request timed out. Please check your network connection.');
        });

        it('handles non-JSON error response gracefully', async () => {
            vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
                new Response('Internal Server Error', {
                    status: 500,
                    statusText: 'Internal Server Error'
                })
            );

            await expect(apiClient('/api/broken')).rejects.toThrow('API error: Internal Server Error (500)');
        });
    });
});
