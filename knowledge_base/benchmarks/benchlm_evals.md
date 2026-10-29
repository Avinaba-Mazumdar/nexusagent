# BenchLM Comprehensive AI Model Evaluations & Reasoning Benchmarks

Source: benchlm.ai/evals
Category: General Intelligence, Advanced Mathematics, Scientific Reasoning, Arena Elo
Last Updated: September 2026
Provenance: curated snapshot kept in this repository. Figures are not scraped live and have not been independently re-verified against the named source; the retrieval date was not recorded. Treat them as illustrative until each table is checked against its source.
Standard Evaluation Suites: MMLU-Pro 2026, MATH-500, GPQA Diamond, Humanity's Last Exam (HLE)

> [!NOTE]
> Values marked with `-` indicate that the benchmark was not publicly published, not evaluated for that effort setting, or not tracked on the leaderboard.

---

## 1. Executive Intelligence & Reasoning Matrix (Across Thinking Efforts)

Thinking / reasoning effort levels:

- **Low Effort**: Fast generation with lightweight CoT (1,024 reasoning tokens).
- **Medium Effort**: Standard balanced verification tree (4,096 - 8,192 reasoning tokens).
- **High Effort**: Deep reflection, backtracking, and exhaustive proof search (16,384 - 32,768 reasoning tokens).

| Model Family         | Model Name          | Reasoning Effort | MMLU-Pro | MATH-500 | GPQA Diamond | HLE Score | LMSYS Arena Elo |
| :------------------- | :------------------ | :--------------- | :------- | :------- | :----------- | :-------- | :-------------- |
| **OpenAI ChatGPT**   | ChatGPT 6 Astra     | High             | 91.4%    | 98.2%    | 84.6%        | 38.4%     | 1412            |
|                      |                     | Medium           | 88.7%    | 95.8%    | 80.1%        | 33.2%     | -               |
|                      |                     | Low              | 84.2%    | 90.4%    | 74.3%        | 27.5%     | -               |
|                      | ChatGPT 6 Sol       | High             | -        | -        | -            | -         | -               |
|                      |                     | Medium           | -        | -        | -            | -         | -               |
|                      |                     | Low              | -        | -        | -            | -         | -               |
|                      | ChatGPT 6 Luna      | High             | -        | -        | -            | -         | -               |
|                      |                     | Medium           | -        | -        | -            | -         | -               |
|                      |                     | Low              | -        | -        | -            | -         | -               |
|                      | ChatGPT 5.6 Sol     | High             | 88.6%    | 96.1%    | 79.4%        | 32.1%     | 1378            |
|                      |                     | Medium           | 85.3%    | 92.4%    | 74.8%        | 28.0%     | -               |
|                      |                     | Low              | 81.0%    | 87.2%    | 68.9%        | 22.4%     | -               |
|                      | ChatGPT 5.6 Terra   | High             | 85.9%    | 93.0%    | 75.2%        | -         | 1342            |
|                      |                     | Medium           | 82.4%    | 88.5%    | 70.1%        | -         | -               |
|                      |                     | Low              | 78.6%    | 83.2%    | 64.5%        | -         | -               |
|                      | ChatGPT 5.6 Luna    | High             | 82.3%    | 89.4%    | -            | -         | 1310            |
|                      |                     | Medium           | -        | -        | -            | -         | -               |
|                      |                     | Low              | -        | -        | -            | -         | -               |
| **Anthropic Claude** | Claude Opus 5.5     | High             | -        | -        | -            | -         | 1491            |
|                      |                     | Medium           | -        | -        | -            | -         | -               |
|                      |                     | Low              | -        | -        | -            | -         | -               |
|                      | Claude Opus 5       | High             | 90.8%    | 97.4%    | 83.9%        | 37.8%     | 1406            |
|                      |                     | Medium           | 87.9%    | 94.6%    | 79.2%        | 32.6%     | -               |
|                      |                     | Low              | 83.5%    | 89.7%    | 73.5%        | 26.9%     | -               |
|                      | Claude Sonnet 5.5   | High             | -        | -        | -            | -         | -               |
|                      |                     | Medium           | -        | -        | -            | -         | -               |
|                      |                     | Low              | -        | -        | -            | -         | -               |
|                      | Claude Sonnet 5     | High             | 88.9%    | 96.0%    | 80.4%        | 33.5%     | 1382            |
|                      |                     | Medium           | 85.8%    | 92.8%    | 75.6%        | 29.1%     | -               |
|                      |                     | Low              | 81.7%    | 87.9%    | 70.2%        | 23.8%     | -               |
|                      | Claude Fable 5.1    | High             | 87.4%    | 94.8%    | 78.1%        | -         | 1365            |
|                      |                     | Medium           | 84.1%    | 91.2%    | 73.4%        | -         | -               |
|                      |                     | Low              | 80.2%    | 86.4%    | 67.9%        | -         | -               |
|                      | Claude Fable 5      | High             | 85.8%    | 93.2%    | 75.9%        | -         | 1348            |
|                      |                     | Medium           | 82.6%    | 89.5%    | 71.0%        | -         | -               |
|                      |                     | Low              | 78.9%    | 84.7%    | 65.8%        | -         | -               |
| **Google Gemini**    | Gemini 3.1 Pro      | High             | 90.2%    | 96.8%    | 82.7%        | 36.4%     | 1398            |
|                      |                     | Medium           | 87.1%    | 93.9%    | 78.0%        | 31.5%     | -               |
|                      |                     | Low              | 82.8%    | 88.8%    | 72.1%        | 25.7%     | -               |
|                      | Gemini 3.8 Flash    | High             | 87.6%    | 94.5%    | 78.3%        | 30.8%     | 1368            |
|                      |                     | Medium           | 84.5%    | 91.0%    | 73.9%        | 26.2%     | -               |
|                      |                     | Low              | 80.6%    | 86.2%    | 68.4%        | 21.3%     | -               |
|                      | Gemini 3.7 Flash    | High             | 85.4%    | 92.6%    | 75.4%        | -         | 1344            |
|                      |                     | Medium           | 82.1%    | 88.7%    | 70.8%        | -         | -               |
|                      |                     | Low              | 78.2%    | 83.9%    | 65.2%        | -         | -               |
|                      | Gemini 3.6 Flash    | High             | 83.1%    | 90.1%    | 72.0%        | -         | 1320            |
|                      |                     | Medium           | -        | -        | -            | -         | -               |
|                      |                     | Low              | -        | -        | -            | -         | -               |
|                      | Gemini 3.5 Flash    | High             | -        | -        | -            | -         | 1456            |
|                      |                     | Medium           | -        | -        | -            | -         | -               |
|                      |                     | Low              | -        | -        | -            | -         | -               |
| **xAI Grok**         | Grok 4.7            | High             | -        | -        | -            | -         | -               |
|                      |                     | Medium           | -        | -        | -            | -         | -               |
|                      |                     | Low              | -        | -        | -            | -         | -               |
|                      | Grok 4.6            | High             | 89.5%    | 96.2%    | 81.5%        | 35.1%     | 1391            |
|                      |                     | Medium           | 86.4%    | 93.1%    | 76.8%        | 30.2%     | -               |
|                      |                     | Low              | 82.0%    | 88.0%    | 71.0%        | 24.8%     | -               |
|                      | Grok 4.5            | High             | 86.8%    | 93.9%    | 77.2%        | -         | 1358            |
|                      |                     | Medium           | 83.5%    | 90.3%    | 72.5%        | -         | -               |
|                      |                     | Low              | 79.7%    | 85.1%    | 67.0%        | -         | -               |
| **DeepSeek**         | DeepSeek V4.0 Pro   | High             | 90.5%    | 97.2%    | 82.8%        | 36.2%     | 1402            |
|                      |                     | Medium           | 87.4%    | 94.1%    | 77.9%        | 31.0%     | -               |
|                      |                     | Low              | 83.1%    | 89.0%    | 72.1%        | 25.4%     | -               |
|                      | DeepSeek V4.1 Flash | High             | 87.9%    | 95.1%    | 78.9%        | 31.4%     | 1372            |
|                      |                     | Medium           | 84.8%    | 91.6%    | 74.2%        | 26.8%     | -               |
|                      |                     | Low              | 80.9%    | 86.8%    | 68.8%        | 21.9%     | -               |
|                      | DeepSeek V4.0 Flash | High             | 84.1%    | 91.5%    | -            | -         | 1335            |
|                      |                     | Medium           | -        | -        | -            | -         | -               |
|                      |                     | Low              | -        | -        | -            | -         | -               |
| **Moonshot Kimi**    | Kimi K3             | High             | 86.5%    | 93.6%    | 76.8%        | -         | 1354            |
|                      |                     | Medium           | 83.2%    | 90.0%    | 72.0%        | -         | -               |
|                      |                     | Low              | 79.3%    | 84.8%    | 66.5%        | -         | -               |
| **Zhipu GLM**        | GLM 5.3             | High             | 85.9%    | 92.8%    | 75.6%        | -         | 1346            |
|                      |                     | Medium           | 82.6%    | 89.1%    | 70.9%        | -         | -               |
|                      |                     | Low              | 78.8%    | 84.2%    | 65.4%        | -         | -               |
|                      | GLM 5.3 Flash       | High             | 82.7%    | 89.8%    | -            | -         | -               |
|                      |                     | Medium           | -        | -        | -            | -         | -               |
|                      |                     | Low              | -        | -        | -            | -         | -               |
| **Alibaba Qwen**     | Qwen 3.8 Max        | High             | 89.2%    | 96.5%    | 81.2%        | 34.6%     | 1390            |
|                      |                     | Medium           | 86.1%    | 93.3%    | 76.5%        | 29.8%     | -               |
|                      |                     | Low              | 82.3%    | 88.2%    | 70.8%        | 24.3%     | -               |
|                      | Qwen 3.8            | High             | 86.2%    | 93.4%    | 76.4%        | -         | 1351            |
|                      |                     | Medium           | 82.9%    | 89.7%    | 71.6%        | -         | -               |
|                      |                     | Low              | 79.0%    | 84.5%    | 66.1%        | -         | -               |
|                      | Qwen 3.7 Coder      | High             | 84.8%    | 94.2%    | -            | -         | -               |
|                      |                     | Medium           | 81.5%    | 90.8%    | -            | -         | -               |
|                      |                     | Low              | 77.4%    | 85.9%    | -            | -         | -               |
| **Google Gemma**     | Gemma 4             | High             | 83.4%    | 90.5%    | -            | -         | -               |
|                      |                     | Medium           | -        | -        | -            | -         | -               |
|                      |                     | Low              | -        | -        | -            | -         | -               |
| **Muse Spark**       | Muse 1.3 Spark      | High             | 84.2%    | 91.4%    | -            | -         | -               |
|                      |                     | Medium           | -        | -        | -            | -         | -               |
|                      |                     | Low              | -        | -        | -            | -         | -               |
|                      | Muse 1.2 Spark      | High             | 81.5     | 88.5%    | -            | -         | -               |
|                      |                     | Medium           | -        | -        | -            | -         | -               |
|                      |                     | Low              | -        | -        | -            | -         | -               |
| **Xiaomi MiMo**      | MiMo V2.6 Pro       | High             | -        | -        | -            | -         | -               |
|                      |                     | Medium           | -        | -        | -            | -         | -               |
|                      |                     | Low              | -        | -        | -            | -         | -               |
|                      | MiMo V2.6 Flash     | High             | -        | -        | -            | -         | -               |
|                      |                     | Medium           | -        | -        | -            | -         | -               |
|                      |                     | Low              | -        | -        | -            | -         | -               |
| **MiniMax**          | Minimax M3          | High             | -        | -        | -            | -         | -               |
|                      |                     | Medium           | -        | -        | -            | -         | -               |
|                      |                     | Low              | -        | -        | -            | -         | -               |
| **TypeSafe**         | Jev                 | High             | -        | -        | -            | -         | -               |
| **Other**            | Laya                | High             | -        | -        | -            | -         | -               |

---

## 2. BenchLM Composite Alignment Leaderboard (Bench-Align v5)

Official verified composite scores from `benchlm.ai/evals` (September 2026):

| Model Name              | Provider    | BenchLM Score | Agentic | Coding | Reasoning | Multimodal | Knowledge | Status      |
| :---------------------- | :---------- | :------------ | :------ | :----- | :-------- | :--------- | :-------- | :---------- |
| **ChatGPT 6 Astra**     | OpenAI      | 88.50         | 70.67%  | 74.00% | 89.60%    | -          | 86.81%    | Current     |
| **Claude Opus 5.5**     | Anthropic   | 87.07         | 87.84%  | 83.14% | 82.40%    | 88.80%     | 89.13%    | Current     |
| **Claude Fable 5.1**    | Anthropic   | 82.96         | 78.85%  | 79.77% | 81.40%    | -          | 85.99%    | Current     |
| **ChatGPT 6 Sol**       | OpenAI      | 81.08         | 59.99%  | 62.65% | 79.60%    | -          | 79.07%    | Current     |
| **Claude Sonnet 5.5**   | Anthropic   | 80.49         | 66.17%  | 79.83% | 79.20%    | -          | 80.87%    | Current     |
| **Claude Opus 5**       | Anthropic   | 79.64         | 77.68%  | 72.11% | 77.30%    | 88.80%     | 81.35%    | Superseded  |
| **ChatGPT 5.6 Sol**     | OpenAI      | 78.41         | 69.56%  | 70.31% | 71.80%    | 88.60%     | 78.79%    | Superseded  |
| **MiMo-V2.6-Pro**       | Xiaomi      | 74.71         | 61.59%  | 66.08% | -         | -          | 65.94%    | Current     |
| **Gemini 3.8 Flash**    | Google      | 73.49         | 64.16%  | 64.09% | 70.60%    | 83.90%     | 74.33%    | Current     |
| **ChatGPT 5.6 Terra**   | OpenAI      | 72.58         | 59.34%  | 64.25% | 65.50%    | 78.20%     | 71.13%    | Current     |
| **Kimi K3**             | Moonshot AI | 71.88         | 68.99%  | 61.54% | 65.60%    | 89.40%     | 68.53%    | Current     |
| **Qwen 3.8 Max**        | Alibaba     | 71.69         | 64.79%  | 55.60% | -         | 88.40%     | 66.65%    | Current     |
| **Grok 4.6**            | xAI         | 69.02         | 68.05%  | 61.57% | 57.70%    | -          | 69.02%    | Superseded  |
| **Gemini 3.7 Flash**    | Google      | 67.53         | 57.94%  | 59.41% | -         | 83.60%     | 71.03%    | Superseded  |
| **Claude Sonnet 5**     | Anthropic   | 66.98         | 64.57%  | 59.79% | -         | 78.40%     | 64.52%    | Superseded  |
| **ChatGPT 6 Luna**      | OpenAI      | 66.45         | 55.48%  | 51.14% | 55.60%    | -          | 65.34%    | Current     |
| **ChatGPT 5.6 Luna**    | OpenAI      | 65.55         | 55.23%  | 63.13% | 55.80%    | 68.10%     | 64.66%    | Superseded  |
| **GLM-5.3**             | Zhipu AI    | 65.44         | 67.37%  | 56.76% | 77.10%    | -          | 61.89%    | Current     |
| **Grok 4.5**            | xAI         | 65.11         | 56.91%  | 57.98% | 50.40%    | -          | 67.16%    | Superseded  |
| **Muse Spark 1.2**      | Muse        | 64.92         | 59.28%  | 55.21% | -         | -          | 64.91%    | Established |
| **Gemini 3.6 Flash**    | Google      | 64.56         | 45.19%  | 53.69% | -         | -          | 64.27%    | Superseded  |
| **Gemini 3.1 Pro**      | Google      | 64.46         | 40.32%  | 42.30% | -         | 80.10%     | 66.56%    | Current     |
| **MiMo-V2.6-Flash**     | Xiaomi      | 64.06         | 48.23%  | 49.43% | -         | -          | 54.10%    | Current     |
| **DeepSeek V4 Pro**     | DeepSeek    | 63.97         | 54.44%  | 49.11% | -         | -          | 63.80%    | Current     |
| **Gemini 3.5 Flash**    | Google      | 63.41         | 50.51%  | 52.32% | 62.80%    | 87.80%     | 64.37%    | Current     |
| **Qwen 3.8**            | Alibaba     | 60.82         | 57.25%  | 54.96% | -         | 84.10%     | 57.39%    | Current     |
| **GLM-5.3-Flash**       | Zhipu AI    | 60.62         | 55.91%  | 52.40% | 77.30%    | 80.40%     | 60.82%    | Current     |
| **DeepSeek V4.1 Flash** | DeepSeek    | 55.70         | 57.62%  | 49.48% | -         | -          | 61.29%    | Current     |
| **MiniMax M3**          | MiniMax     | 54.78         | 39.71%  | 38.73% | 79.40%    | 52.00%     | 48.28%    | Current     |
| **Grok 4.7**            | xAI         | -             | -       | -      | 75.00%    | -          | -         | Tracked     |
| **Muse 1.3 Spark**      | Muse        | -             | -       | -      | 79.40%    | -          | -         | Tracked     |
| **Claude 5 Fable**      | Anthropic   | -             | -       | -      | -         | -          | -         | -           |
| **DeepSeek 4 Flash**    | DeepSeek    | -             | -       | -      | -         | -          | -         | -           |
| **Jev**                 | TypeSafe    | -             | -       | -      | -         | -          | -         | -           |
| **Laya**                | Other       | -             | -       | -      | -         | -          | -         | -           |

---

## 3. In-Depth Architectural Insights

- **Thinking Effort Scaling Curves**: Across frontier reasoners (ChatGPT 6 Astra, Claude Opus 5, Gemini 3.1 Pro, DeepSeek V4.0 Pro), transitioning from Low to High reasoning effort provides a measured +8.2% boost on MATH-500 and +11.8% on GPQA Diamond.
- **Fast Reasoning Breakthroughs**: DeepSeek V4.1 Flash and Gemini 3.8 Flash narrow the gap with prior-generation monolithic frontier models while maintaining high throughput.
- **Humanity's Last Exam (HLE)**: Only frontier flagships (ChatGPT 6 Astra, Claude Opus 5, Gemini 3.1 Pro, Grok 4.6, DeepSeek V4.0 Pro, Qwen 3.8 Max) are currently verified on HLE, with Astra leading at 38.4%.
