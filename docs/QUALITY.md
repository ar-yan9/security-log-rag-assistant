# Local 1.0 acceptance and limits

This release finishes a bounded learning-project milestone, not a commercial
security product. It includes a full-stack UI/API, lexical baseline, actual BGE
embeddings/Qdrant, optional actual local Qwen extractive RAG, checked citations,
whole-corpus structured analytics, exports, Windows setup, tests and a beginner
walkthrough. Nothing here certifies the user's laptop or real-world accuracy.

## Distinct evidence, distinct claims

1. Unit/integration tests check code contracts. Offline model doubles do not show
   an actual model ran. Opt-in tests run actual BGE and local Qwen on CPU.
2. The original 14 development cases use 7 synthetic demo events. They are known
   cases, not held out: lexical hit@1 9/10 and 3/4 absent-evidence abstentions;
   BGE hit@1 10/10 and 4/4 abstentions after the narrow IP guard.
3. New separate development regression: 32 fabricated events, 32 answerable
   queries and 8 absent-IP queries. It is not independently authored/reviewed or
   held out. Each positive query names one unique event IP, so the exact-IP guard
   makes this easier than normal semantic search. It does not prove broad quality.
   At unchanged app thresholds (lexical .05, semantic .7), lexical hit@1 **32/32**,
   BGE **23/32**; both abstain on **8/8** absent-IP cases. Semantic missed 9 cases:
   thresholds can drop correct candidates. We did not tune it to perfect results.
   Scores are not probabilities or comparable across methods.
4. `examples/generation-smoke.json` records real Qwen selections, including a
   quote that mentions twelve ports but does not identify the port numbers.
   Exact quote validation proves provenance, not completeness or relevance.
5. Whole-corpus analytics tests count source records, not attempts inferred from
   text. Author-supplied metadata may itself be wrong. No timestamps are guessed.

Reproduce the new regression:

```powershell
.\.venv\Scripts\python.exe evaluate.py --mode lexical --file examples/regression-events.jsonl --cases examples/regression-cases.json
.\.venv\Scripts\python.exe evaluate.py --mode semantic --file examples/regression-events.jsonl --cases examples/regression-cases.json
```

Cases, corpus and actual outputs are in `examples/regression-*`. The generator
`build_regression.py` makes deterministic synthetic fixtures. Do not call them
independent validation, security accuracy, a threat-detection benchmark or
production throughput. No performance/memory claim has been measured on Aryan's
8GB Windows laptop. Close other heavy apps; retrieval-only mode is the fallback.

## Intentional non-goals for local 1.0

No public deployment/auth/tenant isolation, SIEM replacement, live log collectors,
PCAP, exploit testing, unrestricted answers, fine-tuning, persistent Qdrant
server, automatic real-log schema inference, calibrated threshold, independent
human-labeled benchmark or multilingual/model leaderboard. Those are future
scope, not quietly promised as complete. Known query restrictions: explicit IPs
mean AND within one record; OR/negation/account names/CIDRs aren't parsed.

## Review before trusting a result

Check source ID/line/raw event, metadata provenance, corpus coverage and time
scope. Missing evidence does not prove no incident. Quote acceptance does not
prove a correct answer. Logs can contain instructions: they remain inert text;
no tools or actions are available to the local model. Prompt injection is not
solved and irrelevant malicious text can still be selected. No automatic
redaction: never feed credentials/private data you cannot safely display.
