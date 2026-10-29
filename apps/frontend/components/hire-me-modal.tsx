'use client';

import * as React from 'react';
import { Briefcase, Calendar, CheckCircle2, ChevronRight, ExternalLink, Mail, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';

interface HireMeModalProps {
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
}

export function HireMeModal({ open, onOpenChange }: HireMeModalProps) {
    const calUrl = process.env.NEXT_PUBLIC_CAL_URL || 'https://cal.com/avinaba';
    // No fallback address: an unconfigured email would be a dead mailto link.
    const contactEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-lg p-0 overflow-hidden border border-border bg-card rounded-2xl shadow-2xl">
                {/* Header Graphic Gradient */}
                <div className="relative p-6 pb-4 bg-gradient-to-br from-primary/15 via-primary/5 to-transparent border-b border-border">
                    <div className="flex items-center gap-2 mb-2">
                        <Badge variant="soft" className="gap-1 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider">
                            <Sparkles className="h-3 w-3 text-primary" />
                            Custom Enterprise Architecture
                        </Badge>
                    </div>
                    <DialogTitle className="text-xl font-heading font-extrabold tracking-tight text-foreground">
                        Looking for Custom Ingestion &amp; Private Agents?
                    </DialogTitle>
                    <DialogDescription className="text-xs text-muted-foreground mt-1.5 leading-relaxed">
                        This public open-source showcase runs on a small shared demo quota. Hire me to build and deploy agentic systems on your own data and
                        infrastructure.
                    </DialogDescription>
                </div>

                {/* Body Content */}
                <div className="p-6 space-y-4 text-xs">
                    <div className="space-y-2.5">
                        <h4 className="font-heading font-bold text-foreground flex items-center gap-2">
                            <Briefcase className="h-3.5 w-3.5 text-primary" />
                            What I build for clients:
                        </h4>
                        <ul className="grid grid-cols-1 gap-2 text-muted-foreground">
                            <li className="flex items-start gap-2">
                                <CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                                <span>
                                    <strong>Enterprise Data Connectors:</strong> Continuous sync with Notion, Google Drive, Jira, Confluence, Slack &amp;
                                    private S3 buckets.
                                </span>
                            </li>
                            <li className="flex items-start gap-2">
                                <CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                                <span>
                                    <strong>Zero-Retention Hybrid RAG:</strong> pgvector / Pinecone / Qdrant with local embeddings, semantic reranking, and
                                    sub-second retrieval.
                                </span>
                            </li>
                            <li className="flex items-start gap-2">
                                <CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                                <span>
                                    <strong>Autonomous LangGraph Workflows:</strong> Multi-agent verification, human-in-the-loop tool approvals, and OWASP ASI
                                    security compliance.
                                </span>
                            </li>
                        </ul>
                    </div>

                    <div className="rounded-xl border border-primary/20 bg-primary/5 p-3 flex items-center justify-between">
                        <div>
                            <p className="font-semibold text-foreground text-xs">Available for contract &amp; advisory</p>
                            <p className="text-[11px] text-muted-foreground">Typical turnaround for POC to staging: 2 to 4 weeks</p>
                        </div>
                        <Badge variant="outline" className="text-[11px] font-mono border-primary/30 text-primary">
                            Open to projects
                        </Badge>
                    </div>

                    {/* Action CTAs */}
                    <div className="pt-2 flex flex-col sm:flex-row gap-2.5">
                        <Button asChild variant="default" className="flex-1 justify-center gap-2 text-xs font-bold rounded-xl h-10 shadow-xs">
                            <a href={calUrl} target="_blank" rel="noreferrer">
                                <Calendar className="h-4 w-4" />
                                <span>Book Architecture Call</span>
                                <ChevronRight className="h-3.5 w-3.5 opacity-70" />
                            </a>
                        </Button>
                        {contactEmail && (
                            <Button
                                asChild
                                variant="outline"
                                className="flex-1 justify-center gap-2 text-xs font-semibold rounded-xl h-10 border-border hover:bg-secondary"
                            >
                                <a href={`mailto:${contactEmail}?subject=Custom%20Agentic%20RAG%20Inquiry`}>
                                    <Mail className="h-4 w-4" />
                                    <span>Inquire via Email</span>
                                    <ExternalLink className="h-3.5 w-3.5 opacity-70" />
                                </a>
                            </Button>
                        )}
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
}
