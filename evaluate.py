"""Small labeled synthetic retrieval smoke evaluation, not a production benchmark."""
import json
from pathlib import Path
from retrieval import read_records
from semantic import SemanticIndex

CASES = [
    ('Multiple unsuccessful remote shell authentications', 'AUTH-002'),
    ('A successful SSH login following repeated failures', 'AUTH-003'),
    ('Which DNS domain was requested?', 'DNS-001'),
    ('TCP connection attempts to many destination ports', 'NET-001'),
    ('Did the scheduled backup finish without errors?', 'SAFE-001'),
]


def main():
    index = SemanticIndex(read_records(Path(__file__).with_name('demo.jsonl')))
    rows = []
    try:
        for query, expected in CASES:
            result = index.search(query, min_score=0)
            ids = [e['event_id'] for e in result['evidence']]
            rows.append({'query': query, 'expected': expected, 'top_ids': ids,
                         'hit_at_1': bool(ids and ids[0] == expected), 'hit_at_3': expected in ids})
        print(json.dumps({'model': 'BAAI/bge-small-en-v1.5', 'cases': rows,
                          'hit_at_1': sum(r['hit_at_1'] for r in rows),
                          'hit_at_3': sum(r['hit_at_3'] for r in rows), 'total': len(rows),
                          'limit': 'Five hand-written queries over seven synthetic events. Not held-out or representative of real incident logs.'}, indent=2))
    finally:
        index.close()


if __name__ == '__main__':
    main()
