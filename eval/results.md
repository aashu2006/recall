# Recall eval results

Run 2026-11-09 16:14 IST · 10 synthetic voice notes · call time 2026-11-09T10:30:00+05:30 · STT `prisma-v3.0` (codemix) · LLM `openai/gpt-oss-120b`

| Metric | clean | noisy |
|---|---|---|
| WER | 12.1% | 11.8% |
| CER | 10.0% | 8.2% |
| Extraction accuracy (item, qty, rate, date all correct) | 10/12 (83%) | 11/12 (92%) |
| Extra items (not in the note) | 0 | 0 |
| Matching accuracy | 11/12 (92%) | 12/12 (100%) |
| Confirmation rate (items sent to owner) | 2/12 (17%) | 1/12 (8%) |
| STT latency, median / max | 0.6 s / 0.8 s | 0.5 s / 0.9 s |
| Extract + match latency, median / max | 4.1 s / 6.6 s | 3.7 s / 6.8 s |
| End to end (no DB), median / max | 4.6 s / 7.2 s | 4.3 s / 7.7 s |

Per field accuracy over expected items:

| Field | clean | noisy |
|---|---|---|
| kind | 100.0% | 100.0% |
| item | 100.0% | 100.0% |
| spec | 83.3% | 83.3% |
| quantity | 100.0% | 100.0% |
| unit | 100.0% | 100.0% |
| rate | 83.3% | 91.7% |
| delivery_date | 100.0% | 100.0% |

Per case (items correct / expected, then the pipeline decisions):

| Case | Category | WER clean | Items clean | Decisions clean | WER noisy | Items noisy | Decisions noisy |
|---|---|---|---|---|---|---|---|
| C01 | new_order | 9.1% | 1/1 | create | 15.2% | 1/1 | create |
| C02 | new_order | 6.9% | 0/1 | create | 6.9% | 0/1 | create |
| C03 | quantity_change | 8.0% | 1/1 | update #2 | 4.0% | 1/1 | update #2 |
| C04 | rate_change | 17.2% | 0/1 | update #4 | 3.4% | 1/1 | update #4 |
| C05 | date_change | 8.3% | 1/1 | update #5 | 8.3% | 1/1 | update #5 |
| C06 | two_items | 4.9% | 2/2 | update #1, confirm | 7.3% | 2/2 | update #1, create |
| C07 | two_items | 12.8% | 2/2 | create, create | 20.5% | 2/2 | create, create |
| C08 | ambiguous_update | 22.7% | 1/1 | confirm (#3/#101) | 4.5% | 1/1 | confirm (#3/#101) |
| C09 | noisy | 20.0% | 1/1 | update #1 | 28.0% | 1/1 | update #1 |
| C10 | quantity_and_date_change | 18.2% | 1/1 | update #6 | 18.2% | 1/1 | update #6 |

Raw transcripts, extracted items and decisions: `eval/out/results.json`. Cases and expected items: `eval/cases.json`.
