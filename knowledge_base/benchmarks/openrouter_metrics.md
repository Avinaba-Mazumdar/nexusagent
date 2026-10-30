# OpenRouter Model Pricing & Context Index

Source URL: https://openrouter.ai/api/v1/models (public model catalogue API)
Retrieved: 2026-10-30
Category: Per-token list prices, context windows, release dates, free variants
Provenance: generated directly from the API response (456 models listed). Prices are OpenRouter's catalogue list prices converted from USD per token to USD per 1M tokens; nothing was estimated. Prices change often; re-check the source before relying on a figure.

---

## 1. Latest Text Models per Provider (newest 5 each, batch variants excluded)

| Provider    | Model                        | OpenRouter ID                           | Context (tokens) | Input $/1M | Output $/1M | Listed on  |
| :---------- | :--------------------------- | :-------------------------------------- | :--------------- | :--------- | :---------- | :--------- |
| OpenAI      | GPT-6.1 Terra Pro            | `openai/gpt-6.1-terra-pro`              | 1,050,000        | $1.00      | $5.00       | 2026-10-26 |
| OpenAI      | GPT-6.1 Terra                | `openai/gpt-6.1-terra`                  | 1,050,000        | $1.00      | $5.00       | 2026-10-26 |
| OpenAI      | GPT-6.1 Sol Pro              | `openai/gpt-6.1-sol-pro`                | 1,050,000        | $2.00      | $10.00      | 2026-09-29 |
| OpenAI      | GPT-6.1 Sol                  | `openai/gpt-6.1-sol`                    | 1,050,000        | $2.00      | $10.00      | 2026-09-29 |
| OpenAI      | GPT-6 Luna Pro               | `openai/gpt-6-luna-pro`                 | 1,050,000        | $0.10      | $0.50       | 2026-09-22 |
| Anthropic   | Claude Haiku 5.5             | `anthropic/claude-haiku-5.5`            | 1,000,000        | $0.10      | $0.50       | 2026-10-07 |
| Anthropic   | Claude Sonnet 5.5            | `anthropic/claude-sonnet-5.5`           | 1,000,000        | $2.00      | $10.00      | 2026-09-28 |
| Anthropic   | Claude Opus 5.5              | `anthropic/claude-opus-5.5`             | 1,000,000        | $4.00      | $20.00      | 2026-09-22 |
| Anthropic   | Claude Fable 5.1             | `anthropic/claude-fable-5.1`            | 1,000,000        | $10.00     | $50.00      | 2026-09-01 |
| Anthropic   | Claude Opus 5                | `anthropic/claude-opus-5`               | 1,000,000        | $5.00      | $25.00      | 2026-07-24 |
| Google      | Gemini 4 Argon               | `google/gemini-4-argon`                 | 1,048,576        | $2.00      | $10.00      | 2026-10-13 |
| Google      | Gemini 3.8 Flash             | `google/gemini-3.8-flash`               | 1,048,576        | $0.825     | $4.125      | 2026-09-02 |
| Google      | Gemini 3.7 Flash             | `google/gemini-3.7-flash`               | 1,048,576        | $0.75      | $3.75       | 2026-08-13 |
| Google      | Gemini 3.6 Flash             | `google/gemini-3.6-flash`               | 1,048,576        | $0.75      | $3.75       | 2026-07-21 |
| Google      | Gemini 3.5 Flash Lite        | `google/gemini-3.5-flash-lite`          | 1,048,576        | $0.30      | $2.50       | 2026-07-21 |
| xAI         | Grok 4.7                     | `x-ai/grok-4.7`                         | 500,000          | $2.00      | $6.00       | 2026-09-21 |
| xAI         | Grok 4.6                     | `x-ai/grok-4.6`                         | 500,000          | $2.00      | $6.00       | 2026-08-12 |
| xAI         | Grok 4.5                     | `x-ai/grok-4.5`                         | 500,000          | $2.00      | $6.00       | 2026-07-08 |
| xAI         | Grok Build 0.1               | `x-ai/grok-build-0.1`                   | 256,000          | $1.00      | $2.00       | 2026-05-20 |
| xAI         | Grok 4.3                     | `x-ai/grok-4.3`                         | 1,000,000        | $1.25      | $2.50       | 2026-04-30 |
| Meta        | Muse Spark Open              | `meta/muse-spark-open`                  | 1,048,576        | $1.25      | $4.25       | 2026-10-15 |
| Meta        | Muse Wonder                  | `meta/muse-wonder`                      | 1,048,576        | $4.00      | $20.00      | 2026-10-12 |
| Meta        | Muse Spark 1.3 Contributor   | `meta/muse-spark-1.3-contributor`       | 1,048,576        | $0.10      | $0.20       | 2026-09-02 |
| Meta        | Muse Spark 1.3               | `meta/muse-spark-1.3`                   | 1,048,576        | $1.25      | $4.25       | 2026-09-02 |
| Meta        | Muse Spark 1.2 Contributor   | `meta/muse-spark-1.2-contributor`       | 1,048,576        | $0.10      | $0.20       | 2026-08-21 |
| Moonshot AI | Kimi K3.1 Pro                | `moonshotai/kimi-k3.1-pro`              | 1,048,576        | $2.00      | $10.00      | 2026-10-23 |
| Moonshot AI | Kimi K3                      | `moonshotai/kimi-k3`                    | 1,048,576        | $0.192     | $15.00      | 2026-07-16 |
| Moonshot AI | Kimi K2.7 Code               | `moonshotai/kimi-k2.7-code`             | 262,144          | $0.56      | $3.10       | 2026-06-12 |
| Moonshot AI | Kimi K2.6                    | `moonshotai/kimi-k2.6`                  | 262,144          | $0.65      | $3.41       | 2026-04-20 |
| Moonshot AI | Kimi K2.5                    | `moonshotai/kimi-k2.5`                  | 262,144          | $0.50      | $2.50       | 2026-01-27 |
| DeepSeek    | DeepSeek V4.1 Flash 1017     | `deepseek/deepseek-v4.1-flash-1017`     | 1,048,576        | $0.30      | $1.20       | 2026-10-17 |
| DeepSeek    | DeepSeek V4.1 Flash          | `deepseek/deepseek-v4.1-flash`          | 1,048,576        | $0.045     | $0.50       | 2026-09-10 |
| DeepSeek    | DeepSeek V4 Flash Vision Exp | `deepseek/deepseek-v4-flash-vision-exp` | 1,048,576        | $0.216     | $0.647      | 2026-08-21 |
| DeepSeek    | DeepSeek V4 Pro 0813         | `deepseek/deepseek-v4-pro-0813`         | 1,048,576        | $1.32      | $3.96       | 2026-08-12 |
| DeepSeek    | DeepSeek V4 Flash 0731       | `deepseek/deepseek-v4-flash-0731`       | 1,048,576        | $0.119     | $0.238      | 2026-07-31 |
| Qwen        | Qwen3.8 Max Prime            | `qwen/qwen3.8-max-prime`                | 1,000,000        | $4.00      | $12.00      | 2026-09-23 |
| Qwen        | Qwen3.8 Omni Flash           | `qwen/qwen3.8-omni-flash`               | 1,000,000        | $0.15      | $0.47       | 2026-09-21 |
| Qwen        | Qwen3.8 Max (0902)           | `qwen/qwen3.8-max-0902`                 | 1,000,000        | $2.00      | $6.00       | 2026-09-03 |
| Qwen        | Qwen3.8 Flash                | `qwen/qwen3.8-flash`                    | 1,000,000        | $0.15      | $0.47       | 2026-08-26 |
| Qwen        | Qwen3.8 27B                  | `qwen/qwen3.8-27b`                      | 1,000,000        | $0.15      | $1.875      | 2026-08-14 |
| Z.ai        | GLM 5.3 Prime                | `z-ai/glm-5.3-prime`                    | 1,000,000        | $2.80      | $8.80       | 2026-09-23 |
| Z.ai        | GLM 5.3 FlashX               | `z-ai/glm-5.3-flashx`                   | 1,048,576        | $0.37      | $1.25       | 2026-09-18 |
| Z.ai        | GLM 5.3 Flash                | `z-ai/glm-5.3-flash`                    | 1,048,576        | $0.15      | $0.50       | 2026-08-26 |
| Z.ai        | GLM 5.3                      | `z-ai/glm-5.3`                          | 1,048,576        | $0.08      | $3.60       | 2026-08-18 |
| Z.ai        | GLM 5.2                      | `z-ai/glm-5.2`                          | 1,048,576        | $0.006     | $7.00       | 2026-06-16 |
| Mistral     | Mistral Large 4              | `mistralai/mistral-large-4-0`           | 1,048,576        | $0.70      | $2.10       | 2026-10-06 |
| Mistral     | Mistral Medium 3.5           | `mistralai/mistral-medium-3-5`          | 262,144          | $1.50      | $7.50       | 2026-04-30 |
| Mistral     | Mistral Small 4              | `mistralai/mistral-small-2603`          | 262,144          | $0.15      | $0.60       | 2026-03-16 |
| Mistral     | Devstral 2 2512              | `mistralai/devstral-2512`               | 262,144          | $0.40      | $2.00       | 2025-12-09 |
| Mistral     | Ministral 3 14B 2512         | `mistralai/ministral-14b-2512`          | 262,144          | $0.20      | $0.20       | 2025-12-02 |

## 2. Lowest Combined Price Among the Models Above (input + output per 1M tokens)

| Rank | Model                             | OpenRouter ID                     | Input $/1M | Output $/1M | Input + Output $/1M |
| :--- | :-------------------------------- | :-------------------------------- | :--------- | :---------- | :------------------ |
| 1    | Muse Spark 1.3 Contributor (Meta) | `meta/muse-spark-1.3-contributor` | $0.10      | $0.20       | $0.30               |
| 2    | Muse Spark 1.2 Contributor (Meta) | `meta/muse-spark-1.2-contributor` | $0.10      | $0.20       | $0.30               |
| 3    | DeepSeek V4 Flash 0731 (DeepSeek) | `deepseek/deepseek-v4-flash-0731` | $0.119     | $0.238      | $0.357              |
| 4    | Ministral 3 14B 2512 (Mistral)    | `mistralai/ministral-14b-2512`    | $0.20      | $0.20       | $0.40               |
| 5    | DeepSeek V4.1 Flash (DeepSeek)    | `deepseek/deepseek-v4.1-flash`    | $0.045     | $0.50       | $0.545              |
| 6    | GPT-6 Luna Pro (OpenAI)           | `openai/gpt-6-luna-pro`           | $0.10      | $0.50       | $0.60               |
| 7    | Claude Haiku 5.5 (Anthropic)      | `anthropic/claude-haiku-5.5`      | $0.10      | $0.50       | $0.60               |
| 8    | Qwen3.8 Omni Flash (Qwen)         | `qwen/qwen3.8-omni-flash`         | $0.15      | $0.47       | $0.62               |
| 9    | Qwen3.8 Flash (Qwen)              | `qwen/qwen3.8-flash`              | $0.15      | $0.47       | $0.62               |
| 10   | GLM 5.3 Flash (Z.ai)              | `z-ai/glm-5.3-flash`              | $0.15      | $0.50       | $0.65               |

## 3. Free Variants (`:free` IDs, text output)

| Model                                      | OpenRouter ID                                        | Context (tokens) |
| :----------------------------------------- | :--------------------------------------------------- | :--------------- |
| Cohere: North Mini Code (free)             | `cohere/north-mini-code:free`                        | 256,000          |
| Dots Studio: Dots3-Note Preview (free)     | `dots-studio/dots-3-note-preview:free`               | 512,000          |
| Google: Gemma 4 26B A4B (free)             | `google/gemma-4-26b-a4b-it:free`                     | 262,144          |
| Google: Gemma 4 31B (free)                 | `google/gemma-4-31b-it:free`                         | 262,144          |
| LiquidAI: LFM2.5-2.6B (free)               | `liquid/lfm-2.5-2.6b:free`                           | 65,536           |
| NVIDIA: Nemotron 3 Nano Omni (free)        | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | 256,000          |
| NVIDIA: Nemotron 3 Ultra (free)            | `nvidia/nemotron-3-ultra-550b-a55b:free`             | 1,000,000        |
| NVIDIA: Nemotron 3.5 Content Safety (free) | `nvidia/nemotron-3.5-content-safety:free`            | 128,000          |
| NVIDIA: Nemotron 3.5 Lightning (free)      | `nvidia/nemotron-3.5-lightning:free`                 | 1,000,000        |
| NVIDIA: Nemotron 3.5 Super VL (free)       | `nvidia/nemotron-3.5-super-vl:free`                  | 1,000,000        |
| Poolside: Laguna S 2.1 (free)              | `poolside/laguna-s-2.1:free`                         | 262,144          |
| Poolside: Laguna XS 2.1 (free)             | `poolside/laguna-xs-2.1:free`                        | 262,144          |
| Recursive: Flint (free)                    | `recursive/flint-v1.0:free`                          | 262,144          |
| Thinking Machines: Inkling Small (free)    | `thinkingmachines/inkling-small:free`                | 1,048,576        |
| Thinking Machines: Inkling (free)          | `thinkingmachines/inkling:free`                      | 1,048,576        |
| XingChen: Xing4.0 29B A4B (free)           | `xingchen-agi/xing4.0-29b-a4b:free`                  | 262,144          |

## 4. Top Models on the OpenRouter Rankings Page

Source URL: https://openrouter.ai/rankings
Retrieved: 2026-10-30 (page states: usage data through Oct 29, 2026)

The rankings page shows a "Top Models" list ordered by the Artificial Analysis Intelligence Index (not by token usage; the usage leaderboard is rendered client-side and was not captured). The first ten entries:

| Rank | Model (effort shown on page) | Creator     | AA Intelligence Index |
| :--- | :--------------------------- | :---------- | :-------------------- |
| 1    | Claude Opus 5.5 (Max)        | Anthropic   | 58.4                  |
| 2    | GPT-6 Astra (Max)            | OpenAI      | 56.9                  |
| 3    | GPT-6.1 Sol (Max)            | OpenAI      | 54.5                  |
| 4    | Claude Sonnet 5.5 (Max)      | Anthropic   | 54.2                  |
| 5    | Qwen3.8 Max                  | Qwen        | 53.4                  |
| 6    | GPT-6.1 Terra (Max)          | OpenAI      | 51.0                  |
| 7    | Gemini 4 Argon (High)        | Google      | 50.4                  |
| 8    | Claude Fable 5.1 (Xhigh)     | Anthropic   | 49.7                  |
| 9    | Kimi K3.1 Pro                | Moonshot AI | 46.0                  |
| 10   | Muse Spark 1.3 (Max)         | Meta        | 36.4                  |
