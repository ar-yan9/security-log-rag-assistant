"""Generate a separate synthetic retrieval regression, not held-out validation.

Deterministic fabricated documentation addresses and accounts. No real telemetry.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "examples"


def main():
    events = []
    cases = []
    services = [
        ("ssh", "authentication failure", "remote shell login was denied"),
        ("dns", "DNS query demo.test", "a domain lookup was requested"),
        (
            "backup",
            "backup completed successfully",
            "scheduled archive finished without errors",
        ),
        ("http", "HTTP 403 forbidden", "web access was refused"),
    ]
    for i in range(1, 33):
        service, text, query = services[(i - 1) % 4]
        ip = f"192.0.2.{i}"
        id = f"REG-{i:03d}"
        events.append(
            {
                "id": id,
                "text": f"Synthetic regression: {text} from {ip}; account lab-user-{i}.",
                "fields": {"service": service, "source_ip": ip},
            }
        )
        cases.append(
            {
                "id": f"positive-{i:03d}",
                "query": f"For {ip}, {query}?",
                "expected_ids": [id],
            }
        )
    for i in range(1, 9):
        cases.append(
            {
                "id": f"absent-{i:03d}",
                "query": f"What authentication failure came from 203.0.113.{i}?",
                "expected_ids": [],
            }
        )
    for p, value in [
        (
            ROOT / "regression-events.jsonl",
            "".join(json.dumps(x) + "\n" for x in events),
        ),
        (ROOT / "regression-cases.json", json.dumps(cases, indent=2) + "\n"),
    ]:
        p.write_text(value, encoding="utf-8")


if __name__ == "__main__":
    main()
