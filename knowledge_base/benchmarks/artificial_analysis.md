# Artificial Analysis LLM Leaderboard: Intelligence, Speed & Cost

Source URL: https://artificialanalysis.ai/leaderboards/models
Retrieved: 2026-10-30
Category: Intelligence Index, cost per task, output speed, latency to first chunk
Provenance: copied from the leaderboard table on the retrieval date (top 30 rows by Artificial Analysis Intelligence Index, in the page's order). The page shows no last-updated date. Values are as published; nothing was estimated. "n/a" means the page showed no value.
Methodology (per the page): Artificial Analysis compares over 250 AI models. The Intelligence Index is the site's composite score; the methodology is described at https://artificialanalysis.ai/faq. Each model appears once per reasoning-effort setting, and the effort is part of the row name.

> [!NOTE]
> "Cost per Task" is the cost of running Artificial Analysis's evaluation tasks, not a price per 1M tokens. "Latency First Chunk" includes any thinking time before the first visible output, which is why high-effort reasoning settings show latencies of minutes.

---

## 1. Top 30 Models by Artificial Analysis Intelligence Index

| Rank | Model (effort)                          | Creator   | Context | Intelligence Index | Cost per Task (USD) | Median Output Speed (tok/s) | Latency First Chunk (s) | Total Response (s) |
| :--- | :-------------------------------------- | :-------- | :------ | :----------------- | :------------------ | :-------------------------- | :---------------------- | :----------------- |
| 1    | Gemini 4 Carbon (high)                  | Google    | 1M      | 59                 | $7.76               | 83                          | 103.54                  | 109.60             |
| 2    | Claude Opus 5.5 (max with fallback)     | Anthropic | 1M      | 58                 | $10.04              | 97                          | 644.22                  | 649.39             |
| 3    | Claude Opus 5.5 (xhigh with fallback)   | Anthropic | 1M      | 57                 | $6.05               | 85                          | 121.20                  | 127.05             |
| 4    | GPT-6 Astra (max)                       | OpenAI    | 1M      | 57                 | $6.24               | 79                          | 237.39                  | 243.74             |
| 5    | GPT-6 Astra (xhigh)                     | OpenAI    | 1M      | 55                 | $3.66               | 64                          | 128.16                  | 135.99             |
| 6    | GPT-6 Astra (high)                      | OpenAI    | 1M      | 55                 | $3.24               | 62                          | 37.83                   | 45.86              |
| 7    | GPT-6.1 Sol (max)                       | OpenAI    | 1M      | 55                 | $1.27               | 81                          | 277.18                  | 283.35             |
| 8    | Claude Sonnet 5.5 (max with fallback)   | Anthropic | 1M      | 54                 | $10.02              | 140                         | 410.96                  | 414.53             |
| 9    | GPT-6.1 Sol (xhigh)                     | OpenAI    | 1M      | 52                 | $0.76               | 67                          | 106.94                  | 114.42             |
| 10   | Claude Opus 5.5 (high with fallback)    | Anthropic | 1M      | 52                 | $3.46               | 80                          | 30.74                   | 36.99              |
| 11   | GPT-6 Astra (medium)                    | OpenAI    | 1M      | 51                 | $2.73               | 58                          | 3.76                    | 12.32              |
| 12   | GPT-6.1 Terra (max)                     | OpenAI    | 1M      | 51                 | $0.96               | 91                          | 233.43                  | 238.93             |
| 13   | Gemini 4 Argon (high)                   | Google    | 1M      | 50                 | $7.68               | 83                          | 48.07                   | 54.07              |
| 14   | GPT-6.1 Sol (high)                      | OpenAI    | 1M      | 50                 | $0.59               | 65                          | 33.88                   | 41.52              |
| 15   | Muse Wonder Full (max)                  | Meta      | 1M      | 50                 | n/a                 | n/a                         | n/a                     | n/a                |
| 16   | Claude Fable 5.1 (xhigh with fallback)  | Anthropic | 1M      | 50                 | $10.85              | 63                          | 70.91                   | 78.89              |
| 17   | Claude Sonnet 5.5 (xhigh with fallback) | Anthropic | 1M      | 50                 | $4.09               | 107                         | 29.32                   | 33.97              |
| 18   | Claude Fable 5.1 (max with fallback)    | Anthropic | 1M      | 49                 | $12.99              | 65                          | 218.04                  | 225.67             |
| 19   | Claude Opus 5.5 (medium with fallback)  | Anthropic | 1M      | 48                 | $2.45               | 79                          | 12.68                   | 18.97              |
| 20   | Claude Fable 5.1 (high with fallback)   | Anthropic | 1M      | 47                 | $7.54               | 57                          | 8.51                    | 17.27              |
| 21   | GPT-6.1 Sol (medium)                    | OpenAI    | 1M      | 46                 | $0.36               | 53                          | 4.27                    | 13.74              |
| 22   | Kimi K3.1 Pro                           | Kimi      | 1M      | 46                 | $3.68               | 32                          | 3.10                    | 81.04              |
| 23   | GPT-6.1 Terra (xhigh)                   | OpenAI    | 1M      | 45                 | $0.40               | 91                          | 39.54                   | 45.03              |
| 24   | Muse Wonder (max)                       | Meta      | 1.05M   | 43                 | $6.95               | 146                         | 27.21                   | 44.35              |
| 25   | GPT-6 Astra (low)                       | OpenAI    | 1M      | 43                 | $1.42               | 58                          | 1.98                    | 10.61              |
| 26   | Claude Fable 5.1 (medium with fallback) | Anthropic | 1M      | 43                 | $5.56               | 56                          | 3.90                    | 12.78              |
| 27   | GPT-6.1 Terra (high)                    | OpenAI    | 1M      | 42                 | $0.26               | 91                          | 9.65                    | 15.15              |
| 28   | Claude Sonnet 5.5 (high with fallback)  | Anthropic | 1M      | 41                 | $1.64               | 107                         | 10.07                   | 14.75              |
| 29   | Claude Fable 5.1 (low with fallback)    | Anthropic | 1M      | 38                 | $4.47               | 55                          | 2.15                    | 11.28              |
| 30   | GPT-6.1 Terra (medium)                  | OpenAI    | 1M      | 38                 | $0.17               | 91                          | 2.33                    | 7.83               |

## 2. Reasoning-Effort Trade-offs (rows from Section 1, grouped by model)

Each line lists effort setting: Intelligence Index / Cost per Task / Latency First Chunk.

- **Claude Opus 5.5**: max 58 / $10.04 / 644.22 s; xhigh 57 / $6.05 / 121.20 s; high 52 / $3.46 / 30.74 s; medium 48 / $2.45 / 12.68 s.
- **GPT-6 Astra**: max 57 / $6.24 / 237.39 s; xhigh 55 / $3.66 / 128.16 s; high 55 / $3.24 / 37.83 s; medium 51 / $2.73 / 3.76 s; low 43 / $1.42 / 1.98 s.
- **GPT-6.1 Sol**: max 55 / $1.27 / 277.18 s; xhigh 52 / $0.76 / 106.94 s; high 50 / $0.59 / 33.88 s; medium 46 / $0.36 / 4.27 s.
- **GPT-6.1 Terra**: max 51 / $0.96 / 233.43 s; xhigh 45 / $0.40 / 39.54 s; high 42 / $0.26 / 9.65 s; medium 38 / $0.17 / 2.33 s.
- **Claude Sonnet 5.5**: max 54 / $10.02 / 410.96 s; xhigh 50 / $4.09 / 29.32 s; high 41 / $1.64 / 10.07 s.
- **Claude Fable 5.1**: xhigh 50 / $10.85 / 70.91 s; max 49 / $12.99 / 218.04 s; high 47 / $7.54 / 8.51 s; medium 43 / $5.56 / 3.90 s; low 38 / $4.47 / 2.15 s.

## 3. Observations From the Table

These follow directly from the numbers above; they are not claims made by Artificial Analysis.

- The two highest scores are Gemini 4 Carbon (high) at 59 and Claude Opus 5.5 (max with fallback) at 58.
- GPT-6.1 Sol (max) reaches 55 at $1.27 per task, the lowest cost per task of any row scoring 55 or more.
- Moving from max to xhigh effort costs one point for Claude Opus 5.5 (58 to 57) while cutting latency to first chunk from 644.22 s to 121.20 s.
- For Claude Fable 5.1, xhigh (50) scores higher than max (49) while costing less per task ($10.85 vs $12.99).
- The fastest median output speed in the top 30 is Muse Wonder (max) at 146 tok/s, followed by Claude Sonnet 5.5 (max with fallback) at 140 tok/s.
- Kimi K3.1 Pro is the only model in the top 30 from a creator other than Google, Anthropic, OpenAI or Meta.
