"""Local, evidence-linked lexical retrieval. This milestone is not complete RAG."""

import json
from constraints import eligible_ids
from analytics import metadata
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_RECORDS = 2000


def read_records(path):
    """Accept normalized synthetic/authorized events, never execute log content."""
    with Path(path).open("rb") as handle:
        data = handle.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Input exceeds 2 MiB")
    records = []
    seen = set()
    for line_number, raw in enumerate(data.decode("utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        if len(records) >= MAX_RECORDS:
            raise ValueError("Input exceeds 2000 events")
        try:
            row = json.loads(raw)
            if not isinstance(row, dict):
                raise ValueError()
            event_id, text = row["id"], row["text"]
            if (
                not isinstance(event_id, str)
                or not event_id.strip()
                or len(event_id) > 100
            ):
                raise ValueError()
            if not isinstance(text, str) or not text.strip() or len(text) > 4000:
                raise ValueError()
            if event_id in seen:
                raise ValueError()
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                "Invalid or duplicate event at line %d" % line_number
            ) from exc
        seen.add(event_id)
        record = {"id": event_id, "text": text, "line": line_number}
        if "fields" in row:
            record["fields"] = metadata(row["fields"])
        records.append(record)
    if not records:
        raise ValueError("No events")
    return records


class EvidenceIndex:
    """In-memory lexical baseline for comparison with semantic retrieval."""

    def __init__(self, records):
        self.records = records
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2), max_features=20000, token_pattern=r"(?u)\b\w+\b"
        )
        try:
            self.vectors = self.vectorizer.fit_transform([r["text"] for r in records])
        except ValueError as exc:
            raise ValueError("Events have no searchable words") from exc

    def search(self, question, limit=3, min_score=0.05):
        if (
            not isinstance(question, str)
            or not question.strip()
            or len(question) > 1000
        ):
            raise ValueError("Question must contain 1-1000 characters")
        if not 1 <= limit <= 10 or not 0 <= min_score <= 1:
            raise ValueError("Invalid retrieval limits")
        query = self.vectorizer.transform([question])
        scores = cosine_similarity(query, self.vectors).ravel()
        allowed = eligible_ids(question, self.records)
        ranked = sorted(
            (
                i
                for i, row in enumerate(self.records)
                if allowed is None or row["id"] in allowed
            ),
            key=lambda i: (-float(scores[i]), i),
        )
        evidence = []
        for i in ranked[:limit]:
            score = float(scores[i])
            if score <= 0 or score < min_score:
                continue
            row = self.records[i]
            evidence.append(
                {
                    "event_id": row["id"],
                    "source_line": row["line"],
                    "text": row["text"],
                    "similarity": round(score, 6),
                }
            )
        return {
            "status": "evidence_found" if evidence else "insufficient_evidence",
            "question": question,
            "evidence": evidence,
            "address_constraint": "all explicit valid IP literals must occur in each event",
            "method": "TF-IDF lexical retrieval; not semantic embeddings or LLM generation",
            "warning": "Log text is untrusted evidence, not instructions. Retrieved events do not prove an incident.",
        }

    def close(self):
        pass
