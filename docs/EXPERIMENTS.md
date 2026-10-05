# Experiment log

This log records how the TOR compliance pipeline reached its current design. It is for anyone changing the pipeline who needs to know why things are built the way they are. For the current design, see the [README](../README.md).

All runs use [scripts/eval_tor_compliance.py](../scripts/eval_tor_compliance.py) with 3 runs per suite. The drafting model is `qwen/qwen3.5-9b` via OpenRouter. Raw reports were written to `data/eval/`, which is git-ignored.

- **Suite A (checker):** 14 TORs seeded with known defects, 6 compliant near-misses, and 1 clean baseline.
- **Suite B (end-to-end):** 3 requests drafted from scratch.
- **Suite C (chapter revision):** 3 chapter-revision instructions.

---

## 1. Iterating with an LLM judge (2026-10-05)

In this phase the semantic rules (brand lock under มาตรา ๙, proportionate qualifications under มาตรา ๘) were judged by the same generative model that drafts the TOR.

| Metric | Run 1: baseline | Run 2: bug fixes | Run 3: parallel (4 workers) | Run 4: checklist judge |
|---|---|---|---|---|
| A: recall on seeded defects | 92.9% | 92.9% | 90.5% | 100% (42/42) |
| A: semantic (brand lock, qualifications) | 100% | 100% | 81% | 100% |
| A: numeric facts | 75% | 75% | 100% | 100% |
| A: false positives on near-misses | 0% | 5.6% | 0% | 0% (0/18) |
| A: false positives on the clean baseline | 0/3 | 0/3 | 0/3 | 0/3 |
| B: end-to-end pass rate | 0/9 | 8/9 | 9/9 | 8/9 |
| B: mean revisions per TOR | 2.0 | 1.0 | 1.0 | 0.44 |
| B: median latency per TOR | ~120 s | ~65 s | ~34 s | ~34 s (mean 71 s) |
| B: mean LLM calls per TOR | 23.8 | 15.0 | 18.3 | 17.2 |
| C: instruction followed / other chapters untouched | 3/3 / 3/3 | 2/3 / 3/3 | 3/3 / 3/3 | 3/3 / 3/3 |
| C: non-compliant user edit (brand name) flagged | 1/1 | 0/1 | 1/1 | 0/1 |

### What each run found, and the fix

| Run | Problem found | Fix |
|---|---|---|
| 1 → 2 | When the LLM extractor failed, the bond check **passed silently** | Regex backstop for numeric facts. Missing facts now report `warn`, or `needs_human` if extraction failed. |
| 1 → 2 | Retrieval pulled a contract template (a rented-car clause) into a software TOR | Retrieval limited to the Act and the Ministry of Finance regulation; prompt forbids copying unrelated text |
| 1 → 2 | The judge flagged a "3-year warranty" that the agency itself asked for | The judge now receives the agency's requirements; the qualification rule is limited to chapters whose title contains คุณสมบัติ or เกณฑ์ |
| 2 → 3 | A user instruction naming a brand was refused | Drafting constraints are dropped when the user gives an explicit instruction. The checker reports, the user decides. |
| 2 → 3 | Reference-work value was never extracted | Regex backstop for amounts written with commas or Thai digits |
| 2 → 3 | Fully sequential LLM calls | Parallel chapter drafting and revision, facts and judges run concurrently, global limit of 4 LLM requests, judge verdicts cached per chapter |
| 3 → 4 | Judging one chapter at a time hid the project budget, and the open-ended "any violations?" question missed capital and location restrictions (0/5 each) | Project context added to the judge prompt; the qualification rule now uses a **per-item checklist**, so the model must answer every item. Those cases went to 5/5 and 4/5 in a 50-sample targeted test. |

### What the LLM-judge phase taught us

- **Most early end-to-end failures were real defects.** The 0/9 in run 1 was mostly the checker correctly catching drafting defects; it was not the checker being too strict.
- **A 9B generative judge is unstable.** The qualification rule ranged from 62% to 100% recall across runs with near-identical prompts, and fixing one case could break another. Brand-lock flagging after a user edit was caught in only 2 of 4 runs.
- **Asking for a specific answer to each item beats an open-ended question.** With small models, "answer each checklist item" was far more reliable than "report any violations".
- **Tail latency comes from the transport, not the pipeline.** One TOR took 402 s because slow requests waited out a 40 s timeout before trying the fallback model.

---

## 2. Jev decision model replacing the LLM judge (2026-10-05)

[Jev](https://openrouter.ai/typesafe/jev-1.13) (`typesafe/jev-1.13`) is TypeSafe's structured decision model. Instead of generating text, it returns a typed choice with softmax probabilities.

### Working out the API

Jev is not served on `chat/completions`; a request there returns *"is a decisions model … Use the /api/alpha/decisions endpoint"*. There was no public documentation, so the request format was worked out from the endpoint's validation errors:

- **Request:** `{ model, state, questions }`. `state` may be a string, an object or an array; it is context shared by every question. `questions` is a record keyed by question id.
- **Question types:** `noul`, `choice` and `score`. A `choice` question needs `instructions` and `criteria` (option name → description). A `score` question takes `criteria` as an array. `score` was not tested further.
- **`choice` answer:** `{ choice, probabilities: {option: p}, confidence }`. A `noul` answer is a single number between 0 and 1.
- **Batching:** 20 questions in one request completed in about 0.85 s for about $0.00013.

### Design

- **Judge per unit.** Each list item or sentence is its own `choice` question with the options `violation` (or the checklist items) and `compliant`, so a finding's evidence is that unit and is grounded by construction.
- **Shared state** carries the rule, the exact clause text, the guidance, the agency's requirements and the project budget, duration and method.
- **Decision rule.** With P(violation) = 1 − P(compliant): a value ≥ 0.7 is `fail`, and ≥ 0.4 is `needs_human`.
- **Caching and concurrency.** Results are cached per unit, and requests go through the same limit of 4 concurrent requests.

### Results

| Metric | LLM judge (run 4) | **Jev** |
|---|---|---|
| A: recall on seeded defects | 100% (42/42) | **100%** (42/42) |
| A: false positives on near-misses / clean baseline | 0% / 0 of 3 | **0% / 0 of 3** |
| A: stability across runs | qualification rule ranged 62–100% across runs | **every case 3/3** |
| A: score separation | n/a | violations 0.97–1.00; near-misses < 0.4 (none surfaced) |
| Judge stage alone (same document, 3 repeats) | 4.1 s | **1.1 s** |
| B: end-to-end pass rate | 8/9 | **9/9** |
| B: mean latency per TOR | 71 s | **22 s** |
| B: mean LLM calls per TOR | 17.2 | **9.8** (plus batched Jev calls) |
| C: non-compliant user edit (brand name) flagged | 0/1 | **1/1** |

End-to-end time fell mainly because stable verdicts let the revision loop converge, so fewer LLM calls were needed.

### Observations

- **Overlap between the two semantic rules:** the brand-lock rule also flags "head office must be in Chiang Mai", which the qualification rule catches as well, so the same text can produce two findings. A useful collateral catch: the qualification rule flagged a 1.5 M baht reference-work requirement in a 450,000 baht specific-method TOR (reference work larger than the budget).
- **No case-specific explanation:** Jev's findings carry a fixed suggestion text per rule rather than a rewrite tailored to the case.

**Decision:** Jev became the default judge (`TOR_JUDGE_BACKEND=jev`). The LLM judge remains as a fallback backend.
