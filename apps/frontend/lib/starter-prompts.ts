/** Questions the bundled knowledge base (knowledge_base/benchmarks/*.md) can actually answer. */
export const STARTER_PROMPTS = [
    'Compare Claude Opus 5 and ChatGPT 6 Astra on the Artificial Analysis quality index and price',
    'Which models are cheapest per 1M tokens on OpenRouter?',
    'Summarize the BenchLM reasoning leaderboard for the top models',
    'How do Gemini 3.8 Flash and DeepSeek V4.1 Flash compare on speed and cost?'
] as const;

/** Default query for the MCP inspector's hybrid_rag_search tool. */
export const MCP_DEFAULT_QUERY = 'Claude Opus 5 SWE-Bench Verified';
