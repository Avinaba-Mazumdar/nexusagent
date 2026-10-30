import { defineConfig } from 'vite-plus';

export default defineConfig({
    fmt: {
        ignorePatterns: [
            'node_modules',
            '.pnpm-store',
            '.next',
            'dist',
            'build',
            'out',
            '.venv',
            'next-env.d.ts',
            'pnpm-lock.yaml',
            'uv.lock',
            'apps/backend/pyproject.toml'
        ],
        printWidth: 160,
        tabWidth: 4,
        useTabs: false,
        semi: true,
        singleQuote: true,
        trailingComma: 'none',
        bracketSpacing: true,
        bracketSameLine: false,
        arrowParens: 'always',
        endOfLine: 'lf',
        quoteProps: 'as-needed',
        proseWrap: 'preserve',
        htmlWhitespaceSensitivity: 'css',
        embeddedLanguageFormatting: 'auto'
    },
    lint: {
        options: {
            typeAware: true,
            typeCheck: true
        }
    }
});
