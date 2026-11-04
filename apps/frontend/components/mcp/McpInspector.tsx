'use client';

import * as React from 'react';
import { Terminal, Copy, Check } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { MCP_URL, buildClientConfig } from '@/lib/mcp-client-config';

interface McpInspectorProps {
    onOpenSignIn?: () => void;
}

export function McpInspector({ onOpenSignIn: _onOpenSignIn }: McpInspectorProps = {}) {
    const [copiedUrl, setCopiedUrl] = React.useState(false);
    const [copiedConfig, setCopiedConfig] = React.useState(false);

    const clientConfigJson = React.useMemo(() => buildClientConfig(), []);

    const copyUrl = async () => {
        try {
            await navigator.clipboard.writeText(MCP_URL);
            setCopiedUrl(true);
            setTimeout(() => setCopiedUrl(false), 2000);
        } catch {
            // Clipboard access blocked
        }
    };

    const copyConfig = async () => {
        try {
            await navigator.clipboard.writeText(clientConfigJson);
            setCopiedConfig(true);
            setTimeout(() => setCopiedConfig(false), 2000);
        } catch {
            // Clipboard access blocked
        }
    };

    return (
        <Card className="shadow-2xs border-border" data-testid="mcp-inspector">
            <CardHeader className="p-3 pb-2">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-heading flex items-center gap-1.5">
                        <Terminal className="h-3.5 w-3.5 text-primary" />
                        <span>Connect MCP Client</span>
                    </CardTitle>
                    <Badge variant="outline" className="text-[10px] font-mono border-emerald-500/30 text-emerald-500">
                        Public &middot; Read-only
                    </Badge>
                </div>
                <CardDescription className="text-xs text-muted-foreground">Connect external LLM clients via the Model Context Protocol.</CardDescription>
            </CardHeader>

            <CardContent className="p-3 pt-1 space-y-3">
                <div className="rounded-md border border-border/60 bg-muted/30 p-2.5 text-xs text-muted-foreground">
                    <p className="font-medium text-foreground">Read-only. Searches the 4 public benchmark documents.</p>
                </div>

                {/* MCP URL section */}
                <div className="space-y-1.5">
                    <label className="text-[11px] font-medium text-foreground/80 flex items-center justify-between">
                        <span>Streamable HTTP Endpoint</span>
                    </label>
                    <div className="flex items-center gap-1.5">
                        <code className="flex-1 rounded border border-border bg-muted/50 px-2 py-1 font-mono text-[11px] text-foreground truncate select-all">
                            {MCP_URL}
                        </code>
                        <Button variant="outline" size="sm" className="h-7 px-2 text-xs shrink-0" onClick={copyUrl} aria-label="Copy MCP URL">
                            {copiedUrl ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                            <span className="ml-1 text-[11px]">{copiedUrl ? 'Copied' : 'Copy'}</span>
                        </Button>
                    </div>
                </div>

                {/* Connection instructions */}
                <div className="space-y-2.5 pt-1 text-xs">
                    <div className="space-y-1">
                        <div className="font-semibold text-foreground flex items-center gap-1">
                            <span>Claude (claude.ai / Desktop)</span>
                        </div>
                        <p className="text-[11px] text-muted-foreground font-mono bg-muted/40 p-1.5 rounded border border-border/40">
                            Settings &rarr; Connectors &rarr; Add custom connector &rarr; paste the URL
                        </p>
                    </div>

                    <div className="space-y-1">
                        <div className="font-semibold text-foreground flex items-center gap-1">
                            <span>ChatGPT</span>
                        </div>
                        <p className="text-[11px] text-muted-foreground font-mono bg-muted/40 p-1.5 rounded border border-border/40">
                            Settings &rarr; Apps &amp; Connectors &rarr; Advanced &rarr; Developer mode &rarr; Create connector &rarr; paste the URL, no auth
                        </p>
                    </div>

                    <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                            <span className="font-semibold text-foreground">Cursor / Claude Code / others</span>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 px-1.5 text-[11px] text-muted-foreground hover:text-foreground"
                                onClick={copyConfig}
                                aria-label="Copy JSON config"
                            >
                                {copiedConfig ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                                <span className="ml-1">{copiedConfig ? 'Copied' : 'Copy JSON'}</span>
                            </Button>
                        </div>
                        <pre className="rounded border border-border bg-muted/50 p-2 font-mono text-[11px] text-foreground overflow-x-auto max-h-36">
                            {clientConfigJson}
                        </pre>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
