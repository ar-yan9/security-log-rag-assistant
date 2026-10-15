"""Reproducible retrieval evaluation on labeled synthetic cases, not a security benchmark."""
import argparse
import json
from pathlib import Path
from retrieval import EvidenceIndex, read_records

ROOT = Path(__file__).resolve().parent
DEFAULT_CASES = ROOT / 'examples' / 'evaluation-cases.json'
LIMITATION = ('Hand-written synthetic queries over seven demo events, created after the demo. '
              'Not held out, not representative of production logs, and not a test of LLM '
              'answer correctness, prompt-injection safety, or incident detection. '
              'An empty expected_ids list means no event is labeled relevant, not that no incident occurred.')


def read_cases(path, corpus_ids):
    """Reject ambiguous labels before reporting any metrics."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, list) or not data or len(data) > 1000:
        raise ValueError('Cases must be a nonempty list of at most 1000 items')
    seen = set()
    for row in data:
        if not isinstance(row, dict) or set(row) != {'id', 'query', 'expected_ids'}:
            raise ValueError('Each case needs id, query and expected_ids only')
        case_id, query, expected = row['id'], row['query'], row['expected_ids']
        if not isinstance(case_id, str) or not case_id.strip() or case_id in seen:
            raise ValueError('Case IDs must be unique nonempty strings')
        seen.add(case_id)
        if not isinstance(query, str) or not query.strip() or len(query) > 1000:
            raise ValueError('Case query must contain 1-1000 characters')
        if (not isinstance(expected, list) or any(not isinstance(x, str) for x in expected)
                or len(set(expected)) != len(expected) or not set(expected) <= corpus_ids):
            raise ValueError('Labels must be distinct IDs present in this corpus')
    return data


def evaluate(index, cases, limit=3, min_score=0.05):
    """Measure thresholded retrieval; missing results consume precision slots."""
    if type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError('limit must be an integer from 1 to 10')
    if not isinstance(min_score, (int, float)) or not 0 <= min_score <= 1:
        raise ValueError('min_score must be between 0 and 1')
    rows = []
    for case in cases:
        result = index.search(case['query'], limit=limit, min_score=min_score)
        ids = [e['event_id'] for e in result['evidence']]
        if len(ids) > limit or len(set(ids)) != len(ids):
            raise ValueError('Index returned duplicate IDs or more results than requested')
        relevant = set(case['expected_ids'])
        overlap = relevant.intersection(ids)
        row = {'id': case['id'], 'query': case['query'], 'expected_ids': case['expected_ids'],
               'retrieved_ids': ids, 'answerable': bool(relevant)}
        if relevant:
            row.update(hit_at_1=bool(ids and ids[0] in relevant), hit_at_k=bool(overlap),
                       recall_at_k=len(overlap) / len(relevant), precision_at_k=len(overlap) / limit,
                       reciprocal_rank=next((1 / rank for rank, event in enumerate(ids, 1)
                                             if event in relevant), 0.0))
        else:
            row['correct_abstention'] = not ids
        rows.append(row)
    positive = [r for r in rows if r['answerable']]
    negative = [r for r in rows if not r['answerable']]
    def mean(field):
        return sum(r[field] for r in positive) / len(positive) if positive else None
    summary = {field: mean(field) for field in
               ('hit_at_1', 'hit_at_k', 'recall_at_k', 'precision_at_k', 'reciprocal_rank')}
    summary.update(answerable_cases=len(positive), unanswerable_cases=len(negative),
                   correct_abstentions=sum(r['correct_abstention'] for r in negative),
                   false_evidence_rate=(sum(not r['correct_abstention'] for r in negative) / len(negative)
                                        if negative else None))
    return {'configuration': {'k': limit, 'minimum_similarity': min_score},
            'summary': summary, 'cases': rows, 'limitation': LIMITATION}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('lexical', 'semantic'), default='semantic')
    parser.add_argument('--file', type=Path, default=ROOT / 'demo.jsonl')
    parser.add_argument('--cases', type=Path, default=DEFAULT_CASES)
    parser.add_argument('--limit', type=int, choices=range(1, 11), default=3)
    parser.add_argument('--min-score', type=float, help='Defaults: lexical 0.05; semantic 0.7 (same as app)')
    args = parser.parse_args(argv)
    index = None
    try:
        records = read_records(args.file)
        cases = read_cases(args.cases, {r['id'] for r in records})
        threshold = args.min_score if args.min_score is not None else (0.7 if args.mode == 'semantic' else 0.05)
        if not 0 <= threshold <= 1:
            raise ValueError('min-score must be between 0 and 1')
        if args.mode == 'semantic':
            from semantic import SemanticIndex, MODEL
            index = SemanticIndex(records)
            model = MODEL
        else:
            index = EvidenceIndex(records)
            model = 'TF-IDF lexical baseline'
        report = evaluate(index, cases, args.limit, threshold)
        report.update(mode=args.mode, model=model, corpus_events=len(records))
        print(json.dumps(report, indent=2, allow_nan=False))
        # A completed evaluation is not a passing quality gate. Inspect its metrics.
        return 0
    except (OSError, ValueError, UnicodeError, ImportError, RuntimeError) as exc:
        parser.exit(2, f'Evaluation stopped: {exc}\n')
    finally:
        if index is not None:
            index.close()


if __name__ == '__main__':
    raise SystemExit(main())
