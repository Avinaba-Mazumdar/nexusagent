import { afterEach, describe, expect, it } from 'vite-plus/test';
import { applyTheme, nextTheme, parseTheme, readThemeFromDocument, THEME_BOOT_SCRIPT, THEME_META_COLORS } from './theme';

const root = document.documentElement;

afterEach(() => {
    root.classList.remove('dark', 'black');
    document.querySelector('meta[name="theme-color"]')?.remove();
    localStorage.clear();
});

describe('theme', () => {
    it('parses stored values, falling back to light', () => {
        expect(parseTheme('dark')).toBe('dark');
        expect(parseTheme('black')).toBe('black');
        expect(parseTheme('light')).toBe('light');
        expect(parseTheme('amoled')).toBe('light');
        expect(parseTheme(null)).toBe('light');
    });

    it('cycles light -> dark -> black -> light', () => {
        expect(nextTheme('light')).toBe('dark');
        expect(nextTheme('dark')).toBe('black');
        expect(nextTheme('black')).toBe('light');
    });

    it('applies stacked classes and the browser theme colour', () => {
        const meta = document.createElement('meta');
        meta.name = 'theme-color';
        document.head.appendChild(meta);

        applyTheme('black');
        expect(root.classList.contains('dark')).toBe(true);
        expect(root.classList.contains('black')).toBe(true);
        expect(readThemeFromDocument()).toBe('black');
        expect(meta.content).toBe(THEME_META_COLORS.black);

        applyTheme('dark');
        expect(root.classList.contains('black')).toBe(false);
        expect(readThemeFromDocument()).toBe('dark');
        expect(meta.content).toBe(THEME_META_COLORS.dark);

        applyTheme('light');
        expect(root.classList.contains('dark')).toBe(false);
        expect(readThemeFromDocument()).toBe('light');
    });

    it('boot script restores the stored theme before paint', () => {
        const boot = new Function(THEME_BOOT_SCRIPT);

        localStorage.setItem('nexusagent_theme', 'black');
        boot();
        expect(readThemeFromDocument()).toBe('black');

        localStorage.setItem('nexusagent_theme', 'dark');
        boot();
        expect(readThemeFromDocument()).toBe('dark');

        localStorage.setItem('nexusagent_theme', 'bogus');
        boot();
        expect(readThemeFromDocument()).toBe('light');
    });
});
