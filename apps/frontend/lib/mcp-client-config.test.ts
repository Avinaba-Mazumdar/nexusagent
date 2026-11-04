import { describe, expect, it } from 'vite-plus/test';
import { CLIENT_SERVER_NAME, REPO_PATH_PLACEHOLDER, buildClientConfig } from './mcp-client-config';

describe('buildClientConfig', () => {
    it('starts the stdio launcher through uv in the backend directory', () => {
        const config = JSON.parse(buildClientConfig('C:/work/nexus-agent'));
        const server = config.mcpServers[CLIENT_SERVER_NAME];

        expect(server.command).toBe('uv');
        expect(server.args).toEqual(['run', '--directory', 'C:/work/nexus-agent/apps/backend', 'python', '-m', 'app.mcp.server']);
    });

    it('defaults to the placeholder path so the user has to fill it in', () => {
        const config = JSON.parse(buildClientConfig());

        expect(config.mcpServers[CLIENT_SERVER_NAME].args).toContain(`${REPO_PATH_PLACEHOLDER}/apps/backend`);
    });

    it('ignores trailing slashes on the checkout path', () => {
        const config = JSON.parse(buildClientConfig('/home/dev/nexus-agent//'));

        expect(config.mcpServers[CLIENT_SERVER_NAME].args[2]).toBe('/home/dev/nexus-agent/apps/backend');
    });

    it('never writes secrets or database settings into the client file', () => {
        expect(buildClientConfig()).not.toMatch(/GEMINI|NEON|DATABASE|API_KEY|env/i);
    });
});
