import type { Metadata, Viewport } from 'next';
import { Instrument_Sans, Outfit, JetBrains_Mono } from 'next/font/google';
import '../styles/globals.css';

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
    themeColor: '#004ea1',
    width: 'device-width',
    initialScale: 1
};

export const metadata: Metadata = {
    title: 'NexusAgent — Autonomous Systems Analyst',
    description:
        'Enterprise-grade autonomous systems analyst and architecture intelligence engine powered by LangGraph, LlamaIndex, Neon PostgreSQL 18, and MCP v2.',
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
                color: '#004ea1'
            }
        ]
    },
    manifest: '/site.webmanifest'
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en" suppressHydrationWarning className={`${instrumentSans.variable} ${outfit.variable} ${jetbrainsMono.variable}`}>
            <head>
                <script
                    dangerouslySetInnerHTML={{
                        __html: `(function(){try{var t=localStorage.getItem('nexusagent_theme');if(t==='dark'){document.documentElement.classList.add('dark')}else{document.documentElement.classList.remove('dark')}}catch(e){}})();`
                    }}
                />
            </head>
            <body suppressHydrationWarning className="bg-background text-foreground antialiased font-sans min-h-screen">
                <a href="#main-canvas" className="skip-link">
                    Skip to chat
                </a>
                {children}
            </body>
        </html>
    );
}
