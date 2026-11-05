export const MCP_URL = `${(process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '')}/mcp`;

export function buildClientConfig(): string {
    return JSON.stringify(
        {
            mcpServers: {
                airankagent: {
                    type: 'http',
                    url: MCP_URL
                }
            }
        },
        null,
        2
    );
}
