'use client';

import * as React from 'react';
import Link from 'next/link';
import { Activity, LogOut, Moon, Sun, LogIn } from 'lucide-react';
import { NexusLogo } from '@/components/icons';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Switch } from '@/components/ui/switch';
import type { UserSession } from '@nexusagent/contracts';

export interface AppHeaderProps {
    user: UserSession | null;
    quotaRemaining: number;
    bucketCapacity: number;
    isDarkTheme: boolean;
    onToggleTheme: () => void;
    isObservabilityOpen: boolean;
    onToggleObservability: () => void;
    isStreaming: boolean;
    onOpenSignIn: () => void;
    onLogout: () => void;
}

function initials(name?: string | null): string {
    if (!name) return 'U';
    return name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .slice(0, 2)
        .toUpperCase();
}

export function AppHeader({
    user,
    quotaRemaining,
    bucketCapacity,
    isDarkTheme,
    onToggleTheme,
    isObservabilityOpen,
    onToggleObservability,
    isStreaming,
    onOpenSignIn,
    onLogout
}: AppHeaderProps) {
    const [popoverOpen, setPopoverOpen] = React.useState(false);

    return (
        <header
            role="banner"
            aria-label="Command Center Navigation"
            className="h-14 bg-card border-b border-border px-4 md:px-6 flex items-center justify-between gap-2 shrink-0 z-30"
        >
            <div className="flex items-center gap-3 min-w-0">
                <NexusLogo className="h-8 w-8 rounded-xl shadow-xs shrink-0" aria-hidden="true" />
                <span className="font-heading font-bold text-sm tracking-tight text-foreground truncate">NexusAgent</span>
            </div>

            <div className="flex items-center gap-2 shrink-0">
                {/* Theme Toggle Button */}
                <Button
                    type="button"
                    variant="outline"
                    size="icon-sm"
                    onClick={onToggleTheme}
                    className="rounded-xl border-border h-9 w-9 text-muted-foreground hover:text-foreground shrink-0 cursor-pointer"
                    aria-label="Toggle theme mode"
                    title={isDarkTheme ? 'Switch to light mode' : 'Switch to dark mode'}
                >
                    {isDarkTheme ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                </Button>

                {/* Observability Panel Toggle Button */}
                <Button
                    type="button"
                    variant="outline"
                    size="icon-sm"
                    onClick={onToggleObservability}
                    className={`relative hidden xl:inline-flex rounded-xl border-border h-9 w-9 shrink-0 cursor-pointer transition-colors ${
                        isObservabilityOpen ? 'bg-secondary text-primary border-primary/40' : 'text-muted-foreground hover:text-foreground'
                    }`}
                    title={isObservabilityOpen ? 'Hide Observability Panel' : 'Show Observability Panel'}
                    aria-label="Toggle agent telemetry and observability panel"
                    aria-pressed={isObservabilityOpen}
                >
                    <Activity className="h-4 w-4" aria-hidden="true" />
                    {isStreaming && <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-primary animate-pulse" />}
                </Button>

                {/* Pre-loaded Guest / User Quota Badge */}
                {user && (
                    <div
                        className="hidden sm:flex items-center gap-1.5 h-9 px-3 rounded-xl bg-secondary/50 border border-border text-xs font-medium shrink-0"
                        title={`${quotaRemaining} of ${bucketCapacity} query quota remaining`}
                        data-testid="quota-badge"
                    >
                        <span className={`h-2 w-2 rounded-full shrink-0 ${quotaRemaining > 0 ? 'bg-success' : 'bg-destructive'}`} />
                        <span className="font-semibold text-foreground tabular-nums">
                            {quotaRemaining}/{bucketCapacity}
                        </span>
                        <span className="text-muted-foreground">{user.isGuest ? 'Guest' : 'Questions'}</span>
                    </div>
                )}

                {user ? (
                    <Popover open={popoverOpen} onOpenChange={setPopoverOpen}>
                        <PopoverTrigger asChild>
                            <button
                                type="button"
                                aria-label="User profile menu"
                                className="group relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full p-0 border-0 bg-transparent cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                            >
                                <Avatar className="h-9 w-9 border border-border shadow-xs transition-colors duration-150 group-hover:border-primary group-hover:ring-2 group-hover:ring-primary/25">
                                    {user.avatarUrl ? <AvatarImage src={user.avatarUrl} alt={user.name} /> : null}
                                    <AvatarFallback className="bg-accent text-accent-foreground text-xs font-bold">{initials(user.name)}</AvatarFallback>
                                </Avatar>
                            </button>
                        </PopoverTrigger>
                        <PopoverContent
                            align="end"
                            className="w-80 max-w-[calc(100vw-2rem)] p-4 rounded-2xl shadow-xl border-border bg-popover text-popover-foreground"
                        >
                            {/* User Info */}
                            <div className="flex items-center gap-3 pb-3 border-b border-border">
                                <Avatar className="h-10 w-10 border border-border shrink-0">
                                    {user.avatarUrl ? <AvatarImage src={user.avatarUrl} alt={user.name} /> : null}
                                    <AvatarFallback className="bg-accent text-accent-foreground text-sm font-bold">{initials(user.name)}</AvatarFallback>
                                </Avatar>
                                <div className="flex flex-col min-w-0 flex-1">
                                    <div className="flex items-center gap-1.5">
                                        <span className="font-heading font-bold text-sm text-foreground truncate">{user.name}</span>
                                        <Badge variant={user.isGuest ? 'outline' : 'soft'} className="text-xs px-1.5 py-0 font-medium shrink-0">
                                            {user.isGuest ? 'Guest' : 'Verified'}
                                        </Badge>
                                    </div>
                                    <span className="text-xs text-muted-foreground truncate">{user.email ? user.email : 'Guest session'}</span>
                                </div>
                            </div>

                            {/* Quota Section */}
                            <div className="py-3 border-b border-border space-y-1.5">
                                <div className="flex items-center justify-between text-xs">
                                    <span className="font-medium text-muted-foreground">API Quota</span>
                                    <span className="font-bold text-primary bg-accent px-2 py-0.5 rounded-md border border-border">
                                        {quotaRemaining}/{bucketCapacity} Quota
                                    </span>
                                </div>
                                <div className="w-full bg-secondary h-1.5 rounded-full overflow-hidden">
                                    <div
                                        className="bg-primary h-full rounded-full transition-all duration-300"
                                        style={{ width: `${Math.min(100, Math.max(0, (quotaRemaining / bucketCapacity) * 100))}%` }}
                                    />
                                </div>
                                <p className="text-xs text-muted-foreground">Refills every hour</p>
                            </div>

                            {/* Theme Switch */}
                            <div className="py-3 border-b border-border flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    {isDarkTheme ? <Moon className="h-4 w-4 text-primary" aria-hidden="true" /> : <Sun className="h-4 w-4" aria-hidden="true" />}
                                    <span className="text-xs font-medium text-foreground">Dark Mode</span>
                                </div>
                                <Switch checked={isDarkTheme} onCheckedChange={onToggleTheme} aria-label="Toggle dark mode theme" />
                            </div>

                            {/* Legal & Policy Links */}
                            <div className="py-2.5 border-b border-border flex items-center justify-between text-xs text-muted-foreground px-0.5">
                                <Link href="/privacy" className="hover:text-primary transition-colors">
                                    Privacy Policy
                                </Link>
                                <span aria-hidden="true">•</span>
                                <Link href="/terms" className="hover:text-primary transition-colors">
                                    Terms of Service
                                </Link>
                            </div>

                            {/* Sign Out */}
                            <div className="pt-3">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => {
                                        setPopoverOpen(false);
                                        onLogout();
                                    }}
                                    className="w-full justify-center gap-2 text-xs font-semibold text-destructive border-destructive/40 hover:bg-destructive/10 hover:text-destructive rounded-xl h-9"
                                >
                                    <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
                                    <span>Sign Out</span>
                                </Button>
                            </div>
                        </PopoverContent>
                    </Popover>
                ) : (
                    <Button size="sm" variant="default" onClick={onOpenSignIn} className="text-xs font-bold gap-1.5 rounded-xl h-9">
                        <LogIn className="h-3.5 w-3.5" aria-hidden="true" />
                        <span>Sign In</span>
                    </Button>
                )}
            </div>
        </header>
    );
}

