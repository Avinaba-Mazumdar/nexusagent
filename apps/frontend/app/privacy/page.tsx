import type { Metadata } from 'next';
import Link from 'next/link';
import { ArrowLeft, CheckCircle2, Database, Eye, Globe, KeyRound, Lock, Server, Shield, Trash2, UserCheck } from 'lucide-react';
import { NexusLogo } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { AUDIT_RETENTION_DAYS, SITE_HOST } from '@/lib/site';

export const metadata: Metadata = {
    title: 'Privacy Policy | NexusAgent',
    description: `Privacy Policy and data governance practices for NexusAgent hosted on ${SITE_HOST}.`
};

export default function PrivacyPolicyPage() {
    const lastUpdated = 'October 30, 2026';

    return (
        <div className="min-h-screen bg-background text-foreground flex flex-col">
            {/* Header / Navigation Bar */}
            <header className="h-14 bg-card border-b border-border px-4 md:px-6 flex items-center justify-between sticky top-0 z-30 backdrop-blur-md bg-card/90">
                <div className="flex items-center gap-3">
                    <Link href="/" className="flex items-center gap-2 group cursor-pointer" aria-label="Return to NexusAgent Studio">
                        <NexusLogo className="h-8 w-8 rounded-xl shadow-xs shrink-0 transition-transform group-hover:scale-105" />
                        <span className="font-heading font-bold text-sm tracking-tight text-foreground">NexusAgent</span>
                    </Link>
                    <span className="text-muted-foreground text-xs hidden sm:inline-block">/</span>
                    <Badge variant="outline" className="hidden sm:inline-flex text-xs font-mono border-border text-muted-foreground">
                        {SITE_HOST}
                    </Badge>
                </div>

                <div className="flex items-center gap-2">
                    <Button asChild variant="outline" size="sm" className="text-xs font-semibold rounded-xl h-8 gap-1.5 border-border">
                        <Link href="/">
                            <ArrowLeft className="h-3.5 w-3.5" />
                            <span>Back to Canvas</span>
                        </Link>
                    </Button>
                </div>
            </header>

            {/* Content Container */}
            <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-8 sm:py-12 space-y-8">
                {/* Hero Header */}
                <div className="space-y-3 pb-6 border-b border-border">
                    <div className="flex items-center gap-2">
                        <Badge variant="soft" className="gap-1.5 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider">
                            <Shield className="h-3 w-3 text-primary" />
                            Security &amp; Data Governance
                        </Badge>
                        <span className="text-xs text-muted-foreground font-mono">Effective: {lastUpdated}</span>
                    </div>
                    <h1 className="text-3xl sm:text-4xl font-heading font-extrabold tracking-tight text-foreground">Privacy Policy</h1>
                    <p className="text-sm sm:text-base text-muted-foreground leading-relaxed max-w-3xl">
                        This Privacy Policy governs the collection, processing, and protection of data on{' '}
                        <strong className="text-foreground font-semibold">{SITE_HOST}</strong>, an open-source autonomous systems analyst and architecture
                        intelligence platform. We keep the data we hold to a minimum and describe it below.
                    </p>
                </div>

                {/* Core Principles Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <Card className="border-border bg-card shadow-2xs">
                        <CardContent className="p-4 space-y-1.5">
                            <div className="h-8 w-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center mb-2">
                                <Lock className="h-4 w-4" />
                            </div>
                            <h3 className="font-heading font-bold text-xs text-foreground">Host-Only Scoping</h3>
                            <p className="text-xs text-muted-foreground leading-snug">
                                Session tokens remain strictly partitioned to <code className="text-primary font-mono text-xs">{SITE_HOST}</code> with no
                                cross-subdomain sharing.
                            </p>
                        </CardContent>
                    </Card>

                    <Card className="border-border bg-card shadow-2xs">
                        <CardContent className="p-4 space-y-1.5">
                            <div className="h-8 w-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center mb-2">
                                <Trash2 className="h-4 w-4" />
                            </div>
                            <h3 className="font-heading font-bold text-xs text-foreground">Short Retention</h3>
                            <p className="text-xs text-muted-foreground leading-snug">
                                Inactive guest accounts and their documents are deleted after 24 hours. Tool audit records are deleted after{' '}
                                {AUDIT_RETENTION_DAYS} days.
                            </p>
                        </CardContent>
                    </Card>

                    <Card className="border-border bg-card shadow-2xs">
                        <CardContent className="p-4 space-y-1.5">
                            <div className="h-8 w-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center mb-2">
                                <KeyRound className="h-4 w-4" />
                            </div>
                            <h3 className="font-heading font-bold text-xs text-foreground">Zero Third-Party Trackers</h3>
                            <p className="text-xs text-muted-foreground leading-snug">
                                We run no third-party analytics, behavioral tracking, or fingerprinting scripts on our platform.
                            </p>
                        </CardContent>
                    </Card>
                </div>

                {/* Section Details */}
                <div className="space-y-8 text-xs sm:text-sm text-muted-foreground leading-relaxed">
                    {/* 1. Information We Collect */}
                    <section className="space-y-3">
                        <h2 className="text-lg font-heading font-bold text-foreground flex items-center gap-2">
                            <Eye className="h-4 w-4 text-primary" />
                            1. Information We Collect
                        </h2>
                        <p>
                            Depending on whether you access NexusAgent via a 1-Click Guest Pass or via Google Authentication, we collect only the minimal data
                            required to operate the autonomous analysis engine:
                        </p>
                        <ul className="space-y-2 list-none pl-1">
                            <li className="flex items-start gap-2">
                                <CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                                <div>
                                    <strong className="text-foreground">Ephemeral Guest Pass Data:</strong> When launching an instant guest session, we create a
                                    random account ID. We store your IP address and a hash of a device identifier (not the identifier itself) to enforce rate
                                    limits and prevent abuse. No name, email, or physical identifier is collected.
                                </div>
                            </li>
                            <li className="flex items-start gap-2">
                                <CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                                <div>
                                    <strong className="text-foreground">Google OAuth Profile:</strong> If you elect to authenticate using Google Identity
                                    Services, we receive your verified email address, full name, and avatar URL. This allows persisting your conversation
                                    history across devices. We also store the IP address of your most recent request for rate limiting.
                                </div>
                            </li>
                            <li className="flex items-start gap-2">
                                <CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                                <div>
                                    <strong className="text-foreground">System Queries &amp; Document Ingestion:</strong> Prompts submitted to the Synthesis
                                    Canvas and Markdown documents uploaded to the Document Vault are parsed and stored with vector embeddings in Neon
                                    PostgreSQL. Your uploaded documents are only visible to your account (enforced by access checks in the application). The
                                    text of your questions is also recorded in a tool audit log.
                                </div>
                            </li>
                        </ul>
                    </section>

                    {/* 2. Subdomain Architecture & Security */}
                    <section className="space-y-3">
                        <h2 className="text-lg font-heading font-bold text-foreground flex items-center gap-2">
                            <Globe className="h-4 w-4 text-primary" />
                            2. Subdomain Architecture &amp; Security Boundary
                        </h2>
                        <p>
                            NexusAgent is deployed exclusively at the dedicated subdomain <code className="font-mono text-xs text-foreground">{SITE_HOST}</code>
                            . To safeguard your session against cross-origin or cross-subdomain attacks:
                        </p>
                        <div className="p-4 rounded-xl border border-border bg-card/60 space-y-2">
                            <p className="font-semibold text-foreground text-xs">Host-Only Token Scoping:</p>
                            <p className="text-xs">
                                Your session token is kept in this browser&apos;s local storage, which browsers isolate per origin, so other subdomains under{' '}
                                <code className="font-mono text-xs">avinaba.com</code> (such as portfolio, blog, or mail services) cannot read it. Signing out
                                revokes the token on the server.
                            </p>
                        </div>
                    </section>

                    {/* 3. Third-Party Sub-Processors */}
                    <section className="space-y-3">
                        <h2 className="text-lg font-heading font-bold text-foreground flex items-center gap-2">
                            <Server className="h-4 w-4 text-primary" />
                            3. Infrastructure &amp; Third-Party Processors
                        </h2>
                        <p>These third parties host the service and process your data on our behalf:</p>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                            <div className="p-3 rounded-xl border border-border bg-card space-y-1">
                                <span className="font-bold text-foreground text-xs">Google AI / Google Cloud</span>
                                <p className="text-xs text-muted-foreground">
                                    Gemini model execution and embeddings. Your questions, excerpts of retrieved documents and the text of documents you upload
                                    are sent to the Gemini API. This deployment uses the <strong className="text-foreground">Gemini API free tier</strong>.
                                    Under Google&apos;s free-tier terms, content sent to the API is used to improve Google&apos;s products. Do not ask about or
                                    upload confidential or personal information. See{' '}
                                    <a
                                        href="https://ai.google.dev/gemini-api/terms"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="underline hover:text-primary"
                                    >
                                        Google&apos;s Gemini API terms
                                    </a>
                                    .
                                </p>
                            </div>
                            <div className="p-3 rounded-xl border border-border bg-card space-y-1">
                                <span className="font-bold text-foreground text-xs">Neon Inc. (PostgreSQL 18)</span>
                                <p className="text-xs text-muted-foreground">
                                    Serverless PostgreSQL with pgvector for vectorized document storage, chat histories, and quota ledgers.
                                </p>
                            </div>
                            <div className="p-3 rounded-xl border border-border bg-card space-y-1">
                                <span className="font-bold text-foreground text-xs">Cloudflare, Inc.</span>
                                <p className="text-xs text-muted-foreground">
                                    Edge routing, TLS termination and DDoS mitigation, when enabled for this deployment.
                                </p>
                            </div>
                            <div className="p-3 rounded-xl border border-border bg-card space-y-1">
                                <span className="font-bold text-foreground text-xs">Google Identity Services</span>
                                <p className="text-xs text-muted-foreground">Cryptographic JWT verification for seamless Google Single Sign-On (SSO).</p>
                            </div>
                        </div>
                    </section>

                    {/* 4. Automated Pruning & Retention */}
                    <section className="space-y-3">
                        <h2 className="text-lg font-heading font-bold text-foreground flex items-center gap-2">
                            <Database className="h-4 w-4 text-primary" />
                            4. Data Retention &amp; Automated Pruning
                        </h2>
                        <p>We adhere to strict data minimization principles:</p>
                        <ul className="space-y-1.5 list-disc pl-5">
                            <li>
                                <strong className="text-foreground">Ephemeral Guest Records:</strong> Inactive guest sessions are deleted after 24 hours by a
                                scheduled job (<code className="font-mono text-xs">prune_guests.py</code>), removing their quota records and any documents they
                                uploaded.
                            </li>
                            <li>
                                <strong className="text-foreground">Authenticated User Workspaces:</strong> Retained until the user requests account deletion or
                                deletes individual chats or uploaded documents in the app.
                            </li>
                            <li>
                                <strong className="text-foreground">Tool Audit Records:</strong> Each search, upload and tool call is logged with its input
                                (including your query text) for security review, and deleted after {AUDIT_RETENTION_DAYS} days. The run log in the observability
                                panel is held in your browser only.
                            </li>
                        </ul>
                    </section>

                    {/* 5. User Rights & Data Subject Controls */}
                    <section className="space-y-3">
                        <h2 className="text-lg font-heading font-bold text-foreground flex items-center gap-2">
                            <UserCheck className="h-4 w-4 text-primary" />
                            5. Your Rights &amp; Data Deletion Requests
                        </h2>
                        <p>Regardless of your jurisdiction (including GDPR, UK GDPR, and CCPA/CPRA rights), you have the right to:</p>
                        <ul className="space-y-1 list-disc pl-5">
                            <li>Access all personal data and conversation blueprints associated with your verified account.</li>
                            <li>Request immediate and permanent deletion of your profile, stored documents, and chat histories.</li>
                            <li>Revoke Google OAuth token authorization at any time via your Google Account Security settings.</li>
                            <li>Clear local storage directly within your web browser.</li>
                        </ul>
                        <p className="pt-2">
                            To initiate an account deletion or data subject inquiry, contact the maintainer at{' '}
                            {process.env.NEXT_PUBLIC_CONTACT_EMAIL ? (
                                <a
                                    href={`mailto:${process.env.NEXT_PUBLIC_CONTACT_EMAIL}?subject=Privacy%20Data%20Request%20-%20${SITE_HOST}`}
                                    className="text-primary hover:underline font-medium"
                                >
                                    {process.env.NEXT_PUBLIC_CONTACT_EMAIL}
                                </a>
                            ) : (
                                <span>the contact address listed in the repository README</span>
                            )}
                            .
                        </p>
                    </section>

                    {/* 6. Updates to this Policy */}
                    <section className="space-y-2 pt-2 border-t border-border">
                        <h2 className="text-base font-heading font-bold text-foreground">6. Modifications to This Policy</h2>
                        <p>
                            We may update this Privacy Policy periodically to reflect architectural updates or security hardening on{' '}
                            <code className="font-mono text-xs text-foreground">{SITE_HOST}</code>. The revision date at the top of this document will denote
                            the active version.
                        </p>
                    </section>
                </div>

                {/* Footer Notice */}
                <div className="pt-8 border-t border-border text-center text-xs text-muted-foreground space-y-2">
                    <p>NexusAgent is an open-source project. View source and architectural specifications on GitHub.</p>
                    <div className="flex items-center justify-center gap-4 text-xs font-medium">
                        <Link href="/terms" className="hover:text-primary transition-colors">
                            Terms &amp; Conditions
                        </Link>
                        <span>•</span>
                        <Link href="/" className="hover:text-primary transition-colors">
                            Return to Canvas
                        </Link>
                    </div>
                </div>
            </main>
        </div>
    );
}
