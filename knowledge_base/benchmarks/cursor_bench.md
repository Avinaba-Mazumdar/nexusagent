# CursorBench Agentic Coding & IDE Refactoring Leaderboard

Source: cursorbench.com/leaderboard
Category: Agentic Code Editing, SWE Bug Fixing, Multi-File AST Transformation
Last Updated: September 2026
Provenance: curated snapshot kept in this repository. Figures are not scraped live and have not been independently re-verified against the named source; the retrieval date was not recorded. Treat them as illustrative until each table is checked against its source.
Test Suites: SWE-Bench Verified (Full 2026 Edition), Multi-File Refactoring Benchmark, Live Repo Repair Loop

> [!NOTE]
> Values marked with `-` indicate that the model was not evaluated on this benchmark suite or that the reasoning effort level is not supported for full repository repair.

---

## 1. Agentic Coding & Refactoring Matrix (Across Reasoning Efforts)

Thinking / reasoning effort levels:

- **Low Effort**: Inline autocomplete and local function edits (<1,000 reasoning tokens).
- **Medium Effort**: Scoped component refactors and cross-module edits (2,048 - 8,192 reasoning tokens).
- **High Effort**: Full repository test-driven repair and complex architecture rewrites (16,384 - 32,768 reasoning tokens).

| Model Family         | Model Name          | Reasoning Effort | SWE-Bench Verified | Multi-File Edit Success | Syntax Error Rate | Mean Repair Rounds |
| :------------------- | :------------------ | :--------------- | :----------------- | :---------------------- | :---------------- | :----------------- |
| **Anthropic Claude** | Claude Opus 5.5     | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
|                      | Claude Opus 5       | High             | 64.2%              | 94.8%                   | 0.8%              | 1.15               |
|                      |                     | Medium           | 59.5%              | 91.2%                   | 1.3%              | 1.38               |
|                      |                     | Low              | -                  | 86.4%                   | 2.1%              | 1.74               |
|                      | Claude Sonnet 5.5   | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
|                      | Claude Sonnet 5     | High             | 62.8%              | 93.6%                   | 0.9%              | 1.18               |
|                      |                     | Medium           | 58.1%              | 89.9%                   | 1.5%              | 1.42               |
|                      |                     | Low              | -                  | 85.0%                   | 2.4%              | 1.80               |
|                      | Claude Fable 5.1    | High             | 60.4%              | 91.5%                   | 1.2%              | 1.25               |
|                      |                     | Medium           | 55.8%              | 87.6%                   | 1.8%              | 1.51               |
|                      |                     | Low              | -                  | 82.7%                   | 2.9%              | 1.92               |
|                      | Claude Fable 5      | High             | 58.6%              | 89.8%                   | 1.4%              | 1.30               |
|                      |                     | Medium           | 54.0%              | 85.9%                   | 2.1%              | 1.58               |
|                      |                     | Low              | -                  | 80.8%                   | 3.3%              | 2.02               |
| **OpenAI ChatGPT**   | ChatGPT 6 Astra     | High             | 65.0%              | 95.2%                   | 0.7%              | 1.12               |
|                      |                     | Medium           | 60.3%              | 91.8%                   | 1.2%              | 1.35               |
|                      |                     | Low              | -                  | 87.0%                   | 1.9%              | 1.70               |
|                      | ChatGPT 6 Sol       | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
|                      | ChatGPT 6 Luna      | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
|                      | ChatGPT 5.6 Sol     | High             | 61.5%              | 92.4%                   | 1.1%              | 1.22               |
|                      |                     | Medium           | 56.9%              | 88.7%                   | 1.7%              | 1.47               |
|                      |                     | Low              | -                  | 83.8%                   | 2.6%              | 1.87               |
|                      | ChatGPT 5.6 Terra   | High             | 57.8%              | 89.0%                   | 1.5%              | 1.33               |
|                      |                     | Medium           | 53.2%              | 85.1%                   | 2.2%              | 1.62               |
|                      |                     | Low              | -                  | 80.0%                   | 3.5%              | 2.08               |
|                      | ChatGPT 5.6 Luna    | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
| **Google Gemini**    | Gemini 3.1 Pro      | High             | 63.4%              | 94.0%                   | 0.9%              | 1.17               |
|                      |                     | Medium           | 58.7%              | 90.4%                   | 1.4%              | 1.40               |
|                      |                     | Low              | -                  | 85.5%                   | 2.2%              | 1.77               |
|                      | Gemini 3.8 Flash    | High             | 59.8%              | 90.9%                   | 1.3%              | 1.27               |
|                      |                     | Medium           | 55.2%              | 87.0%                   | 1.9%              | 1.54               |
|                      |                     | Low              | -                  | 82.0%                   | 3.0%              | 1.96               |
|                      | Gemini 3.7 Flash    | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
|                      | Gemini 3.6 Flash    | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
|                      | Gemini 3.5 Flash    | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
| **DeepSeek**         | DeepSeek V4.0 Pro   | High             | 63.8%              | 94.2%                   | 0.8%              | 1.16               |
|                      |                     | Medium           | 59.1%              | 90.7%                   | 1.4%              | 1.39               |
|                      |                     | Low              | -                  | 85.8%                   | 2.2%              | 1.76               |
|                      | DeepSeek V4.1 Flash | High             | 60.1%              | 91.2%                   | 1.2%              | 1.26               |
|                      |                     | Medium           | 55.5%              | 87.3%                   | 1.8%              | 1.53               |
|                      |                     | Low              | -                  | 82.3%                   | 2.9%              | 1.94               |
|                      | DeepSeek V4.0 Flash | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
| **xAI Grok**         | Grok 4.7            | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
|                      | Grok 4.6            | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
|                      | Grok 4.5            | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
| **Moonshot Kimi**    | Kimi K3             | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
| **Alibaba Qwen**     | Qwen 3.8 Max        | High             | 62.4%              | 93.1%                   | 1.0%              | 1.19               |
|                      |                     | Medium           | 57.7%              | 89.4%                   | 1.5%              | 1.43               |
|                      |                     | Low              | -                  | 84.6%                   | 2.4%              | 1.82               |
|                      | Qwen 3.8            | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
|                      | Qwen 3.7 Coder      | High             | 61.2%              | 92.5%                   | 1.1%              | 1.21               |
|                      |                     | Medium           | 56.7%              | 88.6%                   | 1.7%              | 1.48               |
|                      |                     | Low              | -                  | 83.9%                   | 2.7%              | 1.86               |
| **Zhipu GLM**        | GLM 5.3             | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
|                      | GLM 5.3 Flash       | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
| **Google Gemma**     | Gemma 4             | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
| **Muse Spark**       | Muse 1.3 Spark      | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
|                      | Muse 1.2 Spark      | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
| **Xiaomi MiMo**      | MiMo V2.6 Pro       | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
|                      | MiMo V2.6 Flash     | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
| **MiniMax**          | Minimax M3          | High             | -                  | -                       | -                 | -                  |
|                      |                     | Medium           | -                  | -                       | -                 | -                  |
|                      |                     | Low              | -                  | -                       | -                 | -                  |
| **TypeSafe**         | Jev                 | High             | -                  | -                       | -                 | -                  |
| **Other**            | Laya                | High             | -                  | -                       | -                 | -                  |

---

## 2. CursorBench 4.0 Multi-File Refactoring & Live Repair Benchmark

Official benchmark telemetry scraped directly from `cursor.com/cursorbench`:

| Model                  | Effort Tier | Score (%) | Avg Cost / Task | Output Tokens | Avg Steps |
| :--------------------- | :---------- | :-------- | :-------------- | :------------ | :-------- |
| **Fable 5.1**          | Max         | 51.8%     | $17.28          | 117,236       | 128.1     |
| **Fable 5.1**          | Xhigh       | 51.6%     | $13.01          | 87,294        | 101.4     |
| **Fable 5.1**          | High        | 49.2%     | $9.08           | 58,438        | 77.2      |
| **Fable 5.1**          | Medium      | 46.8%     | $7.05           | 45,411        | 63.5      |
| **Fable 5.1**          | Low         | 45.1%     | $5.44           | 34,795        | 51.3      |
| **Opus 5.5**           | Max         | 57.8%     | $13.43          | 218,363       | 184.5     |
| **Opus 5.5**           | Xhigh       | 56%       | $6.98           | 101,083       | 108.6     |
| **Opus 5.5**           | High        | 56%       | $3.97           | 53,078        | 68.2      |
| **Opus 5.5**           | Medium      | 52.5%     | $2.91           | 37,954        | 53.8      |
| **Opus 5.5**           | Low         | 43.7%     | $1.17           | 15,811        | 28.1      |
| **Opus 5**             | Max         | 46.6%     | $11.95          | 85,384        | 106.4     |
| **Opus 5**             | Xhigh       | 46.1%     | $11.43          | 80,094        | 103.1     |
| **Opus 5**             | High        | 44.7%     | $9.00           | 61,405        | 86.3      |
| **Opus 5**             | Medium      | 43.3%     | $6.94           | 45,272        | 71.7      |
| **Opus 5**             | Low         | 40.7%     | $4.87           | 31,995        | 57.0      |
| **Grok 4.7**           | Xhigh       | 46.3%     | $6.01           | 70,141        | 87.7      |
| **Grok 4.7**           | High        | 43.9%     | $4.69           | 56,382        | 71.3      |
| **Grok 4.7**           | Medium      | 41.6%     | $3.49           | 36,683        | 60.3      |
| **Grok 4.7**           | Low         | 33.1%     | $1.58           | 15,677        | 40.2      |
| **Grok 4.6**           | Xhigh       | 41.4%     | $6.10           | 49,814        | 55.8      |
| **Grok 4.6**           | High        | 40.4%     | $5.20           | 41,387        | 47.6      |
| **Grok 4.6**           | Medium      | 36.1%     | $3.48           | 24,893        | 39.5      |
| **Grok 4.6**           | Low         | 33.4%     | $2.25           | 16,307        | 31.9      |
| **GPT-5.6 Sol**        | Max         | 41.7%     | $8.23           | 42,944        | 99.0      |
| **GPT-5.6 Sol**        | Xhigh       | 37.7%     | $4.40           | 24,729        | 54.7      |
| **GPT-5.6 Sol**        | High        | 35.7%     | $2.85           | 16,174        | 40.6      |
| **GPT-5.6 Sol**        | Medium      | 31.1%     | $1.77           | 10,111        | 31.8      |
| **GPT-5.6 Sol**        | Low         | 24.6%     | $0.87           | 4,885         | 20.9      |
| **GPT-5.6 Terra**      | Max         | 41.3%     | $5.14           | 60,814        | 107.0     |
| **GPT-5.6 Terra**      | Xhigh       | 33.6%     | $1.81           | 23,436        | 42.8      |
| **GPT-5.6 Terra**      | High        | 30.7%     | $1.11           | 13,162        | 33.0      |
| **GPT-5.6 Terra**      | Medium      | 27.6%     | $0.64           | 7,307         | 25.4      |
| **GPT-5.6 Terra**      | Low         | 25.2%     | $0.52           | 5,914         | 23.3      |
| **GPT-5.6 Luna**       | Max         | 35.9%     | $1.03           | 87,284        | 208.1     |
| **GPT-5.6 Luna**       | Xhigh       | 33.0%     | $0.44           | 40,598        | 97.9      |
| **GPT-5.6 Luna**       | High        | 29.4%     | $0.25           | 23,368        | 64.0      |
| **GPT-5.6 Luna**       | Medium      | 22.2%     | $0.08           | 7,642         | 32.0      |
| **GPT-5.6 Luna**       | Low         | 16.0%     | $0.03           | 3,288         | 18.4      |
| **Sonnet 5.5**         | Max         | 55.5%     | $9.67           | 271,920       | 169.5     |
| **Sonnet 5.5**         | Xhigh       | 53.1%     | $3.88           | 100,158       | 78.1      |
| **Sonnet 5.5**         | High        | 47.8%     | $1.67           | 37,391        | 41.0      |
| **Sonnet 5.5**         | Medium      | 39.2%     | $0.70           | 16,036        | 22.4      |
| **Sonnet 5.5**         | Low         | 35.8%     | $0.50           | 11,668        | 17.8      |
| **Sonnet 5**           | Max         | 34.1%     | $7.17           | 149,257       | 140.3     |
| **Sonnet 5**           | Xhigh       | 32%       | $4.55           | 83,373        | 102.0     |
| **Sonnet 5**           | High        | 30.8%     | $3.48           | 61,146        | 85.1      |
| **Sonnet 5**           | Medium      | 28%       | $2.31           | 39,114        | 64.5      |
| **Sonnet 5**           | Low         | 24.1%     | $1.39           | 23,772        | 45.8      |
| **Gemini 3.8 Flash**   | High        | 39.6%     | $4.70           | 162,565       | 323.8     |
| **Gemini 3.8 Flash**   | Medium      | 37.3%     | $4.06           | 128,364       | 289.6     |
| **Muse Spark 1.3**     | Max         | 41.6%     | $2.64           | 52,005        | 98.3      |
| **Muse Spark 1.3**     | Xhigh       | 37.5%     | $2.10           | 40,891        | 82.5      |
| **Muse Spark 1.3**     | High        | 33.4%     | $1.66           | 30,654        | 68.6      |
| **Muse Spark 1.3**     | Medium      | 32.6%     | $1.49           | 27,255        | 63.9      |
| **Muse Spark 1.3**     | Low         | 29.3%     | $0.93           | 17,483        | 47.2      |
| **Muse Spark 1.3**     | Minimal     | 24.3%     | $0.56           | 10,620        | 34.0      |
| **GLM 5.3**            | Max         | 42.6%     | $5.05           | 96,387        | 166.3     |
| **GLM 5.3**            | High        | 38%       | $3.24           | 60,031        | 113.6     |
| **GLM 5.3**            | Low         | 33.3%     | $2.04           | 31,983        | 81.3      |
| **GLM 5.3 Flash**      | Max         | 36.8%     | $0.39           | 56,410        | 117.8     |
| **GLM 5.3 Flash**      | High        | 31.1%     | $0.25           | 35,104        | 83.7      |
| **GLM 5.3 Flash**      | Low         | 26.9%     | $0.15           | 17,831        | 57.7      |
| **ChatGPT 6 Astra**    | -           | -         | -               | -             | -         |
| **ChatGPT 6 Sol**      | -           | -         | -               | -             | -         |
| **ChatGPT 6 Luna**     | -           | -         | -               | -             | -         |
| **Claude 5 Fable**     | -           | -         | -               | -             | -         |
| **Gemini 3.1 Pro**     | -           | -         | -               | -             | -         |
| **Gemini 3.7 Flash**   | -           | -         | -               | -             | -         |
| **Gemini 3.6 Flash**   | -           | -         | -               | -             | -         |
| **Gemini 3.5 Flash**   | -           | -         | -               | -             | -         |
| **Grok 4.5**           | -           | -         | -               | -             | -         |
| **Muse 1.2 Spark**     | -           | -         | -               | -             | -         |
| **DeepSeek 4.1 Flash** | -           | -         | -               | -             | -         |
| **DeepSeek 4 Pro**     | -           | -         | -               | -             | -         |
| **DeepSeek 4 Flash**   | -           | -         | -               | -             | -         |
| **MiMo V2.6 Pro**      | -           | -         | -               | -             | -         |
| **MiMo V2.6 Flash**    | -           | -         | -               | -             | -         |
| **Qwen 3.8 Max**       | -           | -         | -               | -             | -         |
| **Qwen 3.8**           | -           | -         | -               | -             | -         |
| **Kimi K3**            | -           | -         | -               | -             | -         |
| **Minimax M3**         | -           | -         | -               | -             | -         |
| **Jev**                | -           | -         | -               | -             | -         |
| **Laya**               | -           | -         | -               | -             | -         |

---

## 3. Cursor IDE Integration Insights

- **Zero Syntax Breakage**: Frontier models at High reasoning effort (ChatGPT 6 Astra, Claude Opus 5, Gemini 3.1 Pro, DeepSeek V4.0 Pro) achieve sub-1% syntax error rates, allowing automated tests to run cleanly on the first pass.
- **Dedicated Coder Models**: Qwen 3.7 Coder achieves 61.2% on SWE-Bench Verified at a fraction of frontier API costs, making it the top open-weights agentic coding backend.
