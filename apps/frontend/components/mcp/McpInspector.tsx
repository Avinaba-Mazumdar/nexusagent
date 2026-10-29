'use client';

import * as React from 'react';
import { Terminal, Play, CheckCircle2, AlertCircle, Loader2, Database, Search, ArrowRight } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';

export interface McpToolOption {
    name: 'hybrid_rag_search' | 'mcp_sql_audit';
    label: string;
    description: string;
    defaultArgs: Record<string, unknown>;
}

const MCP_TOOLS: McpToolOption[] = [
    {
        name: 'hybrid_rag_search',
        label: 'RAG Search',
        description: 'Reciprocal Rank Fusion over benchmarks',
        defaultArgs: { query: 'Gemini 2.5 Flash CursorBench score', limit: 3 }
    },
    {
        name: 'mcp_sql_audit',
        label: 'SQL Audit',
        description: 'Read-only pgvector schema inspect',
        defaultArgs: { query: "SELECT tablename FROM pg_tables WHERE schemaname = 'public';" }
    }
];

interface McpInspectorProps {
    apiBase?: string;
    authToken?: string | null;
}

export function McpInspector({ apiBase = 'http://localhost:8000', authToken }: McpInspectorProps) {
    const [selectedTool, setSelectedTool] = React.useState<McpToolOption>(MCP_TOOLS[0]);
    const [argsJson, setArgsJson] = React.useState<string>(JSON.stringify(MCP_TOOLS[0].defaultArgs, null, 2));
    const [isLoading, setIsLoading] = React.useState(false);
    const [lastRequest, setLastRequest] = React.useState<Record<string, unknown> | null>(null);
    const [lastResponse, setLastResponse] = React.useState<Record<string, unknown> | null>(null);
    const [latencyMs, setLatencyMs] = React.useState<number | null>(null);
    const [errorMsg, setErrorMsg] = React.useState<string | null>(null);
    const [modalOpen, setModalOpen] = React.useState(false);

    const handleSelectTool = (tool: McpToolOption) => {
        setSelectedTool(tool);
        setArgsJson(JSON.stringify(tool.defaultArgs, null, 2));
        setErrorMsg(null);
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
            params: {
                name: selectedTool.name,
                arguments: parsedArgs
            }
        };

        setLastRequest(rpcPayload);
        const startTime = performance.now();

        try {
            const headers: Record<string, string> = {
                'Content-Type': 'application/json'
            };
            if (authToken) {
                headers.Authorization = `Bearer ${authToken}`;
            }

            const res = await fetch(`${apiBase}/api/mcp/v1`, {
                method: 'POST',
                headers,
                body: JSON.stringify(rpcPayload)
            });

            const elapsed = Math.round(performance.now() - startTime);
            setLatencyMs(elapsed);

            const json = await res.json();
            setLastResponse(json);

            if (!res.ok || json.error) {
                setErrorMsg(json.error?.message || `HTTP ${res.status}`);
            }
        } catch (err: unknown) {
            const elapsed = Math.round(performance.now() - startTime);
            setLatencyMs(elapsed);
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
                    <CardTitle className="text-xs font-heading flex items-center gap-1.5">
                        <Terminal className="h-3.5 w-3.5 text-primary" />
                        <span>MCP v2 Protocol Inspector</span>
                    </CardTitle>
                    <Badge variant="soft" className="text-[9px] font-mono">
                        v2024-11-05
                    </Badge>
                </div>
                <CardDescription className="text-xs text-muted-foreground flex items-center justify-between">
                    <span>Direct JSON-RPC 2.0 Gateway</span>
                    <span className="text-[10px] text-success font-medium flex items-center gap-1">
                        <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
                        SSE Ready
                    </span>
                </CardDescription>
            </CardHeader>
            <CardContent className="p-3 pt-0 space-y-2.5">
                {/* Tool Selector Tabs */}
                <div className="grid grid-cols-2 gap-1 bg-secondary/50 p-1 rounded-lg border border-border/60">
                    {MCP_TOOLS.map((t) => {
                        const active = t.name === selectedTool.name;
                        return (
                            <button
                                key={t.name}
                                type="button"
                                onClick={() => handleSelectTool(t)}
                                className={`text-[10px] py-1 px-1.5 rounded-md font-medium transition-all text-center truncate ${
                                    active ? 'bg-background text-foreground shadow-2xs font-semibold' : 'text-muted-foreground hover:text-foreground'
                                }`}
                                title={t.description}
                            >
                                {t.name === 'hybrid_rag_search' && <Search className="inline h-2.5 w-2.5 mr-1" />}
                                {t.name === 'mcp_sql_audit' && <Database className="inline h-2.5 w-2.5 mr-1" />}
                                {t.label}
                            </button>
                        );
                    })}
                </div>

                {/* Input Arguments Field */}
                <div className="space-y-1">
                    <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                        <span className="font-mono">arguments (JSON)</span>
                        <span className="text-[9px] truncate max-w-[170px]">{selectedTool.description}</span>
                    </div>
                    <textarea
                        aria-label="MCP Tool Arguments JSON"
                        value={argsJson}
                        onChange={(e) => setArgsJson(e.target.value)}
                        rows={3}
                        className="w-full h-30 font-mono text-[10px] bg-background border border-border rounded-lg p-2 leading-tight focus:outline-hidden focus:ring-1 focus:ring-primary text-foreground resize-none"
                    />
                </div>

                {/* Action Trigger */}
                <div className="flex items-center gap-2">
                    <Button
                        size="sm"
                        disabled={isLoading}
                        onClick={handleExecuteTool}
                        className="flex-1 h-7.5 text-xs font-semibold rounded-lg gap-1.5 shadow-2xs"
                    >
                        {isLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3 fill-current" />}
                        <span>{isLoading ? 'Executing...' : 'Invoke Tool'}</span>
                    </Button>

                    <Dialog open={modalOpen} onOpenChange={setModalOpen}>
                        <DialogTrigger asChild>
                            <Button size="sm" variant="outline" className="h-7.5 text-[11px] rounded-lg px-2 text-muted-foreground">
                                Raw Wire
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-xl max-h-[80vh] flex flex-col p-4">
                            <DialogHeader>
                                <DialogTitle className="text-sm font-heading flex items-center gap-1.5">
                                    <Terminal className="h-4 w-4 text-primary" />
                                    MCP v2 Wire Protocol Inspector
                                </DialogTitle>
                                <DialogDescription className="text-xs">
                                    Standardized JSON-RPC 2.0 frames dispatched to <code>/api/mcp/v1</code> &amp; SSE transport.
                                </DialogDescription>
                            </DialogHeader>

                            <div className="grid grid-cols-2 gap-3 flex-1 overflow-hidden pt-2 text-xs">
                                <div className="flex flex-col overflow-hidden">
                                    <div className="font-mono text-[10px] font-semibold text-muted-foreground pb-1">Outbound Request</div>
                                    <pre className="flex-1 overflow-auto bg-background p-2.5 rounded-lg border border-border font-mono text-[10px] text-foreground">
                                        {lastRequest ? JSON.stringify(lastRequest, null, 2) : '// No request executed yet'}
                                    </pre>
                                </div>
                                <div className="flex flex-col overflow-hidden">
                                    <div className="flex items-center justify-between pb-1">
                                        <span className="font-mono text-[10px] font-semibold text-muted-foreground">Inbound Response</span>
                                        {latencyMs !== null && (
                                            <Badge variant="outline" className="text-[9px] font-mono">
                                                {latencyMs}ms
                                            </Badge>
                                        )}
                                    </div>
                                    <pre className="flex-1 overflow-auto bg-background p-2.5 rounded-lg border border-border font-mono text-[10px] text-foreground">
                                        {lastResponse ? JSON.stringify(lastResponse, null, 2) : '// Awaiting response'}
                                    </pre>
                                </div>
                            </div>
                        </DialogContent>
                    </Dialog>
                </div>

                {/* Inline Status & Results Box */}
                {(lastResponse || errorMsg) && (
                    <div
                        className={`p-2 rounded-lg border text-[11px] space-y-1 ${
                            errorMsg ? 'bg-destructive/10 border-destructive/30' : 'bg-success-bg border-success-border'
                        }`}
                    >
                        <div className="flex items-center justify-between text-[10px] font-medium">
                            <span className="flex items-center gap-1">
                                {errorMsg ? (
                                    <>
                                        <AlertCircle className="h-3 w-3 text-destructive" />
                                        <span className="text-destructive font-semibold">RPC Error</span>
                                    </>
                                ) : (
                                    <>
                                        <CheckCircle2 className="h-3 w-3 text-success" />
                                        <span className="text-success font-semibold">RPC 200 OK</span>
                                    </>
                                )}
                            </span>
                            {latencyMs !== null && <span className="font-mono text-muted-foreground text-[9px]">{latencyMs}ms</span>}
                        </div>
                        <div className="font-mono text-[10px] max-h-20 overflow-y-auto whitespace-pre-wrap text-foreground/90">
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

                {/* Client Integration Tip */}
                <div className="pt-1 border-t border-border/60 flex items-center justify-between text-[10px] text-muted-foreground">
                    <span>Client config:</span>
                    <a href="/api/mcp/sse" target="_blank" rel="noreferrer" className="text-primary hover:underline font-mono inline-flex items-center gap-0.5">
                        GET /api/mcp/sse <ArrowRight className="h-2.5 w-2.5" />
                    </a>
                </div>
            </CardContent>
        </Card>
    );
}
