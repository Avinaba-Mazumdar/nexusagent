/**
 * NexusAgent Edge Routing Gateway (Cloudflare Worker)
 *
 * Standalone Edge Function for rate-limiting, model routing, and key rotation
 * across Google AI Studio free tier limits.
 *
 * Deploy outside OSS repo to Cloudflare Workers:
 *   npx wrangler deploy
 *
 * Environment Variables (set via Cloudflare dashboard or wrangler.toml):
 *   - GEMINI_API_KEYS: Comma-separated list of free-tier Gemini API keys (key1,key2,...)
 *   - ALLOWED_ORIGINS: Comma-separated list of CORS origins (https://your-portfolio.vercel.app,http://localhost:3000)
 */

interface Env {
    GEMINI_API_KEYS?: string;
    ALLOWED_ORIGINS?: string;
}

// In-memory sliding window rate tracking per Worker isolate
const rateLimitState = {
    windowStart: Date.now(),
    requestCount: 0,
    rpmLimit: 15
};

function checkAndIncrementRpm(): { allow: boolean; count: number } {
    const now = Date.now();
    if (now - rateLimitState.windowStart > 60000) {
        rateLimitState.windowStart = now;
        rateLimitState.requestCount = 0;
    }
    rateLimitState.requestCount++;
    return {
        allow: rateLimitState.requestCount <= rateLimitState.rpmLimit,
        count: rateLimitState.requestCount
    };
}

export default {
    async fetch(request: Request, env: Env): Promise<Response> {
        const origin = request.headers.get('Origin');
        const allowedList = (env.ALLOWED_ORIGINS || 'https://nexusagent.avinaba.com,http://localhost:3000,http://127.0.0.1:3000')
            .split(',')
            .map((o) => o.trim())
            .filter(Boolean);

        const allowOriginHeader =
            origin && (allowedList.includes('*') || allowedList.includes(origin)) ? origin : allowedList[0] || 'https://nexusagent.avinaba.com';

        const corsHeaders = {
            'Access-Control-Allow-Origin': allowOriginHeader,
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-User-API-Key, X-User-Provider',
            'Access-Control-Expose-Headers': 'X-Selected-Model, X-Routing-Stage, X-RateLimit-RPM-Remaining'
        };

        if (request.method === 'OPTIONS') {
            return new Response(null, { status: 204, headers: corsHeaders });
        }

        if (request.method !== 'POST') {
            return new Response(JSON.stringify({ error: 'Method not allowed' }), {
                status: 405,
                headers: { ...corsHeaders, 'Content-Type': 'application/json' }
            });
        }

        try {
            const userApiKey = request.headers.get('X-User-API-Key');
            const userProvider = request.headers.get('X-User-Provider') || 'google';
            const body = (await request.json()) as {
                messages: Array<{ role: string; content: string }>;
                stream?: boolean;
                model?: string;
            };

            // 1. BYOK Path: direct pass-through if client supplied their own key
            if (userApiKey) {
                return await handleByokRequest(body, userApiKey, userProvider, corsHeaders);
            }

            // 2. Demo Tier Path: Edge rate-limiting & model routing cascade
            const keyPool = (env.GEMINI_API_KEYS || '')
                .split(',')
                .map((k) => k.trim())
                .filter(Boolean);
            if (keyPool.length === 0) {
                return new Response(JSON.stringify({ error: 'Gateway unconfigured: No GEMINI_API_KEYS defined.' }), {
                    status: 503,
                    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
                });
            }

            const { allow, count } = checkAndIncrementRpm();
            const remainingRpm = Math.max(0, rateLimitState.rpmLimit - count);

            // Model routing cascade strategy:
            // If within comfortable RPM (<12/15), prefer gemini-2.5-flash
            // If approaching limit (>12), switch to gemini-2.5-flash-lite
            const preferredModel = count > 12 ? 'gemini-2.5-flash-lite' : 'gemini-2.5-flash';
            const fallbackModel = preferredModel === 'gemini-2.5-flash' ? 'gemini-2.5-flash-lite' : 'gemini-1.5-flash';

            // Try primary model with key rotation
            let activeKey = keyPool[count % keyPool.length];
            let res = await callGeminiApi(preferredModel, activeKey, body);

            let selectedModel = preferredModel;
            let routingStage = 'PRIMARY';

            // 3. Fallback on 429 (ResourceExhausted / Rate Limited)
            if (res.status === 429 || !res.ok) {
                // Try fallback model with alternative key
                const altKey = keyPool[(count + 1) % keyPool.length];
                const fallbackRes = await callGeminiApi(fallbackModel, altKey, body);
                if (fallbackRes.ok) {
                    res = fallbackRes;
                    selectedModel = fallbackModel;
                    routingStage = 'FALLBACK_MODEL';
                }
            }

            const responseHeaders = new Headers(res.headers);
            Object.entries(corsHeaders).forEach(([k, v]) => responseHeaders.set(k, v));
            responseHeaders.set('X-Selected-Model', selectedModel);
            responseHeaders.set('X-Routing-Stage', routingStage);
            responseHeaders.set('X-RateLimit-RPM-Remaining', remainingRpm.toString());

            return new Response(res.body, {
                status: res.status,
                headers: responseHeaders
            });
        } catch (err: any) {
            return new Response(JSON.stringify({ error: err.message || 'Internal Gateway Error' }), {
                status: 500,
                headers: { ...corsHeaders, 'Content-Type': 'application/json' }
            });
        }
    }
};

async function callGeminiApi(model: string, apiKey: string, body: any): Promise<Response> {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:streamGenerateContent?alt=sse&key=${apiKey}`;
    const contents = (body.messages || []).map((m: any) => ({
        role: m.role === 'assistant' ? 'model' : 'user',
        parts: [{ text: m.content }]
    }));

    return fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ contents })
    });
}

async function handleByokRequest(body: any, apiKey: string, provider: string, corsHeaders: Record<string, string>): Promise<Response> {
    if (provider === 'openrouter') {
        const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${apiKey}`,
                'HTTP-Referer': 'https://nexusagent.avinaba.com',
                'X-Title': 'NexusAgent Showcase'
            },
            body: JSON.stringify({
                model: body.model || 'google/gemini-2.5-flash',
                messages: body.messages,
                stream: true
            })
        });
        const headers = new Headers(res.headers);
        Object.entries(corsHeaders).forEach(([k, v]) => headers.set(k, v));
        headers.set('X-Selected-Model', body.model || 'google/gemini-2.5-flash');
        headers.set('X-Routing-Stage', 'BYOK_OPENROUTER');
        return new Response(res.body, { status: res.status, headers });
    }

    // Default to Google Gemini BYOK
    const res = await callGeminiApi('gemini-2.5-flash', apiKey, body);
    const headers = new Headers(res.headers);
    Object.entries(corsHeaders).forEach(([k, v]) => headers.set(k, v));
    headers.set('X-Selected-Model', 'gemini-2.5-flash');
    headers.set('X-Routing-Stage', 'BYOK_GOOGLE');
    return new Response(res.body, { status: res.status, headers });
}
