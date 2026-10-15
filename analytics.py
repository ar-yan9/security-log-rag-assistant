"""Deterministic whole-corpus summaries of explicit structured fields, never top-k.

Metadata is supplied by the corpus author, not inferred from arbitrary prose.
One row counts as one record, not one login attempt. Unknown fields stay unknown.
"""

import ipaddress
from datetime import datetime, timezone
from collections import Counter

FIELDS = {"timestamp", "service", "outcome", "source_ip"}


def metadata(value):
    if value is None:
        return {}
    if not isinstance(value, dict) or set(value) - FIELDS:
        raise ValueError("Invalid structured fields")
    result = {}
    for key, item in value.items():
        if not isinstance(item, str) or not item.strip() or len(item) > 100:
            raise ValueError("Invalid structured value")
        if key == "timestamp":
            try:
                stamp = datetime.fromisoformat(item.replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    raise ValueError()
            except ValueError as exc:
                raise ValueError(
                    "Timestamp needs ISO-8601 and explicit offset"
                ) from exc
            item = stamp.astimezone(timezone.utc).isoformat()
        elif key == "source_ip":
            item = str(ipaddress.ip_address(item))
        result[key] = item
    return result


def summarize(
    records, service=None, outcome=None, source_ip=None, start=None, end=None
):
    if source_ip:
        source_ip = str(ipaddress.ip_address(source_ip))
    times = metadata({k: v for k, v in [("timestamp", start)] if v})
    lower = times.get("timestamp")
    upper = metadata({"timestamp": end}).get("timestamp") if end else None
    if lower and upper and lower >= upper:
        raise ValueError("Start must be before end")
    candidates = []
    for row in records:
        fields = row.get("fields", {})
        if any(
            value and fields.get(key) != value
            for key, value in [
                ("service", service),
                ("outcome", outcome),
                ("source_ip", source_ip),
            ]
        ):
            continue
        ts = fields.get("timestamp")
        if (lower or upper) and not ts:
            continue
        if lower and ts < lower or upper and ts >= upper:
            continue
        candidates.append(row)

    def counts(key):
        c = Counter(r.get("fields", {}).get(key, "(unknown)") for r in candidates)
        return [
            {"value": k, "records": v}
            for k, v in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))
        ]

    rows = sorted(
        candidates,
        key=lambda r: (
            not bool(r.get("fields", {}).get("timestamp")),
            r.get("fields", {}).get("timestamp", ""),
            r["line"],
        ),
    )
    return {
        "status": "analytics_ready",
        "corpus_records": len(records),
        "matching_records": len(rows),
        "structured_records": sum(bool(r.get("fields")) for r in records),
        "filters": {
            "service": service,
            "outcome": outcome,
            "source_ip": source_ip,
            "start_inclusive": lower,
            "end_exclusive": upper,
        },
        "by_service": counts("service"),
        "by_outcome": counts("outcome"),
        "by_source_ip": counts("source_ip"),
        "timeline": [
            {
                "event_id": r["id"],
                "source_line": r["line"],
                "timestamp": r.get("fields", {}).get("timestamp"),
                "text": r["text"],
            }
            for r in rows
        ],
        "warning": "Counts are input records, not inferred incidents or login attempts. Structured metadata is author-supplied, not verified against prose. Missing fields are unknown. Time filters exclude undated rows; all matched source rows are returned. No LLM or top-k sampling.",
    }
