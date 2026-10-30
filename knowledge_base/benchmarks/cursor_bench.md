# CursorBench 4.0 Agentic Coding Leaderboard

Source URL: https://cursor.com/cursorbench
Background: https://cursor.com/blog/cursorbench
Retrieved: 2026-10-30 (newest changelog entry on the page: Oct 7, 2026)
Category: Agentic coding score, cost per task, tokens per task, steps per task
Provenance: copied from the CursorBench leaderboard on the retrieval date (all 81 rows, in the page's order). Values are as published; nothing was estimated. The page has a single score column and no provider column; each model appears once per reasoning-effort setting.

> [!NOTE]
> In Cursor's words: "We evaluate agents on ambiguous, multi-file tasks from real Cursor sessions. Higher scores are better." CursorBench 4.0 (Sep 10, 2026) added "new long-horizon problems focused on edit, refactor, investigation, intent understanding, managing jobs, and design adherence." Cost per task "is computed by applying each model's published per-million-token pricing (input, cache read, cache write, and output) to the tokens it used on each task. Results are subject to variance; small differences in scores may not be statistically meaningful."

Version history from the page: 4.0 (Sep 10, 2026) long-horizon problems; 3.2 (Jul 8, 2026) "instruction following and advanced tool use problems"; 3.1 (May 19, 2026) "codebase understanding, bugfinding, planning, and code review"; 3.0 (Mar 11, 2026) "edit, refactor, and bugfix problems". Oct 7, 2026: "Updated Sonnet 5.5 results to account for adjusted pricing."

---

## 1. CursorBench 4.0 Leaderboard (All 81 Rows)

| Rank | Model (effort)                  | CursorBench 4.0 Score | Cost / Task | Tokens / Task | Steps / Task |
| :--- | :------------------------------ | :-------------------- | :---------- | :------------ | :----------- |
| 1    | Opus 5.5 Max                    | 57.8%                 | $13.43      | 218,363       | 185          |
| 2    | Opus 5.5 Extra High             | 56.0%                 | $6.98       | 101,083       | 109          |
| 3    | Opus 5.5 High                   | 56.0%                 | $3.97       | 53,078        | 68           |
| 4    | Sonnet 5.5 Max                  | 55.5%                 | $7.05       | 271,920       | 170          |
| 5    | Sonnet 5.5 Extra High           | 53.1%                 | $2.81       | 100,158       | 78           |
| 6    | Gemini 4 Argon High             | 52.9%                 | $4.57       | 109,500       | 118          |
| 7    | Gemini 4 Argon Medium           | 52.8%                 | $4.39       | 103,600       | 115          |
| 8    | Opus 5.5 Medium                 | 52.5%                 | $2.91       | 37,954        | 54           |
| 9    | Fable 5.1 Max                   | 51.8%                 | $17.28      | 117,236       | 128          |
| 10   | Fable 5.1 Extra High            | 51.6%                 | $13.01      | 87,294        | 101          |
| 11   | Gemini 4 Argon Low              | 50.6%                 | $4.09       | 94,200        | 110          |
| 12   | Muse Wonder Max                 | 50.4%                 | $5.25       | 49,692        | 114          |
| 13   | Fable 5.1 High                  | 49.2%                 | $9.08       | 58,438        | 77           |
| 14   | Haiku 5.5 Max                   | 48.4%                 | $1.12       | 325,934       | 163          |
| 15   | Muse Wonder Extra High          | 48.2%                 | $4.24       | 39,564        | 96           |
| 16   | Sonnet 5.5 High                 | 47.8%                 | $1.20       | 37,391        | 41           |
| 17   | DeepSeek V4.1 Flash 1017 Max    | 47.7%                 | $0.98       | 537,047       | 187          |
| 18   | Fable 5.1 Medium                | 46.8%                 | $7.05       | 45,411        | 63           |
| 19   | Opus 5 Max                      | 46.6%                 | $11.95      | 85,384        | 106          |
| 20   | Grok 4.7 Extra High             | 46.3%                 | $6.01       | 70,141        | 88           |
| 21   | DeepSeek V4.1 Flash 1017 Medium | 46.3%                 | $0.80       | 398,255       | 189          |
| 22   | Opus 5 Extra High               | 46.1%                 | $11.43      | 80,094        | 103          |
| 23   | Muse Wonder High                | 46.1%                 | $3.51       | 33,612        | 84           |
| 24   | DeepSeek V4.1 Flash 1017 High   | 45.6%                 | $0.77       | 385,196       | 186          |
| 25   | Muse Wonder Medium              | 45.2%                 | $2.82       | 27,124        | 75           |
| 26   | Fable 5.1 Low                   | 45.1%                 | $5.44       | 34,795        | 51           |
| 27   | DeepSeek V4.1 Flash 1017 Low    | 44.9%                 | $0.60       | 290,651       | 161          |
| 28   | Opus 5 High                     | 44.7%                 | $9.00       | 61,405        | 86           |
| 29   | Haiku 5.5 Extra High            | 44.3%                 | $0.56       | 143,813       | 93           |
| 30   | Grok 4.7 High                   | 43.9%                 | $4.69       | 56,382        | 71           |
| 31   | Opus 5.5 Low                    | 43.7%                 | $1.17       | 15,811        | 28           |
| 32   | Opus 5 Medium                   | 43.3%                 | $6.94       | 45,272        | 72           |
| 33   | GLM 5.3 Max                     | 42.6%                 | $5.05       | 96,387        | 166          |
| 34   | Haiku 5.5 High                  | 42.3%                 | $0.32       | 77,057        | 59           |
| 35   | GPT-5.6 Sol Max                 | 41.7%                 | $8.23       | 42,944        | 99           |
| 36   | Muse Wonder Low                 | 41.7%                 | $1.91       | 18,880        | 56           |
| 37   | Grok 4.7 Medium                 | 41.6%                 | $3.49       | 36,683        | 60           |
| 38   | Muse Spark 1.3 Max              | 41.6%                 | $2.64       | 52,005        | 98           |
| 39   | Grok 4.6 Extra High             | 41.4%                 | $6.10       | 49,814        | 56           |
| 40   | GPT-5.6 Terra Max               | 41.3%                 | $5.14       | 60,814        | 107          |
| 41   | Opus 5 Low                      | 40.7%                 | $4.87       | 31,995        | 57           |
| 42   | Grok 4.6 High                   | 40.4%                 | $5.20       | 41,387        | 48           |
| 43   | Gemini 3.8 Flash High           | 39.6%                 | $4.70       | 162,565       | 324          |
| 44   | Sonnet 5.5 Medium               | 39.2%                 | $0.52       | 16,036        | 22           |
| 45   | GLM 5.3 High                    | 38.0%                 | $3.24       | 60,031        | 114          |
| 46   | GPT-5.6 Sol Extra High          | 37.7%                 | $4.40       | 24,729        | 55           |
| 47   | Muse Spark 1.3 Extra High       | 37.5%                 | $2.10       | 40,891        | 83           |
| 48   | Gemini 3.8 Flash Medium         | 37.3%                 | $4.06       | 128,364       | 290          |
| 49   | Haiku 5.5 Medium                | 36.9%                 | $0.17       | 42,659        | 39           |
| 50   | GLM 5.3 Flash Max               | 36.8%                 | $0.39       | 56,410        | 118          |
| 51   | Grok 4.6 Medium                 | 36.1%                 | $3.48       | 24,893        | 40           |
| 52   | GPT-5.6 Luna Max                | 35.9%                 | $1.03       | 87,284        | 208          |
| 53   | Sonnet 5.5 Low                  | 35.8%                 | $0.37       | 11,668        | 18           |
| 54   | GPT-5.6 Sol High                | 35.7%                 | $2.85       | 16,174        | 41           |
| 55   | Muse Wonder Minimal             | 34.2%                 | $0.84       | 9,761         | 33           |
| 56   | Sonnet 5 Max                    | 34.1%                 | $7.17       | 149,257       | 140          |
| 57   | GPT-5.6 Terra Extra High        | 33.6%                 | $1.81       | 23,436        | 43           |
| 58   | Grok 4.6 Low                    | 33.4%                 | $2.25       | 16,307        | 32           |
| 59   | Muse Spark 1.3 High             | 33.4%                 | $1.66       | 30,654        | 69           |
| 60   | GLM 5.3 Low                     | 33.3%                 | $2.04       | 31,983        | 81           |
| 61   | Grok 4.7 Low                    | 33.1%                 | $1.58       | 15,677        | 40           |
| 62   | GPT-5.6 Luna Extra High         | 33.0%                 | $0.44       | 40,598        | 98           |
| 63   | Muse Spark 1.3 Medium           | 32.6%                 | $1.49       | 27,255        | 64           |
| 64   | Sonnet 5 Extra High             | 32.0%                 | $4.55       | 83,373        | 102          |
| 65   | GPT-5.6 Sol Medium              | 31.1%                 | $1.77       | 10,111        | 32           |
| 66   | GLM 5.3 Flash High              | 31.1%                 | $0.25       | 35,104        | 84           |
| 67   | Haiku 5.5 Low                   | 30.9%                 | $0.08       | 23,382        | 25           |
| 68   | Sonnet 5 High                   | 30.8%                 | $3.48       | 61,146        | 85           |
| 69   | GPT-5.6 Terra High              | 30.7%                 | $1.11       | 13,162        | 33           |
| 70   | GPT-5.6 Luna High               | 29.4%                 | $0.25       | 23,368        | 64           |
| 71   | Muse Spark 1.3 Low              | 29.3%                 | $0.93       | 17,483        | 47           |
| 72   | Sonnet 5 Medium                 | 28.0%                 | $2.31       | 39,114        | 65           |
| 73   | Composer 2.5                    | 27.7%                 | $0.68       | 17,347        | 41           |
| 74   | GPT-5.6 Terra Medium            | 27.6%                 | $0.64       | 7,307         | 25           |
| 75   | GLM 5.3 Flash Low               | 26.9%                 | $0.15       | 17,831        | 58           |
| 76   | GPT-5.6 Terra Low               | 25.2%                 | $0.52       | 5,914         | 23           |
| 77   | GPT-5.6 Sol Low                 | 24.6%                 | $0.87       | 4,885         | 21           |
| 78   | Muse Spark 1.3 Minimal          | 24.3%                 | $0.56       | 10,620        | 34           |
| 79   | Sonnet 5 Low                    | 24.1%                 | $1.39       | 23,772        | 46           |
| 80   | GPT-5.6 Luna Medium             | 22.2%                 | $0.08       | 7,642         | 32           |
| 81   | GPT-5.6 Luna Low                | 16.0%                 | $0.03       | 3,288         | 18           |

## 2. Best Score per Model Family (from Section 1)

| Model family             | Best setting     | Score | Cost / Task |
| :----------------------- | :--------------- | :---- | :---------- |
| Opus 5.5                 | Max              | 57.8% | $13.43      |
| Sonnet 5.5               | Max              | 55.5% | $7.05       |
| Gemini 4 Argon           | High             | 52.9% | $4.57       |
| Fable 5.1                | Max              | 51.8% | $17.28      |
| Muse Wonder              | Max              | 50.4% | $5.25       |
| Haiku 5.5                | Max              | 48.4% | $1.12       |
| DeepSeek V4.1 Flash 1017 | Max              | 47.7% | $0.98       |
| Opus 5                   | Max              | 46.6% | $11.95      |
| Grok 4.7                 | Extra High       | 46.3% | $6.01       |
| GLM 5.3                  | Max              | 42.6% | $5.05       |
| GPT-5.6 Sol              | Max              | 41.7% | $8.23       |
| Muse Spark 1.3           | Max              | 41.6% | $2.64       |
| Grok 4.6                 | Extra High       | 41.4% | $6.10       |
| GPT-5.6 Terra            | Max              | 41.3% | $5.14       |
| Gemini 3.8 Flash         | High             | 39.6% | $4.70       |
| GLM 5.3 Flash            | Max              | 36.8% | $0.39       |
| GPT-5.6 Luna             | Max              | 35.9% | $1.03       |
| Sonnet 5                 | Max              | 34.1% | $7.17       |
| Composer 2.5             | (single setting) | 27.7% | $0.68       |

## 3. Observations From the Table

These follow directly from the numbers above; they are not claims made by Cursor.

- Opus 5.5 High (56.0%, $3.97) matches Opus 5.5 Extra High (56.0%, $6.98) at about 57% of the cost per task and roughly half the tokens.
- The lowest-cost rows scoring above 45%: DeepSeek V4.1 Flash 1017 High (45.6%, $0.77), DeepSeek V4.1 Flash 1017 Medium (46.3%, $0.80), DeepSeek V4.1 Flash 1017 Max (47.7%, $0.98) and Haiku 5.5 Max (48.4%, $1.12). DeepSeek V4.1 Flash 1017 Max uses the most tokens per task on the board (537,047).
- Gemini 3.8 Flash takes the most steps per task of any model (324 at High, 290 at Medium).
- Sonnet 5.5 Medium (39.2%) takes 22 steps per task at $0.52, against 170 steps and $7.05 for Sonnet 5.5 Max (55.5%).
- Composer 2.5, the only model listed with a single setting, scores 27.7% at $0.68 per task.
