import { describe, expect, it } from 'vite-plus/test';
import { MCP_URL, buildClientConfig } from './mcp-client-config';

describe('mcp-client-config', () => {
    it('exports an MCP_URL ending with /mcp', () => {
        expect(MCP_URL).toMatch(/\/mcp$/);
    });

    it('builds valid JSON config with http transport', () => {
        const config = JSON.parse(buildClientConfig());
        expect(config.mcpServers.airankagent).toEqual({
            type: 'http',
            url: MCP_URL
        });
    });

    it('never writes secrets or database settings into the client file', () => {
        expect(buildClientConfig()).not.toMatch(/GEMINI|NEON|DATABASE|API_KEY|env/i);
    });
});
