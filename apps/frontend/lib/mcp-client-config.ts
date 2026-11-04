/** Stands in for the absolute path of the user's checkout; the user replaces it before pasting. */
export const REPO_PATH_PLACEHOLDER = '<ABSOLUTE_PATH_TO_NEXUS_AGENT>';

/** The name the server appears under in Claude Desktop and Cursor. */
export const CLIENT_SERVER_NAME = 'nexusagent';

/**
 * The `mcpServers` document that Claude Desktop and Cursor both read. It starts the stdio launcher
 * (`python -m app.mcp.server`) through uv, inside apps/backend. That server reads its own
 * `.env.local`, so no API key or database URL goes into the client's config file.
 */
export function buildClientConfig(repoPath: string = REPO_PATH_PLACEHOLDER): string {
    const backendDir = `${repoPath.replace(/[\\/]+$/, '')}/apps/backend`;
    return JSON.stringify(
        {
            mcpServers: {
                [CLIENT_SERVER_NAME]: {
                    command: 'uv',
                    args: ['run', '--directory', backendDir, 'python', '-m', 'app.mcp.server']
                }
            }
        },
        null,
        2
    );
}
