/** Questions the bundled knowledge base (knowledge_base/benchmarks/*.md) can actually answer. */
export const STARTER_PROMPTS = [
    'Compare Claude Opus 5.5 and GPT-6 Astra on the Artificial Analysis Intelligence Index and cost per task',
    'Which models are cheapest per 1M tokens on OpenRouter?',
    'Summarize the BenchLM overall rankings for the top models',
    'How do Gemini 3.8 Flash and DeepSeek V4.1 Flash compare on CursorBench score and cost?'
] as const;

/** Default query for the MCP inspector's hybrid_rag_search tool. */
export const MCP_DEFAULT_QUERY = 'Opus 5.5 CursorBench 4.0 score';
