import { describe, expect, it } from 'vite-plus/test';
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { MCP_DEFAULT_QUERY, STARTER_PROMPTS } from './starter-prompts';

const KB_DIR = path.resolve(import.meta.dirname, '../../../knowledge_base/benchmarks');
const kbText = readdirSync(KB_DIR)
    .map((f) => readFileSync(path.join(KB_DIR, f), 'utf8'))
    .join('\n')
    .toLowerCase();

// Benchmark prompts and default MCP query must reference entities in the knowledge base.
const BENCHMARK_TERMS: Record<string, string[]> = {
    [STARTER_PROMPTS[0]]: ['artificial analysis', 'intelligence index'],
    [STARTER_PROMPTS[1]]: ['gpt', 'claude', 'cursorbench'],
    [STARTER_PROMPTS[2]]: ['openrouter'],
    [MCP_DEFAULT_QUERY]: ['cursorbench']
};

describe('starter prompts', () => {
    it('has 4 starter prompts', () => {
        expect(STARTER_PROMPTS).toHaveLength(4);
    });

    it.each(Object.entries(BENCHMARK_TERMS))('"%s" only references things in the knowledge base', (_prompt, terms) => {
        for (const term of terms) expect(kbText).toContain(term);
    });
});
