# OpenRouter Model Throughput, Latency & Pricing Index

Source: openrouter.ai/rankings
Category: Provider Pricing, TTFT Latency, Tokens/Sec Throughput, Reasoning Overheads
Last Updated: September 2026
Provenance: curated snapshot kept in this repository. Figures are not scraped live and have not been independently re-verified against the named source; the retrieval date was not recorded. Treat them as illustrative until each table is checked against its source.
Telemetry Scope: Production edge clusters across global provider routes

> [!NOTE]
> Values marked with `-` indicate that the provider does not levy a reasoning surcharge or that the model operates at a single fixed inference latency without variable reasoning effort tiers.

---

## 1. Provider Pricing, Context Windows & Throughput Matrix

| Model Identifier               | Context Window | Prompt ($/1M) | Completion ($/1M) | Reasoning Surcharge  | Max Output | Tokens / Sec |
| :----------------------------- | :------------- | :------------ | :---------------- | :------------------- | :--------- | :----------- |
| `openai/chatgpt-6-astra`       | 2,000,000      | $4.00         | $16.00            | +$16.00/1M reasoning | 64,000     | 88 tok/s     |
| `openai/chatgpt-5.6-sol`       | 1,000,000      | $2.00         | $8.00             | +$8.00/1M reasoning  | 32,000     | 96 tok/s     |
| `openai/chatgpt-5.6-terra`     | 500,000        | $0.80         | $3.20             | +$3.20/1M reasoning  | 16,000     | 115 tok/s    |
| `openai/chatgpt-5.6-luna`      | 256,000        | $0.25         | $1.00             | -                    | 8,192      | 145 tok/s    |
| `anthropic/claude-opus-5`      | 1,000,000      | $5.00         | $20.00            | +$20.00/1M reasoning | 64,000     | 78 tok/s     |
| `anthropic/claude-sonnet-5`    | 1,000,000      | $2.50         | $10.00            | +$10.00/1M reasoning | 64,000     | 102 tok/s    |
| `anthropic/claude-fable-5.1`   | 500,000        | $1.20         | $4.80             | +$4.80/1M reasoning  | 32,000     | 120 tok/s    |
| `anthropic/claude-fable-5`     | 500,000        | $0.90         | $3.60             | +$3.60/1M reasoning  | 32,000     | 128 tok/s    |
| `google/gemini-3.1-pro`        | 10,000,000     | $1.50         | $6.00             | -                    | 64,000     | 95 tok/s     |
| `google/gemini-3.8-flash`      | 4,000,000      | $0.15         | $0.60             | -                    | 64,000     | 165 tok/s    |
| `google/gemini-3.7-flash`      | 2,000,000      | $0.10         | $0.40             | -                    | 32,000     | 175 tok/s    |
| `google/gemini-3.6-flash`      | 1,000,000      | $0.06         | $0.25             | -                    | 16,000     | 190 tok/s    |
| `google/gemma-4`               | 256,000        | $0.05         | $0.20             | -                    | 16,000     | 195 tok/s    |
| `deepseek/deepseek-v4.0-pro`   | 1,000,000      | $0.35         | $1.40             | -                    | 64,000     | 110 tok/s    |
| `deepseek/deepseek-v4.1-flash` | 512,000        | $0.08         | $0.32             | -                    | 32,000     | 160 tok/s    |
| `deepseek/deepseek-v4.0-flash` | 256,000        | $0.05         | $0.20             | -                    | 16,000     | 180 tok/s    |
| `xai/grok-4.6`                 | 2,000,000      | $2.80         | $11.20            | -                    | 64,000     | 92 tok/s     |
| `xai/grok-4.5`                 | 1,000,000      | $1.40         | $5.60             | -                    | 32,000     | 110 tok/s    |
| `moonshot/kimi-k3`             | 5,000,000      | $0.40         | $1.60             | -                    | 32,000     | 125 tok/s    |
| `zhipu/glm-5.3`                | 1,000,000      | $0.30         | $1.20             | -                    | 32,000     | 130 tok/s    |
| `zhipu/glm-5.3-flash`          | 512,000        | $0.07         | $0.28             | -                    | 16,000     | 185 tok/s    |
| `qwen/qwen-3.8-max`            | 2,000,000      | $1.80         | $7.20             | -                    | 64,000     | 105 tok/s    |
| `qwen/qwen-3.8`                | 1,000,000      | $0.20         | $0.80             | -                    | 32,000     | 138 tok/s    |
| `qwen/qwen-3.7-coder`          | 1,000,000      | $0.22         | $0.88             | -                    | 32,000     | 145 tok/s    |
| `muse/muse-1.3-spark`          | 512,000        | $0.09         | $0.36             | -                    | 32,000     | 170 tok/s    |
| `muse/muse-1.2-spark`          | 256,000        | $0.04         | $0.16             | -                    | 16,000     | 210 tok/s    |
| `openai/chatgpt-6-sol`         | 1,050,000      | $2.00         | $10.00            | -                    | 128,000    | -            |
| `openai/chatgpt-6-luna`        | 1,050,000      | $0.10         | $0.50             | -                    | 128,000    | -            |
| `anthropic/claude-opus-5.5`    | 1,000,000      | $4.00         | $20.00            | -                    | 128,000    | -            |
| `anthropic/claude-sonnet-5.5`  | 1,000,000      | $2.00         | $10.00            | -                    | 128,000    | -            |
| `google/gemini-3.5-flash`      | 1,048,576      | $1.50         | $9.00             | +$9.00/1M reasoning  | 65,536     | -            |
| `xai/grok-4.7`                 | 500,000        | $2.00         | $6.00             | -                    | 450,000    | -            |
| `mimo/mimo-v2.6-pro`           | 1,050,000      | $0.43         | $0.87             | -                    | 131,072    | -            |
| `mimo/mimo-v2.6-flash`         | 1,048,576      | $0.14         | $0.28             | -                    | 131,072    | -            |
| `minimax/minimax-m3`           | 1,048,576      | $0.30         | $1.20             | -                    | 512,000    | -            |
| `typesafe/jev-router`          | 1,000,000      | -             | -                 | -                    | -          | -            |
| `laya`                         | -              | -             | -                 | -                    | -          | -            |

---

## 2. Latency Benchmarks (TTFT ms) Across Reasoning Efforts

Time To First Token (TTFT in milliseconds) measured from client edge across Low, Medium, and High reasoning effort traces:

| Model Identifier               | TTFT (Low Effort) | TTFT (Medium Effort) | TTFT (High Effort) | Cold-Start Overhead |
| :----------------------------- | :---------------- | :------------------- | :----------------- | :------------------ |
| `openai/chatgpt-6-astra`       | 420ms             | 1,150ms              | 3,400ms            | +210ms              |
| `openai/chatgpt-5.6-sol`       | 380ms             | 920ms                | 2,600ms            | +180ms              |
| `openai/chatgpt-5.6-terra`     | 290ms             | 680ms                | 1,850ms            | +140ms              |
| `openai/chatgpt-5.6-luna`      | -                 | 190ms                | -                  | +95ms               |
| `anthropic/claude-opus-5`      | 480ms             | 1,320ms              | 3,850ms            | +240ms              |
| `anthropic/claude-sonnet-5`    | 340ms             | 840ms                | 2,350ms            | +160ms              |
| `anthropic/claude-fable-5.1`   | 260ms             | 610ms                | 1,650ms            | +120ms              |
| `anthropic/claude-fable-5`     | 240ms             | 560ms                | 1,500ms            | +110ms              |
| `google/gemini-3.1-pro`        | 360ms             | 890ms                | 2,450ms            | +150ms              |
| `google/gemini-3.8-flash`      | 180ms             | 420ms                | 1,100ms            | +85ms               |
| `google/gemini-3.7-flash`      | 160ms             | 380ms                | 980ms              | +75ms               |
| `google/gemini-3.6-flash`      | -                 | 140ms                | -                  | +65ms               |
| `google/gemma-4`               | -                 | 130ms                | -                  | +60ms               |
| `deepseek/deepseek-v4.0-pro`   | 280ms             | 710ms                | 1,980ms            | +130ms              |
| `deepseek/deepseek-v4.1-flash` | 190ms             | 440ms                | 1,150ms            | +90ms               |
| `deepseek/deepseek-v4.0-flash` | -                 | 150ms                | -                  | +70ms               |
| `xai/grok-4.6`                 | 390ms             | 960ms                | 2,750ms            | +190ms              |
| `xai/grok-4.5`                 | 310ms             | 740ms                | 2,050ms            | +150ms              |
| `moonshot/kimi-k3`             | 280ms             | 690ms                | 1,920ms            | +135ms              |
| `zhipu/glm-5.3`                | 270ms             | 660ms                | 1,840ms            | +130ms              |
| `zhipu/glm-5.3-flash`          | -                 | 150ms                | -                  | +70ms               |
| `qwen/qwen-3.8-max`            | 330ms             | 820ms                | 2,300ms            | +160ms              |
| `qwen/qwen-3.8`                | 250ms             | 600ms                | 1,680ms            | +120ms              |
| `qwen/qwen-3.7-coder`          | 210ms             | 520ms                | 1,450ms            | +105ms              |
| `muse/muse-1.3-spark`          | -                 | 170ms                | -                  | +80ms               |
| `muse/muse-1.2-spark`          | -                 | 120ms                | -                  | +55ms               |
| `openai/chatgpt-6-sol`         | -                 | -                    | -                  | -                   |
| `openai/chatgpt-6-luna`        | -                 | -                    | -                  | -                   |
| `anthropic/claude-opus-5.5`    | -                 | -                    | -                  | -                   |
| `anthropic/claude-sonnet-5.5`  | -                 | -                    | -                  | -                   |
| `google/gemini-3.5-flash`      | -                 | -                    | -                  | -                   |
| `xai/grok-4.7`                 | -                 | -                    | -                  | -                   |
| `mimo/mimo-v2.6-pro`           | -                 | -                    | -                  | -                   |
| `mimo/mimo-v2.6-flash`         | -                 | -                    | -                  | -                   |
| `minimax/minimax-m3`           | -                 | -                    | -                  | -                   |
| `typesafe/jev-router`          | -                 | -                    | -                  | -                   |
| `laya`                         | -                 | -                    | -                  | -                   |

---

## 3. Economic Routing Recommendations

1. **High-Throughput Interactive Tier**: Gemini 3.8 Flash and DeepSeek V4.1 Flash provide optimal performance under $0.60/1M tokens while sustaining sub-200ms TTFT.
2. **Deep Mathematical Proofs & Formal Verification**: ChatGPT 6 Astra and Claude Opus 5 dominate High-effort theorem reasoning, justifying their premium completion tiers for mission-critical tasks.
3. **Massive Context Retrieval**: Gemini 3.1 Pro (10M context window) and Kimi K3 (5M context window) enable entire repository ingests without chunk boundary fragmentation.
