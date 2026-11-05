import type { Metadata, Viewport } from 'next';
import { headers } from 'next/headers';
import { Instrument_Sans, Outfit, JetBrains_Mono } from 'next/font/google';
import '../styles/globals.css';
import { THEME_BOOT_SCRIPT } from '@/lib/theme';

const instrumentSans = Instrument_Sans({
    subsets: ['latin'],
    variable: '--font-sans',
    display: 'swap'
});

const outfit = Outfit({
    subsets: ['latin'],
    variable: '--font-heading',
    display: 'swap'
});

const jetbrainsMono = JetBrains_Mono({
    subsets: ['latin'],
    variable: '--font-mono',
    display: 'swap'
});

export const viewport: Viewport = {
    themeColor: '#2C357D',
    width: 'device-width',
    initialScale: 1
};

export const metadata: Metadata = {
    title: 'NexusAgent: an open-source LLM benchmark assistant',
    description: 'An open-source LLM benchmark assistant powered by LangGraph, Neon PostgreSQL 18, and the Model Context Protocol.',
    icons: {
        icon: [
            { url: '/favicon.ico', sizes: 'any' },
            { url: '/icon.svg', type: 'image/svg+xml' },
            { url: '/favicon-32x32.png', type: 'image/png', sizes: '32x32' },
            { url: '/favicon-16x16.png', type: 'image/png', sizes: '16x16' }
        ],
        apple: [{ url: '/apple-touch-icon.png', sizes: '180x180', type: 'image/png' }],
        other: [
            {
                rel: 'mask-icon',
                url: '/icon.svg',
                color: '#2C357D'
            }
        ]
    },
    manifest: '/site.webmanifest'
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
    // Per-request CSP nonce set by proxy.ts; the inline theme script below needs it to run.
    const nonce = (await headers()).get('x-nonce') ?? undefined;
    return (
        <html lang="en" suppressHydrationWarning className={`${instrumentSans.variable} ${outfit.variable} ${jetbrainsMono.variable}`}>
            <head>
                <script
                    nonce={nonce}
                    suppressHydrationWarning
                    dangerouslySetInnerHTML={{
                        __html: THEME_BOOT_SCRIPT
                    }}
                />
            </head>
            <body suppressHydrationWarning className="bg-background text-foreground antialiased font-sans min-h-dvh">
                <a href="#main-canvas" className="skip-link">
                    Skip to chat
                </a>
                {children}
            </body>
        </html>
    );
}
