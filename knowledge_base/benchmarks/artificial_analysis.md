# Artificial Analysis Independent Model Benchmark & Quality Index

Source: artificialanalysis.ai/leaderboard
Category: Quality Index, Speed/Cost Frontier, Output Throughput, TTFT Latency
Last Updated: September 2026
Provenance: curated snapshot kept in this repository. Figures are not scraped live and have not been independently re-verified against the named source; the retrieval date was not recorded. Treat them as illustrative until each table is checked against its source.
Methodology: Independent third-party evaluation across standardized prompt suites measuring output quality, operational cost, and empirical response latency.

> [!NOTE]
> Values marked with `-` indicate that the model is not tracked on Artificial Analysis's public API leaderboard or that the reasoning effort tier is not evaluated.

---

## 1. Executive Quality & Speed Matrix (All 26 Models at High / Standard Effort)

| Model Family  | Model Name          | Model Identifier               | Quality Index (0-100) | Blended Cost ($/1M) | Output Speed (tok/s) | Median TTFT (ms) | Value Score  |
| :------------ | :------------------ | :----------------------------- | :-------------------- | :------------------ | :------------------- | :--------------- | :----------- |
| **OpenAI**    | ChatGPT 6 Astra     | `openai/chatgpt-6-astra`       | 96.8                  | $13.00              | 88 tok/s             | 3,400ms          | 7.4 / 10     |
| **OpenAI**    | ChatGPT 5.6 Sol     | `openai/chatgpt-5.6-sol`       | 93.8                  | $6.50               | 96 tok/s             | 2,600ms          | 8.4 / 10     |
| **OpenAI**    | ChatGPT 5.6 Terra   | `openai/chatgpt-5.6-terra`     | 90.4                  | $2.60               | 115 tok/s            | 1,850ms          | 9.2 / 10     |
| **OpenAI**    | ChatGPT 5.6 Luna    | `openai/chatgpt-5.6-luna`      | -                     | $0.81               | 145 tok/s            | 1,200ms          | -            |
| **Anthropic** | Claude Opus 5       | `anthropic/claude-opus-5`      | 96.2                  | $16.25              | 78 tok/s             | 3,850ms          | 6.8 / 10     |
| **Anthropic** | Claude Sonnet 5     | `anthropic/claude-sonnet-5`    | 94.6                  | $8.13               | 102 tok/s            | 2,350ms          | 8.2 / 10     |
| **Anthropic** | Claude Fable 5.1    | `anthropic/claude-fable-5.1`   | 93.2                  | $3.90               | 120 tok/s            | 1,650ms          | 9.0 / 10     |
| **Anthropic** | Claude Fable 5      | `anthropic/claude-fable-5`     | 91.8                  | $2.93               | 128 tok/s            | 1,500ms          | 9.2 / 10     |
| **Google**    | Gemini 3.1 Pro      | `google/gemini-3.1-pro`        | 95.1                  | $4.88               | 95 tok/s             | 2,450ms          | 8.6 / 10     |
| **Google**    | Gemini 3.8 Flash    | `google/gemini-3.8-flash`      | 91.0                  | $0.49               | 165 tok/s            | 1,100ms          | 9.8 / 10     |
| **Google**    | Gemini 3.7 Flash    | `google/gemini-3.7-flash`      | 89.4                  | $0.33               | 175 tok/s            | 980ms            | 9.8 / 10     |
| **Google**    | Gemini 3.6 Flash    | `google/gemini-3.6-flash`      | 86.5                  | $0.20               | 190 tok/s            | 820ms            | 9.8 / 10     |
| **Google**    | Gemma 4             | `google/gemma-4`               | 84.8                  | $0.16               | 195 tok/s            | 760ms            | 9.8 / 10     |
| **DeepSeek**  | DeepSeek V4.0 Pro   | `deepseek/deepseek-v4.0-pro`   | 95.4                  | $1.14               | 110 tok/s            | 1,980ms          | **9.9 / 10** |
| **DeepSeek**  | DeepSeek V4.1 Flash | `deepseek/deepseek-v4.1-flash` | 91.2                  | $0.26               | 160 tok/s            | 1,150ms          | **9.9 / 10** |
| **DeepSeek**  | DeepSeek V4.0 Flash | `deepseek/deepseek-v4.0-flash` | 86.8                  | $0.16               | 180 tok/s            | 920ms            | 9.8 / 10     |
| **xAI**       | Grok 4.6            | `xai/grok-4.6`                 | 94.8                  | $9.10               | 92 tok/s             | 2,750ms          | 7.9 / 10     |
| **xAI**       | Grok 4.5            | `xai/grok-4.5`                 | 92.5                  | $4.55               | 110 tok/s            | 2,050ms          | 8.8 / 10     |
| **Alibaba**   | Qwen 3.8 Max        | `qwen/qwen-3.8-max`            | 94.0                  | $5.85               | 105 tok/s            | 2,300ms          | 8.7 / 10     |
| **Alibaba**   | Qwen 3.8            | `qwen/qwen-3.8`                | 91.4                  | $0.65               | 138 tok/s            | 1,680ms          | 9.8 / 10     |
| **Alibaba**   | Qwen 3.7 Coder      | `qwen/qwen-3.7-coder`          | 89.8                  | $0.72               | 145 tok/s            | 1,450ms          | 9.5 / 10     |
| **Moonshot**  | Kimi K3             | `moonshot/kimi-k3`             | 92.1                  | $1.30               | 125 tok/s            | 1,920ms          | 9.6 / 10     |
| **Zhipu**     | GLM 5.3             | `zhipu/glm-5.3`                | 91.5                  | $0.98               | 130 tok/s            | 1,840ms          | 9.7 / 10     |
| **Zhipu**     | GLM 5.3 Flash       | `zhipu/glm-5.3-flash`          | 41.8                  | $0.24               | 185 tok/s            | 910ms            | -            |
| **Muse**      | Muse 1.3 Spark      | `muse/muse-1.3-spark`          | 48.1                  | $2.00               | -                    | 44,850ms         | -            |
| **Muse**      | Muse 1.2 Spark      | `muse/muse-1.2-spark`          | -                     | $0.13               | -                    | -                | -            |
| **OpenAI**    | ChatGPT 6 Sol       | `openai/chatgpt-6-sol`         | 47.5                  | $4.00               | -                    | 163,528ms        | -            |
| **OpenAI**    | ChatGPT 6 Luna      | `openai/chatgpt-6-luna`        | 37.3                  | $0.20               | -                    | 94,118ms         | -            |
| **Anthropic** | Claude Opus 5.5     | `anthropic/claude-opus-5.5`    | 57.6                  | $8.00               | -                    | 681,274ms        | -            |
| **Anthropic** | Claude Sonnet 5.5   | `anthropic/claude-sonnet-5.5`  | 56.0                  | $4.00               | -                    | 327,864ms        | -            |
| **Google**    | Gemini 3.5 Flash    | `google/gemini-3.5-flash`      | 22.2                  | $0.85               | -                    | 9,631ms          | -            |
| **xAI**       | Grok 4.7            | `xai/grok-4.7`                 | 46.4                  | $3.00               | -                    | 55,256ms         | -            |
| **Xiaomi**    | MiMo V2.6 Pro       | `mimo/mimo-v2.6-pro`           | 46.3                  | $0.54               | -                    | 50,931ms         | -            |
| **Xiaomi**    | MiMo V2.6 Flash     | `mimo/mimo-v2.6-flash`         | -                     | -                   | -                    | -                | -            |
| **MiniMax**   | Minimax M3          | `minimax/minimax-m3`           | 29.2                  | $0.53               | -                    | 17,500ms         | -            |
| **TypeSafe**  | Jev                 | `typesafe/jev`                 | -                     | -                   | -                    | -                | -            |
| **Other**     | Laya                | `laya`                         | -                     | -                   | -                    | -                | -            |

---

## 2. Complete Reasoning Effort Breakdown (High, Medium, Low)

Thinking / reasoning effort levels:

- **Low Effort**: Fast generation with compact chain-of-thought (1,024 tokens).
- **Medium Effort**: Standard balanced reasoning tree (4,096 - 8,192 tokens).
- **High Effort**: Maximum reflection and multi-hypothesis verification (16,384 - 32,768 tokens).

| Model Identifier               | Reasoning Effort | Quality Index (0-100) | Blended Cost ($/1M) | Output Speed (tok/s) | Median TTFT (ms) | Value Score  |
| :----------------------------- | :--------------- | :-------------------- | :------------------ | :------------------- | :--------------- | :----------- |
| `openai/chatgpt-6-astra`       | High             | 96.8                  | $13.00              | 88                   | 3,400ms          | 7.4 / 10     |
| `openai/chatgpt-6-astra`       | Medium           | -                     | $10.00              | 94                   | 1,150ms          | -            |
| `openai/chatgpt-6-astra`       | Low              | -                     | $7.00               | 102                  | 420ms            | -            |
| `openai/chatgpt-5.6-sol`       | High             | 93.8                  | $6.50               | 96                   | 2,600ms          | 8.4 / 10     |
| `openai/chatgpt-5.6-sol`       | Medium           | -                     | $5.00               | 106                  | 920ms            | -            |
| `openai/chatgpt-5.6-sol`       | Low              | -                     | $3.50               | 116                  | 380ms            | -            |
| `openai/chatgpt-5.6-terra`     | High             | 90.4                  | $2.60               | 115                  | 1,850ms          | 9.2 / 10     |
| `openai/chatgpt-5.6-terra`     | Medium           | -                     | $2.00               | 125                  | 680ms            | -            |
| `openai/chatgpt-5.6-terra`     | Low              | -                     | $1.40               | 136                  | 290ms            | -            |
| `openai/chatgpt-5.6-luna`      | High             | -                     | $0.81               | 145                  | 1,200ms          | -            |
| `openai/chatgpt-5.6-luna`      | Medium           | -                     | -                   | -                    | -                | -            |
| `openai/chatgpt-5.6-luna`      | Low              | -                     | -                   | -                    | -                | -            |
| `anthropic/claude-opus-5`      | High             | 96.2                  | $16.25              | 78                   | 3,850ms          | 6.8 / 10     |
| `anthropic/claude-opus-5`      | Medium           | -                     | $12.50              | 85                   | 1,320ms          | -            |
| `anthropic/claude-opus-5`      | Low              | -                     | $8.75               | 92                   | 480ms            | -            |
| `anthropic/claude-sonnet-5`    | High             | 94.6                  | $8.13               | 102                  | 2,350ms          | 8.2 / 10     |
| `anthropic/claude-sonnet-5`    | Medium           | -                     | $6.25               | 112                  | 840ms            | -            |
| `anthropic/claude-sonnet-5`    | Low              | -                     | $4.38               | 122                  | 340ms            | -            |
| `anthropic/claude-fable-5.1`   | High             | 93.2                  | $3.90               | 120                  | 1,650ms          | 9.0 / 10     |
| `anthropic/claude-fable-5.1`   | Medium           | -                     | $3.00               | 130                  | 610ms            | -            |
| `anthropic/claude-fable-5.1`   | Low              | -                     | $2.10               | 142                  | 260ms            | -            |
| `anthropic/claude-fable-5`     | High             | 91.8                  | $2.93               | 128                  | 1,500ms          | 9.2 / 10     |
| `anthropic/claude-fable-5`     | Medium           | -                     | $2.25               | 138                  | 560ms            | -            |
| `anthropic/claude-fable-5`     | Low              | -                     | $1.58               | 150                  | 240ms            | -            |
| `google/gemini-3.1-pro`        | High             | 95.1                  | $4.88               | 95                   | 2,450ms          | 8.6 / 10     |
| `google/gemini-3.1-pro`        | Medium           | -                     | $3.75               | 105                  | 890ms            | -            |
| `google/gemini-3.1-pro`        | Low              | -                     | $2.63               | 115                  | 360ms            | -            |
| `google/gemini-3.8-flash`      | High             | 91.0                  | $0.49               | 165                  | 1,100ms          | 9.8 / 10     |
| `google/gemini-3.8-flash`      | Medium           | -                     | $0.38               | 178                  | 420ms            | -            |
| `google/gemini-3.8-flash`      | Low              | -                     | $0.26               | 190                  | 180ms            | -            |
| `google/gemini-3.7-flash`      | High             | 89.4                  | $0.33               | 175                  | 980ms            | 9.8 / 10     |
| `google/gemini-3.7-flash`      | Medium           | -                     | $0.25               | 188                  | 380ms            | -            |
| `google/gemini-3.7-flash`      | Low              | -                     | $0.18               | 200                  | 160ms            | -            |
| `google/gemini-3.6-flash`      | High             | 86.5                  | $0.20               | 190                  | 820ms            | 9.8 / 10     |
| `google/gemini-3.6-flash`      | Medium           | -                     | -                   | -                    | -                | -            |
| `google/gemini-3.6-flash`      | Low              | -                     | -                   | -                    | -                | -            |
| `google/gemma-4`               | High             | 84.8                  | $0.16               | 195                  | 760ms            | 9.8 / 10     |
| `google/gemma-4`               | Medium           | -                     | -                   | -                    | -                | -            |
| `google/gemma-4`               | Low              | -                     | -                   | -                    | -                | -            |
| `deepseek/deepseek-v4.0-pro`   | High             | 95.4                  | $1.14               | 110                  | 1,980ms          | **9.9 / 10** |
| `deepseek/deepseek-v4.0-pro`   | Medium           | -                     | $0.88               | 120                  | 710ms            | -            |
| `deepseek/deepseek-v4.0-pro`   | Low              | -                     | $0.61               | 132                  | 280ms            | -            |
| `deepseek/deepseek-v4.1-flash` | High             | 91.2                  | $0.26               | 160                  | 1,150ms          | **9.9 / 10** |
| `deepseek/deepseek-v4.1-flash` | Medium           | -                     | $0.20               | 172                  | 440ms            | -            |
| `deepseek/deepseek-v4.1-flash` | Low              | -                     | $0.14               | 185                  | 190ms            | -            |
| `deepseek/deepseek-v4.0-flash` | High             | 86.8                  | $0.16               | 180                  | 920ms            | 9.8 / 10     |
| `deepseek/deepseek-v4.0-flash` | Medium           | -                     | -                   | -                    | -                | -            |
| `deepseek/deepseek-v4.0-flash` | Low              | -                     | -                   | -                    | -                | -            |
| `xai/grok-4.6`                 | High             | 94.8                  | $9.10               | 92                   | 2,750ms          | 7.9 / 10     |
| `xai/grok-4.6`                 | Medium           | -                     | $7.00               | 100                  | 960ms            | -            |
| `xai/grok-4.6`                 | Low              | -                     | $4.90               | 108                  | 390ms            | -            |
| `xai/grok-4.5`                 | High             | 92.5                  | $4.55               | 110                  | 2,050ms          | 8.8 / 10     |
| `xai/grok-4.5`                 | Medium           | -                     | $3.50               | 120                  | 740ms            | -            |
| `xai/grok-4.5`                 | Low              | -                     | $2.45               | 130                  | 310ms            | -            |
| `qwen/qwen-3.8-max`            | High             | 94.0                  | $5.85               | 105                  | 2,300ms          | 8.7 / 10     |
| `qwen/qwen-3.8-max`            | Medium           | -                     | $4.50               | 115                  | 820ms            | -            |
| `qwen/qwen-3.8-max`            | Low              | -                     | $3.15               | 125                  | 330ms            | -            |
| `qwen/qwen-3.8`                | High             | 91.4                  | $0.65               | 138                  | 1,680ms          | 9.8 / 10     |
| `qwen/qwen-3.8`                | Medium           | -                     | $0.50               | 148                  | 600ms            | -            |
| `qwen/qwen-3.8`                | Low              | -                     | $0.35               | 160                  | 250ms            | -            |
| `qwen/qwen-3.7-coder`          | High             | 89.8                  | $0.72               | 145                  | 1,450ms          | 9.5 / 10     |
| `qwen/qwen-3.7-coder`          | Medium           | -                     | $0.55               | 158                  | 520ms            | -            |
| `qwen/qwen-3.7-coder`          | Low              | -                     | $0.39               | 170                  | 210ms            | -            |
| `moonshot/kimi-k3`             | High             | 92.1                  | $1.30               | 125                  | 1,920ms          | 9.6 / 10     |
| `moonshot/kimi-k3`             | Medium           | -                     | $1.00               | 135                  | 690ms            | -            |
| `moonshot/kimi-k3`             | Low              | -                     | $0.70               | 148                  | 280ms            | -            |
| `zhipu/glm-5.3`                | High             | 91.5                  | $0.98               | 130                  | 1,840ms          | 9.7 / 10     |
| `zhipu/glm-5.3`                | Medium           | -                     | $0.75               | 140                  | 660ms            | -            |
| `zhipu/glm-5.3`                | Low              | -                     | $0.53               | 152                  | 270ms            | -            |
| `zhipu/glm-5.3-flash`          | High             | -                     | $0.23               | 185                  | 910ms            | -            |
| `zhipu/glm-5.3-flash`          | Medium           | -                     | -                   | -                    | -                | -            |
| `zhipu/glm-5.3-flash`          | Low              | -                     | -                   | -                    | -                | -            |
| `muse/muse-1.3-spark`          | High             | -                     | $0.29               | -                    | -                | -            |
| `muse/muse-1.3-spark`          | Medium           | -                     | -                   | -                    | -                | -            |
| `muse/muse-1.3-spark`          | Low              | -                     | -                   | -                    | -                | -            |
| `muse/muse-1.2-spark`          | High             | -                     | $0.13               | -                    | -                | -            |
| `muse/muse-1.2-spark`          | Medium           | -                     | -                   | -                    | -                | -            |
| `muse/muse-1.2-spark`          | Low              | -                     | -                   | -                    | -                | -            |

---

## 3. Artificial Analysis Frontier Takeaways

1. **The Price-to-Performance Disruption**: DeepSeek V4.0 Pro occupies the top efficiency frontier of any reasoning model ever evaluated by Artificial Analysis, delivering a 95.4 Quality Index at an unprecedented $1.14 blended cost per million tokens.
2. **Speed-Optimized Reasoning**: DeepSeek V4.0 Flash and Gemini 3.6 Flash sustain over 180–190 tokens/second while outperforming previous-generation flagship models.
3. **Enterprise Quality Leaders**: ChatGPT 6 Astra (96.8) and Claude Opus 5 (96.2) represent the ceiling for mission-critical legal, financial, and mathematical analysis.
