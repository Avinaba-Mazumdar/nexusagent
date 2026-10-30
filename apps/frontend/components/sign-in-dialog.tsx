'use client';

import * as React from 'react';
import Link from 'next/link';
import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';

export interface SignInDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    googleClientId: string;
    gisLoaded: boolean;
    isGoogleLoading: boolean;
    isGuestLoading: boolean;
    error: string | null;
    /** A guest with uploaded documents: signing in with Google starts a fresh workspace. */
    hasGuestDocuments?: boolean;
    onGuestLogin: () => Promise<void>;
    renderGoogleButton: (container: HTMLDivElement | null) => void;
}

export function SignInDialog({
    open,
    onOpenChange,
    googleClientId,
    gisLoaded,
    isGoogleLoading,
    isGuestLoading,
    error,
    hasGuestDocuments = false,
    onGuestLogin,
    renderGoogleButton
}: SignInDialogProps) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-120 p-6 sm:p-7 rounded-3xl gap-4 border border-border/80 shadow-2xl">
                <DialogHeader className="text-left space-y-1">
                    <DialogTitle className="text-xl sm:text-2xl font-bold tracking-tight text-foreground font-heading">Sign In to NexusAgent</DialogTitle>
                    <DialogDescription className="text-xs text-muted-foreground leading-relaxed">
                        Choose an option to begin architecture analysis with your complimentary live LLM quota.
                    </DialogDescription>
                </DialogHeader>

                <div className="flex flex-col gap-4 pt-1">
                    {/* Live Models Banner */}
                    <div className="bg-banner-bg border border-banner-border rounded-2xl p-3 sm:p-3.5 flex items-center gap-3">
                        <span className="shrink-0 bg-banner-badge-bg text-banner-badge-text text-xs font-mono font-bold tracking-wider px-2 py-1 rounded-md uppercase">
                            Live models
                        </span>
                        <p className="text-xs sm:text-xs text-muted-foreground leading-snug">
                            Answers are generated live by Google Gemini. Guests get a small free allowance; Google accounts get more. Both refill hourly.
                        </p>
                    </div>

                    {/* Sign In with Google Card */}
                    <div className="border-2 border-featured-border rounded-2xl p-4 sm:p-5 bg-featured-bg relative">
                        <h3 className="text-sm font-bold text-foreground">Sign in with Google</h3>
                        <p className="text-xs text-muted-foreground mt-1 mb-4 leading-relaxed">Keeps your chat history across sessions and devices.</p>
                        {hasGuestDocuments && (
                            <p role="note" className="text-xs text-foreground mb-4 p-2.5 rounded-lg border border-warning-border bg-warning-bg leading-relaxed">
                                Signing in starts a fresh workspace. Documents uploaded as a guest will be deleted.
                            </p>
                        )}

                        {googleClientId ? (
                            isGoogleLoading ? (
                                <div className="h-11 flex items-center justify-center gap-2 text-xs text-muted-foreground" role="status">
                                    <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden="true" />
                                    <span>Connecting…</span>
                                </div>
                            ) : (
                                <div className="w-full min-h-11 flex items-center justify-center">
                                    {!gisLoaded && <span className="text-xs text-muted-foreground">Loading Google sign-in…</span>}
                                    <div ref={renderGoogleButton} className="w-full flex justify-center" />
                                </div>
                            )
                        ) : (
                            <p className="text-xs text-muted-foreground">Google sign-in isn&apos;t configured on this deployment.</p>
                        )}
                    </div>

                    {/* Divider with OR */}
                    <div className="relative flex items-center justify-center my-0.5">
                        <div className="absolute inset-0 flex items-center">
                            <div className="w-full border-t border-border/70" />
                        </div>
                        <div className="relative bg-card px-3 text-xs uppercase tracking-widest font-bold text-muted-foreground">OR</div>
                    </div>

                    {/* Continue as Guest Card */}
                    <div className="bg-secondary/40 dark:bg-secondary/20 border border-border/70 rounded-2xl p-4 sm:p-5 flex items-center justify-between gap-4">
                        <div className="space-y-1">
                            <h3 className="text-sm font-bold text-foreground">Continue as Guest</h3>
                            <p className="text-xs text-muted-foreground leading-relaxed max-w-55 sm:max-w-65">
                                Start right away with a free hourly allowance. No registration required.
                            </p>
                        </div>
                        <Button
                            variant="outline"
                            disabled={isGuestLoading || isGoogleLoading}
                            onClick={onGuestLogin}
                            className="shrink-0 bg-card hover:bg-secondary text-foreground font-semibold text-xs px-4 py-2.5 rounded-xl border-border/80 shadow-xs h-10"
                        >
                            {isGuestLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : 'Start as Guest'}
                        </Button>
                    </div>
                </div>

                <p className="text-xs text-muted-foreground text-center pt-1">
                    By continuing, you agree to our{' '}
                    <Link href="/terms" onClick={() => onOpenChange(false)} className="text-primary hover:underline">
                        Terms &amp; Conditions
                    </Link>{' '}
                    and{' '}
                    <Link href="/privacy" onClick={() => onOpenChange(false)} className="text-primary hover:underline">
                        Privacy Policy
                    </Link>
                    .
                </p>
                {error && (
                    <p className="text-xs text-destructive text-center pt-1" role="alert">
                        {error}
                    </p>
                )}
            </DialogContent>
        </Dialog>
    );
}
