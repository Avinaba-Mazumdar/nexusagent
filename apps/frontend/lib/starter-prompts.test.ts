import { describe, expect, it } from 'vite-plus/test';
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { MCP_DEFAULT_QUERY, STARTER_PROMPTS } from './starter-prompts';

const KB_DIR = path.resolve(import.meta.dirname, '../../../knowledge_base/benchmarks');
const kbText = readdirSync(KB_DIR)
    .map((f) => readFileSync(path.join(KB_DIR, f), 'utf8'))
    .join('\n')
    .toLowerCase();

// Model and source names each prompt relies on must exist in the knowledge base.
const REQUIRED_TERMS: Record<string, string[]> = {
    [STARTER_PROMPTS[0]]: ['claude opus 5.5', 'gpt-6 astra', 'intelligence index'],
    [STARTER_PROMPTS[1]]: ['openrouter'],
    [STARTER_PROMPTS[2]]: ['benchlm'],
    [STARTER_PROMPTS[3]]: ['gemini 3.8 flash', 'deepseek v4.1 flash', 'cursorbench'],
    [MCP_DEFAULT_QUERY]: ['opus 5.5', 'cursorbench 4.0']
};

describe('starter prompts', () => {
    it.each(Object.entries(REQUIRED_TERMS))('"%s" only references things in the knowledge base', (_prompt, terms) => {
        for (const term of terms) expect(kbText).toContain(term);
    });
});
