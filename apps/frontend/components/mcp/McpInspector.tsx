'use client';

import * as React from 'react';
import { Terminal, Play, CheckCircle2, AlertCircle, Loader2, Search, Copy, Check, LogIn } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { API_BASE, apiClient } from '@/lib/api-client';
import { useAuthStore } from '@/lib/auth-store';
import { MCP_DEFAULT_QUERY } from '@/lib/starter-prompts';

const MCP_TOOL = {
    name: 'hybrid_rag_search',
    label: 'RAG Search',
    description: 'Reciprocal Rank Fusion over benchmarks',
    defaultArgs: { query: MCP_DEFAULT_QUERY, limit: 3 }
};

const SSE_ENDPOINT = `${API_BASE.replace(/\/$/, '')}/api/mcp/sse`;

interface McpInspectorProps {
    onOpenSignIn?: () => void;
}

export function McpInspector({ onOpenSignIn }: McpInspectorProps) {
    const token = useAuthStore((s) => s.token);
    const [argsJson, setArgsJson] = React.useState<string>(JSON.stringify(MCP_TOOL.defaultArgs, null, 2));
    const [isLoading, setIsLoading] = React.useState(false);
    const [lastRequest, setLastRequest] = React.useState<Record<string, unknown> | null>(null);
    const [lastResponse, setLastResponse] = React.useState<Record<string, unknown> | null>(null);
    const [latencyMs, setLatencyMs] = React.useState<number | null>(null);
    const [errorMsg, setErrorMsg] = React.useState<string | null>(null);
    const [modalOpen, setModalOpen] = React.useState(false);
    const [copied, setCopied] = React.useState<'endpoint' | 'token' | null>(null);

    const copyToClipboard = async (value: string, what: 'endpoint' | 'token') => {
        try {
            await navigator.clipboard.writeText(value);
            setCopied(what);
            setTimeout(() => setCopied(null), 2000);
        } catch {
            // Clipboard access blocked
        }
    };

    const handleExecuteTool = async () => {
        setIsLoading(true);
        setErrorMsg(null);
        let parsedArgs: Record<string, unknown>;

        try {
            parsedArgs = JSON.parse(argsJson);
        } catch (err: unknown) {
            setErrorMsg(`Invalid JSON arguments: ${err instanceof Error ? err.message : String(err)}`);
            setIsLoading(false);
            return;
        }

        const rpcPayload = {
            jsonrpc: '2.0',
            id: `client-${Date.now()}`,
            method: 'tools/call',
            params: { name: MCP_TOOL.name, arguments: parsedArgs }
        };

        setLastRequest(rpcPayload);
        const startTime = performance.now();

        try {
            const json = await apiClient<Record<string, unknown> & { error?: { message?: string } }>('/api/mcp/v1', {
                method: 'POST',
                body: JSON.stringify(rpcPayload)
            });
            setLatencyMs(Math.round(performance.now() - startTime));
            setLastResponse(json);
            if (json.error) setErrorMsg(json.error.message || 'Request failed');
        } catch (err: unknown) {
            setLatencyMs(Math.round(performance.now() - startTime));
            const msg = err instanceof Error ? err.message : 'Network execution failed';
            setErrorMsg(msg);
            setLastResponse({ error: { code: -32000, message: msg } });
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <Card className="shadow-2xs border-border" data-testid="mcp-inspector">
            <CardHeader className="p-3 pb-2">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-heading flex items-center gap-1.5">
                        <Terminal className="h-3.5 w-3.5 text-primary" />
                        <span>MCP Tool Inspector</span>
                    </CardTitle>
                    <Badge variant="soft" className="text-xs font-mono">
                        2024-11-05
                    </Badge>
                </div>
                <CardDescription className="text-xs text-muted-foreground">Call a tool over the JSON-RPC 2.0 HTTP gateway</CardDescription>
            </CardHeader>
            <CardContent className="p-3 pt-0 space-y-2.5">
                {/* Tool Label */}
                <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-secondary/50 border border-border/60 text-xs font-medium text-foreground">
                    <Search className="h-3 w-3 text-primary shrink-0" aria-hidden="true" />
                    <span className="font-semibold">{MCP_TOOL.label}</span>
                    <span className="text-muted-foreground text-xs truncate">— {MCP_TOOL.description}</span>
                </div>

                {/* Input Arguments Field */}
                <div className="space-y-1">
                    <label htmlFor="mcp-args" className="font-mono text-xs text-muted-foreground">
                        arguments (JSON)
                    </label>
                    <textarea
                        id="mcp-args"
                        aria-label="MCP Tool Arguments JSON"
                        value={argsJson}
                        onChange={(e) => setArgsJson(e.target.value)}
                        rows={3}
                        className="w-full h-30 font-mono text-xs bg-background border border-border rounded-lg p-2 leading-tight focus:outline-hidden focus:ring-1 focus:ring-primary text-foreground resize-none"
                    />
                </div>

                {/* Action Trigger */}
                {token ? (
                    <div className="flex items-center gap-2">
                        <Button
                            size="sm"
                            disabled={isLoading}
                            onClick={handleExecuteTool}
                            className="flex-1 h-8 text-xs font-semibold rounded-lg gap-1.5 shadow-2xs"
                        >
                            {isLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3 fill-current" />}
                            <span>{isLoading ? 'Executing...' : 'Invoke Tool'}</span>
                        </Button>

                        <Dialog open={modalOpen} onOpenChange={setModalOpen}>
                            <DialogTrigger asChild>
                                <Button size="sm" variant="outline" className="h-8 text-xs rounded-lg px-2 text-muted-foreground">
                                    Raw messages
                                </Button>
                            </DialogTrigger>
                            <DialogContent className="max-w-xl max-h-4/5 flex flex-col p-4">
                                <DialogHeader>
                                    <DialogTitle className="text-sm font-heading flex items-center gap-1.5">
                                        <Terminal className="h-4 w-4 text-primary" />
                                        JSON-RPC messages
                                    </DialogTitle>
                                    <DialogDescription className="text-xs">
                                        Frames sent to <code>/api/mcp/v1</code> and the server&apos;s reply.
                                    </DialogDescription>
                                </DialogHeader>

                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 flex-1 overflow-hidden pt-2 text-xs">
                                    <div className="flex flex-col overflow-hidden">
                                        <div className="font-mono text-xs font-semibold text-muted-foreground pb-1">Request</div>
                                        <pre className="flex-1 overflow-auto bg-background p-2.5 rounded-lg border border-border font-mono text-xs text-foreground">
                                            {lastRequest ? JSON.stringify(lastRequest, null, 2) : '// No request executed yet'}
                                        </pre>
                                    </div>
                                    <div className="flex flex-col overflow-hidden">
                                        <div className="flex items-center justify-between pb-1">
                                            <span className="font-mono text-xs font-semibold text-muted-foreground">Response</span>
                                            {latencyMs !== null && (
                                                <Badge variant="outline" className="text-xs font-mono">
                                                    {latencyMs}ms
                                                </Badge>
                                            )}
                                        </div>
                                        <pre className="flex-1 overflow-auto bg-background p-2.5 rounded-lg border border-border font-mono text-xs text-foreground">
                                            {lastResponse ? JSON.stringify(lastResponse, null, 2) : '// Awaiting response'}
                                        </pre>
                                    </div>
                                </div>
                            </DialogContent>
                        </Dialog>
                    </div>
                ) : (
                    <Button size="sm" onClick={onOpenSignIn} className="w-full h-8 text-xs font-semibold rounded-lg gap-1.5">
                        <LogIn className="h-3 w-3" aria-hidden="true" />
                        <span>Sign in to try MCP tools</span>
                    </Button>
                )}

                {/* Inline Status & Results Box */}
                {(lastResponse || errorMsg) && (
                    <div
                        className={`p-2 rounded-lg border text-xs space-y-1 ${errorMsg ? 'bg-destructive/10 border-destructive/30' : 'bg-success-bg border-success-border'}`}
                    >
                        <div className="flex items-center justify-between text-xs font-medium">
                            <span className="flex items-center gap-1">
                                {errorMsg ? (
                                    <>
                                        <AlertCircle className="h-3 w-3 text-destructive" />
                                        <span className="text-destructive font-semibold">Error</span>
                                    </>
                                ) : (
                                    <>
                                        <CheckCircle2 className="h-3 w-3 text-success" />
                                        <span className="text-success font-semibold">Success</span>
                                    </>
                                )}
                            </span>
                            {latencyMs !== null && <span className="font-mono text-muted-foreground text-xs">{latencyMs}ms</span>}
                        </div>
                        <div className="font-mono text-xs max-h-20 overflow-y-auto whitespace-pre-wrap text-foreground/90">
                            {errorMsg ||
                                (lastResponse?.result && typeof lastResponse.result === 'object' && 'content' in lastResponse.result
                                    ? String(
                                          (lastResponse.result as { content?: Array<{ text: string }> }).content?.[0]?.text ??
                                              JSON.stringify(lastResponse.result)
                                      )
                                    : JSON.stringify(lastResponse?.result ?? lastResponse ?? {}, null, 2))}
                        </div>
                    </div>
                )}

                {/* Connecting an external MCP client */}
                <div className="pt-1.5 border-t border-border/60 space-y-1 text-xs text-muted-foreground">
                    <div className="flex items-center justify-between gap-2">
                        <span>SSE endpoint for external MCP clients:</span>
                        <button
                            type="button"
                            onClick={() => copyToClipboard(SSE_ENDPOINT, 'endpoint')}
                            aria-label="Copy MCP SSE endpoint URL"
                            className="inline-flex items-center gap-1 text-primary hover:underline cursor-pointer"
                        >
                            {copied === 'endpoint' ? <Check className="h-3 w-3" aria-hidden="true" /> : <Copy className="h-3 w-3" aria-hidden="true" />}
                            <span>{copied === 'endpoint' ? 'Copied' : 'Copy'}</span>
                        </button>
                    </div>
                    <code className="block font-mono text-xs text-foreground break-all">{SSE_ENDPOINT}</code>
                    {token && (
                        <div className="flex items-center justify-between gap-2">
                            <span>Clients send your access token as a Bearer header. It expires in 24 hours; don&apos;t share it.</span>
                            <button
                                type="button"
                                onClick={() => copyToClipboard(token, 'token')}
                                aria-label="Copy access token"
                                className="inline-flex items-center gap-1 text-primary hover:underline cursor-pointer shrink-0"
                            >
                                {copied === 'token' ? <Check className="h-3 w-3" aria-hidden="true" /> : <Copy className="h-3 w-3" aria-hidden="true" />}
                                <span>{copied === 'token' ? 'Copied' : 'Copy token'}</span>
                            </button>
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
