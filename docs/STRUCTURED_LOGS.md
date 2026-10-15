# Whole-corpus analytics

The query/search path returns top-k similar evidence. It must not count incidents,
construct complete timelines or infer how many failures happened. Analytics is
separate: every input JSONL record is considered, no embeddings/LLM needed.

Optional explicit metadata:

```json
{"id":"LAB-001","text":"Synthetic SSH failure from 192.0.2.10","fields":{"timestamp":"2026-01-01T00:00:00Z","service":"ssh","outcome":"failure","source_ip":"192.0.2.10"}}
```

`id`/`text` remain required. `fields` is optional, with only `timestamp`, `service`,
`outcome`, `source_ip`. Strings are 1-100 characters. Timestamps need ISO-8601 and
an explicit offset, converted to UTC. IPv4/IPv6 addresses are validated and
canonicalized. Invalid metadata stops ingestion instead of silently guessing.
Unknown outer fields are ignored. The plain-text normalizer does not invent
these fields. An owner-supplied adapter/schema mapping is needed for real logs.

Use the UI section **Count records. Keep the sources.** Leave filters blank for
all records, or use exact case-sensitive service/outcome values and an exact IP.
Time range is start-inclusive and end-exclusive. Missing timestamps are excluded
when time bounds are present. Missing metadata otherwise appears as `(unknown)`.
Undated records appear last, not at an invented date. Export includes every
matched source row; UI pages contain 20 rows each.

Example local API (server running, authorized synthetic data only):

```powershell
$body = @{service='ssh';outcome='failure'} | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/analytics -Method Post -ContentType application/json -Body $body
```

The demo labels two records as SSH failure. One says "five failures" in its text.
Analytics correctly counts **two records**, not six attempts or two incidents.
Metadata is supplied by the author and is not verified against the prose. These
are bookkeeping summaries of input, not threat detection. No "most malicious
host" or severity ranking is inferred. Duplicate IDs are rejected on ingestion.

Data remains local but is not automatically redacted. Exports can contain raw
private logs. Do not commit or share them without permission. Source data must
not change during an investigation: search indexes are loaded once and analytics
reads the configured file per request. Restart after any corpus change so the
views refer to the same source version.
