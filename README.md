# Log Lens

A local security-log evidence workbench with a React frontend, FastAPI backend,
BGE embeddings, Qdrant vector search and optional CPU-only Qwen generation.

Ask a question, inspect the retrieved log lines, and let a local model select
verbatim quotes. Every accepted quote is checked against a retrieved event and
shown with its event ID and source line. This is deliberately **extractive RAG**,
not an unrestricted chatbot that writes incident conclusions.

**Status: local 1.0 learning-project milestone complete, not a production security product.**
The bundled corpus has seven synthetic events. It is a learning/demo corpus,
not representative telemetry and not proof of real-world detection accuracy.

## What runs today

- React workbench: sample questions, search/RAG modes, evidence cards, source
  citations, loading/error/abstention states, desktop and mobile layout.
- FastAPI: `/api/health`, `/api/search`, `/api/ask`; original unprefixed routes
  also remain available for CLI/API experiments.
- TF-IDF lexical baseline without model downloads.
- Optional real `BAAI/bge-small-en-v1.5` embeddings (384 dimensions), cosine
  search in an **in-memory local Qdrant** collection. This is not a Qdrant server.
- Optional `Qwen/Qwen2.5-0.5B-Instruct-GGUF` running via `llama-cpp-python`.
  No hosted LLM API, API key or paid subscription.
- Generation fails closed on malformed JSON, unknown/duplicate citations,
  invented quotes, excessive output or a truncated response.
- UTF-8 JSONL ingestion bounded to 2 MiB / 2,000 events / 4,000 characters per
  event. One source line is one chunk. IDs must be unique.
- Deterministic whole-corpus analytics: exact structured filters, record counts,
  UTC/undated source timeline and JSON export, separate from similarity top-k.
  [Schema and limits](docs/STRUCTURED_LOGS.md). Evidence/RAG JSON export in the UI.
- Plain-text log normalization keeps original text and line numbers. It does
  **not** parse timestamps, infer a missing year, classify incidents or read PCAP.

## Quick start

Use Python 3.11 and Node.js 22 with npm. First setup needs internet to install
packages; full setup also downloads public models. Models are not in this repo.

Windows PowerShell, in the project folder:

```powershell
py -3.11 setup_project.py
.\.venv\Scripts\python.exe run.py
```

Open `http://127.0.0.1:8000`. This starts the frontend and API on one local origin.
The default is lexical retrieval. It is useful even without an LLM, but it is
**not** the semantic/LLM path.

For actual semantic retrieval + local generation:

```powershell
py -3.11 setup_project.py --full
$env:RETRIEVAL_MODE = 'semantic'
$env:LOCAL_GGUF_MODEL = (Resolve-Path '.\models\qwen2.5-0.5b-instruct-q4_k_m.gguf').Path
.\.venv\Scripts\python.exe run.py
```

In the UI, select **Local RAG · checked quotes**. Try the SSH sample question.
See [RUN_WINDOWS.md](RUN_WINDOWS.md) for exact setup, stopping, troubleshooting,
Linux commands and the developer workflow. Windows and Linux unit-test matrices and actual CPU-model smoke tests have
passed in CI. See the [real-model run](https://github.com/ar-yan9/security-log-rag-assistant/actions/runs/38766397735).
This does not prove setup on your particular laptop or performance on real logs.

## How the pipeline works

```text
Authorized UTF-8 logs -> bounded JSONL events (one line = one chunk)
                      -> TF-IDF baseline OR local BGE embeddings
                      -> local Qdrant cosine top-k (semantic mode)
Question ------------> same embedding model -> retrieved raw events
                      -> optional local Qwen evidence selection
                      -> JSON + exact quote/citation checks
                      -> React source cards and checked quotes
```

The model sees only up to three retrieved events. No tools, browser, shell,
network actions or file access are available to it. It selects evidence instead
of deciding whether a host was compromised. There is no training/fine-tuning here.

## Reproduce tests and demo evidence

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm test
npm run build
cd ..
```

Offline Python tests use test doubles for model-output validation; they do not
prove a real LLM will answer correctly. The separate real embedding test opts in
to model downloads:

```powershell
$env:RUN_MODEL_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest test_semantic.py -q
.\.venv\Scripts\python.exe evaluate.py
```

[examples/retrieval-smoke.json](examples/retrieval-smoke.json) records five
hand-written paraphrase queries over seven synthetic events: hit@1 and hit@3 were
5/5 in that tiny run. This is **not a held-out benchmark**. It does not measure
incident detection, security safety or usefulness on production logs.

[examples/generation-smoke.json](examples/generation-smoke.json) records eight
real local-Qwen calls/abstentions. It includes one important limitation: asking
"Which ports were scanned?" returned a matching quote that mentions twelve ports,
not actual port numbers. Quote validation establishes provenance, **not answer
completeness**. Do not count all evidence selections as correct answers.

## Retrieval evaluation with absent-evidence cases

`evaluate.py` now accepts labeled cases and compares the retrieval modes at the
same thresholds used by the app. It does not run generation. On Windows:

```powershell
.\.venv\Scripts\python.exe evaluate.py --mode lexical
.\.venv\Scripts\python.exe evaluate.py --mode semantic
```

For another **authorized** normalized corpus, use
`--file local-data/events.jsonl --cases local-data/cases.json`. Each case has a unique `id`, a `query`, and an
`expected_ids` list. An empty list labels the query as having no relevant event
in that corpus. Unknown/duplicate event labels are rejected. The optional
`--limit` (1-10) and `--min-score` are recorded in the output; defaults are k=3,
lexical=0.05, semantic=0.7. Scores across these two methods are not comparable.

Checked-in [cases](examples/evaluation-cases.json) and actual local run reports:
[lexical](examples/evaluation-lexical.json),
[semantic](examples/evaluation-semantic.json). Fourteen hand-written queries
cover the same seven demo events: ten answerable and four absent-evidence.
These cases were written after the demo; **they are not held out**.

| Metric at the default threshold, k=3 | Lexical | BGE + Qdrant |
| --- | ---: | ---: |
| Answerable hit@1 | 9/10 | 10/10 |
| Answerable hit@3 | 9/10 | 10/10 |
| Mean recall@3 | 0.90 | 1.00 |
| Mean precision@3 | 0.333 | 0.367 |
| Mean reciprocal rank within top 3 | 0.90 | 1.00 |
| Correct absent-evidence abstentions | 3/4 | 4/4 |
| False-evidence rate on absent-evidence queries | 25% | 0% |

Hit@k means at least one labeled relevant event occurs in the returned top k.
Recall@k is the fraction of all relevant labels retrieved. Precision@k divides
relevant results by k, including empty result slots. Reciprocal rank is 1/rank
of the first relevant event, or zero for a miss. Answerable metrics exclude
absent-evidence cases; false-evidence rate counts absent-evidence queries with
any retrieved event. A category with no cases reports null, never 100%.

**Regression fixed narrowly:** both modes previously returned SSH events for a
query about account `payroll-root` and source `203.0.113.99`, although neither
was in the corpus. The explicit IP constraint now abstains for this query.
It does not enforce account names: a wrong account with an existing IP can
still retrieve an irrelevant event. Do not assert entity-specific facts without
checking the quoted source. Thresholds and labeled cases are unchanged.
Four absent-evidence cases are too few to estimate a real false-positive rate.
These numbers do not evaluate LLM correctness, prompt-injection resistance,
incident detection or production usefulness.

## Use your own authorized log excerpt

Prefer synthetic data. If you use private logs, get permission and remove
credentials, tokens, personal data and anything you cannot show in the UI.

```powershell
New-Item -ItemType Directory -Force local-data
.\.venv\Scripts\python.exe normalize.py .\local-data\input.log .\local-data\events.jsonl --prefix LAB
$env:SECURITY_LOG_FILE = (Resolve-Path '.\local-data\events.jsonl').Path
.\.venv\Scripts\python.exe run.py
```

`normalize.py` refuses to overwrite an existing output. The source is configured
in the local environment, not as an arbitrary HTTP path. Restart after changing
the corpus. Indexes are recreated in memory and are not persistent.

## Retrieval guard regression check

The original 14 synthetic cases are unchanged. After the explicit-IP check,
BGE keeps 10/10 hit@1 and abstains on 4/4 absent-evidence cases (previously 3/4).
Lexical keeps 9/10 hit@1 and abstains on 3/4 (previously 2/4). These are tiny,
known development cases, not independent validation. The previously failing
query names both an absent account and an absent IP; this fixes the IP mismatch,
not general account-name matching. Reproduce with the evaluation commands above.

## Security and privacy boundaries

- Bind only to `127.0.0.1`; no authentication or tenant isolation. **Do not expose
  this server through a tunnel, LAN bind or public deployment.**
- Raw event text is returned by the API and shown in the UI. There is no automatic
  redaction. Local-first does not make secrets safe to paste into logs.
- React escapes text; no raw HTML is rendered. Host allowlisting, same-origin
  assets, no CORS allowance, no-store responses and defensive headers reduce
  avoidable exposure. They do not make this production-ready.
- A log can contain prompt injection. It is treated as untrusted text, never
  instructions. Quote checks limit invented output, but a malicious or irrelevant
  log can still be selected/quoted. **Prompt injection is not solved.**
- BGE scores are not probabilities. The demo threshold is a heuristic and has
  not been calibrated on real logs. Low scores can still be relevant; high
  scores do not prove relevance. The UI says similarity, not confidence.
- Input/quote limits bound some costs. Concurrent generation is serialized;
  a cancelled UI request may not interrupt native CPU inference.

## What is intentionally not claimed

No SIEM replacement, automatic threat detection, incident verdicts, native PCAP
analysis, high-volume telemetry ingestion, persistent vector database, hybrid
fusion, semantic reranking, multilingual evaluation, fine-tuning or production
security. Semantic top-k cannot answer counts or complete timelines. Use the separate
structured analytics panel for record counts, never inferred attempt/incident counts.

### Explicit IP constraints

Lexical and semantic retrieval now require every valid, standalone IPv4/IPv6
literal in a query to occur in each candidate event before top-k selection.
IPv6 spellings are canonicalized. An absent address yields no evidence rather
than a similar event for a different address. Similarity thresholds still apply.

This is a narrow safety check, not a query language: several addresses mean AND
within one event, so OR queries and cross-event questions can miss relevant
results. Negation, CIDRs, ranges, IP:port pairs and usernames are not interpreted.
Use positive questions about standalone addresses. A matching IP does not make
an event relevant or prove an incident. Account names still need manual review.

The bounded local 1.0 milestone is complete. Broader adapters, independently
labeled evaluation and public-product hardening remain explicit future scope,
not shipped claims. See [acceptance and honest quality results](docs/QUALITY.md).
The separate 40-case synthetic regression exposes BGE misses (23/32 answerable
hit@1 at .7 versus lexical 32/32); both abstained on 8/8 absent-IP cases.
Do not generalize the tiny demo's perfect semantic result to other logs.

## Model and tool references

- [BGE model card](https://huggingface.co/BAAI/bge-small-en-v1.5), including its
  warning about absolute similarity scores.
- [Qwen GGUF model card](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF).
- [llama-cpp-python CPU wheel index](https://abetlen.github.io/llama-cpp-python/whl/cpu/llama-cpp-python/).

Model weights retain their own licenses and are downloaded separately. No model
weights or private logs should be committed to GitHub.
