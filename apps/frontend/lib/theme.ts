// Three colour themes. Classes on <html>: light = none, dark = `dark`, black = `dark black`.
// Black stacks on dark so every `dark:` utility still applies; it only overrides surfaces.

export type ThemeName = 'light' | 'dark' | 'black';

export const THEME_STORAGE_KEY = 'nexusagent_theme';

export const THEMES: readonly { id: ThemeName; label: string }[] = [
    { id: 'light', label: 'Light' },
    { id: 'dark', label: 'Dark' },
    { id: 'black', label: 'Black' }
];

// Browser chrome colour (mobile address bar) per theme.
export const THEME_META_COLORS: Record<ThemeName, string> = {
    light: '#2C357D',
    dark: '#0C0E1A',
    black: '#000000'
};

export function parseTheme(value: unknown): ThemeName {
    return value === 'dark' || value === 'black' ? value : 'light';
}

export function nextTheme(theme: ThemeName): ThemeName {
    const i = THEMES.findIndex((t) => t.id === theme);
    return THEMES[(i + 1) % THEMES.length].id;
}

export function themeLabel(theme: ThemeName): string {
    return THEMES.find((t) => t.id === theme)?.label ?? 'Light';
}

export function readThemeFromDocument(root: HTMLElement = document.documentElement): ThemeName {
    if (root.classList.contains('black')) return 'black';
    return root.classList.contains('dark') ? 'dark' : 'light';
}

export function applyTheme(theme: ThemeName, root: HTMLElement = document.documentElement): void {
    root.classList.toggle('dark', theme !== 'light');
    root.classList.toggle('black', theme === 'black');
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', THEME_META_COLORS[theme]);
}

// Same logic as applyTheme, inlined into <head> by layout.tsx so the theme is set before first paint.
export const THEME_BOOT_SCRIPT = `(function(){try{var t=localStorage.getItem('${THEME_STORAGE_KEY}');var c=document.documentElement.classList;c.toggle('dark',t==='dark'||t==='black');c.toggle('black',t==='black')}catch(e){}})();`;
