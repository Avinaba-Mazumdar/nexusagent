import type { Metadata } from 'next';
import Link from 'next/link';
import { AlertOctagon, ArrowLeft, CheckCircle2, Cpu, FileCheck, KeyRound, Scale, ShieldAlert, Terminal } from 'lucide-react';
import { NexusLogo } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export const metadata: Metadata = {
    title: 'Terms and Conditions | NexusAgent',
    description: 'Terms of Service and Acceptable Use Policy for NexusAgent hosted on nexusagent.avinaba.com.'
};

export default function TermsAndConditionsPage() {
    const lastUpdated = 'October 17, 2026';

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
                    <Badge variant="outline" className="hidden sm:inline-flex text-[11px] font-mono border-border text-muted-foreground">
                        nexusagent.avinaba.com
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
                            <Scale className="h-3 w-3 text-primary" />
                            Legal &amp; Usage Framework
                        </Badge>
                        <span className="text-xs text-muted-foreground font-mono">Effective: {lastUpdated}</span>
                    </div>
                    <h1 className="text-3xl sm:text-4xl font-heading font-extrabold tracking-tight text-foreground">Terms and Conditions</h1>
                    <p className="text-sm sm:text-base text-muted-foreground leading-relaxed max-w-3xl">
                        These Terms and Conditions constitute a legally binding agreement between you and NexusAgent governing your access to and use of the
                        platform, API gateway, and autonomous agent orchestration services hosted at{' '}
                        <strong className="text-foreground font-semibold">nexusagent.avinaba.com</strong>.
                    </p>
                </div>

                {/* Key Guardrails Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <Card className="border-border bg-card shadow-2xs">
                        <CardContent className="p-4 space-y-1.5">
                            <div className="h-8 w-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center mb-2">
                                <Cpu className="h-4 w-4" />
                            </div>
                            <h3 className="font-heading font-bold text-xs text-foreground">Read-Only Tools</h3>
                            <p className="text-[11px] text-muted-foreground leading-snug">
                                Agent tools only search the knowledge base; they never modify data or execute code.
                            </p>
                        </CardContent>
                    </Card>

                    <Card className="border-border bg-card shadow-2xs">
                        <CardContent className="p-4 space-y-1.5">
                            <div className="h-8 w-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center mb-2">
                                <KeyRound className="h-4 w-4" />
                            </div>
                            <h3 className="font-heading font-bold text-xs text-foreground">BYOK User Liability</h3>
                            <p className="text-[11px] text-muted-foreground leading-snug">
                                Custom API keys (OpenRouter / Gemini) route pass-through requests under your provider agreement and billing terms.
                            </p>
                        </CardContent>
                    </Card>

                    <Card className="border-border bg-card shadow-2xs">
                        <CardContent className="p-4 space-y-1.5">
                            <div className="h-8 w-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center mb-2">
                                <AlertOctagon className="h-4 w-4" />
                            </div>
                            <h3 className="font-heading font-bold text-xs text-foreground">No Malicious Probing</h3>
                            <p className="text-[11px] text-muted-foreground leading-snug">
                                Automated vulnerability scanning, prompt injection attacks, and subdomain abuse will trigger immediate IP revocation.
                            </p>
                        </CardContent>
                    </Card>
                </div>

                {/* Terms Sections */}
                <div className="space-y-8 text-xs sm:text-sm text-muted-foreground leading-relaxed">
                    {/* 1. Acceptance & Eligibility */}
                    <section className="space-y-3">
                        <h2 className="text-lg font-heading font-bold text-foreground flex items-center gap-2">
                            <FileCheck className="h-4 w-4 text-primary" />
                            1. Acceptance of Terms &amp; Scope of Service
                        </h2>
                        <p>
                            By clicking &ldquo;Start as Guest&rdquo;, signing in via Google OAuth, or sending API requests to{' '}
                            <code className="font-mono text-xs text-foreground">nexusagent.avinaba.com</code>, you represent that you have read, understood, and
                            agree to be bound by these Terms and our Privacy Policy. If you do not agree, you must discontinue use immediately.
                        </p>
                        <p>
                            NexusAgent provides an open-source technical showcase demonstrating LangGraph multi-agent synthesis, Neon PostgreSQL pgvector
                            retrieval, model cascading, and MCP protocol integration. The service is provided primarily for architectural research, software
                            evaluation, and technical portfolio demonstration.
                        </p>
                    </section>

                    {/* 2. Acceptable Use Policy */}
                    <section className="space-y-3">
                        <h2 className="text-lg font-heading font-bold text-foreground flex items-center gap-2">
                            <ShieldAlert className="h-4 w-4 text-primary" />
                            2. Acceptable Use Policy (AUP)
                        </h2>
                        <p>
                            You agree not to use the services hosted at <code className="font-mono text-xs text-foreground">nexusagent.avinaba.com</code> to:
                        </p>
                        <ul className="space-y-2 list-none pl-1">
                            <li className="flex items-start gap-2">
                                <CheckCircle2 className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
                                <div>
                                    <strong className="text-foreground">Prompt Injection &amp; Jailbreak Exploits:</strong> Deliberately craft input payloads
                                    intended to bypass LLM system prompts, extract internal server instructions, or force unauthorized tool invocation.
                                </div>
                            </li>
                            <li className="flex items-start gap-2">
                                <CheckCircle2 className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
                                <div>
                                    <strong className="text-foreground">Infrastructure Abuse:</strong> Execute denial-of-service (DoS) attacks, flood the
                                    Cloudflare routing gateway, script rapid guest pass generation to circumvent rate limits, or scan backend endpoints.
                                </div>
                            </li>
                            <li className="flex items-start gap-2">
                                <CheckCircle2 className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
                                <div>
                                    <strong className="text-foreground">Prohibited Content Ingestion:</strong> Upload documents containing malware, malicious
                                    scripts, classified state materials, unauthorized personal identifiable information (PII), or infringing trade secrets.
                                </div>
                            </li>
                            <li className="flex items-start gap-2">
                                <CheckCircle2 className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
                                <div>
                                    <strong className="text-foreground">Subdomain Impersonation:</strong> Attempt DNS spoofing, CNAME hijacking, or impersonate
                                    the <code className="font-mono text-xs text-foreground">nexusagent.avinaba.com</code> origin or author.
                                </div>
                            </li>
                        </ul>
                    </section>

                    {/* 3. Autonomous Execution Disclaimer */}
                    <section className="space-y-3">
                        <h2 className="text-lg font-heading font-bold text-foreground flex items-center gap-2">
                            <Terminal className="h-4 w-4 text-primary" />
                            3. Autonomous Execution Disclaimer
                        </h2>
                        <p>
                            NexusAgent utilizes autonomous agent planning algorithms that evaluate user inputs and can propose tool calls such as document
                            searches and read-only database queries. You acknowledge and agree that:
                        </p>
                        <div className="p-4 rounded-xl border border-border bg-card/60 space-y-2">
                            <p className="text-xs">
                                Large language models are probabilistic and may produce hallucinations, inaccuracies, or incomplete architectural
                                recommendations. All generated architecture blueprints, Mermaid diagrams, and benchmark evaluations must be independently
                                validated before use in production settings.
                            </p>
                        </div>
                    </section>

                    {/* 4. BYOK API Keys & Third-Party Charges */}
                    <section className="space-y-3">
                        <h2 className="text-lg font-heading font-bold text-foreground flex items-center gap-2">
                            <KeyRound className="h-4 w-4 text-primary" />
                            4. Bring Your Own Key (BYOK) Agreement
                        </h2>
                        <p>
                            Users who utilize the Bring Your Own Key feature acknowledge that API keys for Google AI Studio (Gemini) or OpenRouter are passed
                            directly to their respective external endpoints.
                        </p>
                        <ul className="space-y-1.5 list-disc pl-5">
                            <li>
                                You are solely responsible for all billing costs, usage fees, and token charges incurred on your third-party provider accounts.
                            </li>
                            <li>
                                NexusAgent does not guarantee that your personal API keys will be accepted if your account has exhausted its external quotas.
                            </li>
                            <li>
                                NexusAgent holds zero liability for provider credential leaks caused by compromised user client machines or malicious
                                extensions.
                            </li>
                        </ul>
                    </section>

                    {/* 5. Intellectual Property & Open Source */}
                    <section className="space-y-3">
                        <h2 className="text-lg font-heading font-bold text-foreground flex items-center gap-2">
                            <Scale className="h-4 w-4 text-primary" />
                            5. Intellectual Property &amp; Open Source Licensing
                        </h2>
                        <p>The NexusAgent software codebase is open-source and governed by the repository license (MIT License / Apache 2.0).</p>
                        <p>
                            You retain full ownership of all original text prompts and proprietary documents uploaded to your session. By submitting queries,
                            you grant NexusAgent a temporary, non-exclusive license to process your input in-memory strictly to generate real-time analysis
                            responses.
                        </p>
                    </section>

                    {/* 6. Limitation of Liability & Warranty Disclaimer */}
                    <section className="space-y-3">
                        <h2 className="text-lg font-heading font-bold text-foreground flex items-center gap-2">
                            <AlertOctagon className="h-4 w-4 text-primary" />
                            6. &ldquo;AS-IS&rdquo; Disclaimer &amp; Limitation of Liability
                        </h2>
                        <p className="uppercase text-xs font-mono font-semibold text-foreground">
                            THE SERVICES AT NEXUSAGENT.AVINABA.COM ARE PROVIDED ON AN &ldquo;AS IS&rdquo; AND &ldquo;AS AVAILABLE&rdquo; BASIS WITHOUT
                            WARRANTIES OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, ACCURACY
                            OF AGENTIC SYNTHESIS, OR CONTINUOUS UPTIME.
                        </p>
                        <p>
                            To the maximum extent permitted by applicable law, neither the author, contributors, nor hosting providers shall be liable for any
                            indirect, incidental, consequential, or punitive damages, or loss of profits, data, or business opportunities arising from your use
                            or inability to use the platform.
                        </p>
                    </section>

                    {/* 7. Termination & Quota Governance */}
                    <section className="space-y-2">
                        <h2 className="text-base font-heading font-bold text-foreground">7. Quota Allocation &amp; Access Termination</h2>
                        <p>
                            Complimentary guest quotas (5 live queries) and token buckets are provided at our sole discretion. We reserve the right to throttle,
                            suspend, or permanently terminate access to any IP address or user account that exhibits abusive behavior, automated bot scraping,
                            or violations of these Terms.
                        </p>
                    </section>

                    {/* 8. Contact & Legal Inquiries */}
                    <section className="space-y-2 pt-2 border-t border-border">
                        <h2 className="text-base font-heading font-bold text-foreground">8. Inquiries &amp; Author Contact</h2>
                        <p>
                            For inquiries concerning these Terms or commercial architectural consulting, please contact:{' '}
                            <a
                                href="mailto:architect@nexusagent.internal?subject=Terms%20Inquiry%20-%20nexusagent.avinaba.com"
                                className="text-primary hover:underline font-medium"
                            >
                                architect@nexusagent.internal
                            </a>{' '}
                            or schedule a session via Cal.com.
                        </p>
                    </section>
                </div>

                {/* Footer Notice */}
                <div className="pt-8 border-t border-border text-center text-xs text-muted-foreground space-y-2">
                    <p>NexusAgent is an open-source project. View source and architectural specifications on GitHub.</p>
                    <div className="flex items-center justify-center gap-4 text-xs font-medium">
                        <Link href="/privacy" className="hover:text-primary transition-colors">
                            Privacy Policy
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
