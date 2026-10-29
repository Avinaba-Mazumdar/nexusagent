'use client';

import * as React from 'react';
import { ShieldAlert, Check, X, Code2, AlertTriangle, Timer } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { PendingApproval } from '@/hooks/useAgentStream';

interface ApprovalModalProps {
    open: boolean;
    approval: PendingApproval | null;
    onResolve: (decision: 'approve' | 'reject') => void;
}

export function ApprovalModal({ open, approval, onResolve }: ApprovalModalProps) {
    const [secondsLeft, setSecondsLeft] = React.useState<number | null>(null);
    const onResolveRef = React.useRef(onResolve);
    onResolveRef.current = onResolve;

    // Mirror the server-side approval timeout: count down and close as denied once it lapses.
    React.useEffect(() => {
        const timeout = approval?.timeoutSeconds;
        if (!open || !timeout) {
            setSecondsLeft(null);
            return;
        }
        const deadline = Date.now() + timeout * 1000;
        setSecondsLeft(timeout);
        const interval = setInterval(() => {
            const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
            setSecondsLeft(remaining);
            if (remaining === 0) {
                clearInterval(interval);
                onResolveRef.current('reject');
            }
        }, 1000);
        return () => clearInterval(interval);
    }, [open, approval?.approvalId, approval?.timeoutSeconds]);

    if (!approval) return null;

    const isHighRisk = approval.riskLevel === 'high';
    const codeArg = typeof approval.arguments?.code === 'string' ? approval.arguments.code : null;

    return (
        <Dialog open={open} onOpenChange={(val) => !val && onResolve('reject')}>
            <DialogContent
                className="max-w-md sm:max-w-lg p-5 border-border shadow-xl rounded-2xl"
                data-testid="hitl-approval-modal"
                aria-describedby="hitl-dialog-description"
            >
                <DialogHeader className="space-y-2 pb-1">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <div
                                className={`p-2 rounded-xl border ${isHighRisk ? 'bg-destructive/15 border-destructive/30 text-destructive' : 'bg-warning-bg border-warning-border text-warning'}`}
                            >
                                <ShieldAlert className="h-5 w-5" />
                            </div>
                            <DialogTitle className="text-sm font-heading font-bold text-foreground">HITL Security Authorization Required</DialogTitle>
                        </div>
                        <Badge variant={isHighRisk ? 'destructive' : 'outline'} className="text-[10px] font-mono uppercase tracking-wider">
                            {approval.riskLevel} Risk
                        </Badge>
                    </div>
                    <DialogDescription id="hitl-dialog-description" className="text-xs text-muted-foreground leading-relaxed">
                        The agent paused at tool <code>{approval.tool}</code> and needs your confirmation before running this database operation.
                    </DialogDescription>
                    {secondsLeft !== null && (
                        <p className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground" role="timer" aria-live="off">
                            <Timer className="h-3.5 w-3.5" aria-hidden="true" />
                            <span>
                                Auto-denies in <strong className="tabular-nums text-foreground">{secondsLeft}s</strong>
                            </span>
                        </p>
                    )}
                </DialogHeader>

                <div className="space-y-3 py-2 text-xs">
                    {/* Tool & Session Metadata */}
                    <div className="flex items-center justify-between bg-secondary/40 border border-border/80 px-3 py-2 rounded-xl text-[11px] font-mono">
                        <span className="text-muted-foreground flex items-center gap-1.5">
                            <Code2 className="h-3.5 w-3.5 text-primary" />
                            Tool: <strong className="text-foreground">{approval.tool}</strong>
                        </span>
                        <span className="text-muted-foreground text-[10px]">
                            ID: <span className="text-foreground">{approval.approvalId}</span>
                        </span>
                    </div>

                    {/* Code or Arguments payload viewer */}
                    <div className="space-y-1">
                        <label className="text-[10px] font-mono text-muted-foreground font-semibold">Execution Payload:</label>
                        <pre className="p-3 rounded-xl bg-card border border-border text-[11px] font-mono max-h-48 overflow-y-auto whitespace-pre-wrap text-foreground/90 leading-tight">
                            {codeArg || JSON.stringify(approval.arguments, null, 2)}
                        </pre>
                    </div>

                    {/* Security Notice */}
                    <div className="p-2.5 rounded-xl bg-warning-bg border border-warning-border flex items-start gap-2 text-[11px] text-muted-foreground leading-normal">
                        <AlertTriangle className="h-4 w-4 text-warning shrink-0 mt-0.5" aria-hidden="true" />
                        <span>Denying skips this tool; the agent continues and answers without its output.</span>
                    </div>
                </div>

                <DialogFooter className="flex flex-row justify-end gap-2 pt-2 border-t border-border">
                    <Button
                        type="button"
                        variant="outline"
                        onClick={() => onResolve('reject')}
                        className="h-9 px-4 text-xs font-semibold rounded-xl text-destructive hover:bg-destructive/10 border-destructive/30 gap-1.5"
                    >
                        <X className="h-3.5 w-3.5" />
                        <span>Deny &amp; Skip</span>
                    </Button>
                    <Button
                        type="button"
                        variant="default"
                        onClick={() => onResolve('approve')}
                        className="h-9 px-4 text-xs font-bold rounded-xl gap-1.5 bg-success hover:opacity-90 text-success-foreground shadow-xs"
                    >
                        <Check className="h-3.5 w-3.5" />
                        <span>Authorize &amp; Run</span>
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
