"""Golden checks: the shipped examples must ingest to the shipped expected output.

Any adapter behavior change updates these files deliberately, never silently.
"""
from pathlib import Path

from ingest import ingest

EXAMPLES = Path(__file__).parent / 'examples'


def golden(path):
    # Windows checkouts may carry CRLF; the content contract is newline-agnostic.
    return path.read_text(encoding='utf-8').replace('\r\n', '\n')


def test_sample_auth_log_matches_golden(tmp_path):
    dest = tmp_path / 'auth.jsonl'
    summary = ingest(EXAMPLES / 'sample-auth.log', dest, prefix='AUTH',
                     year=2026, utc_offset='+05:30')
    assert summary == {'records': 8, 'dated': 7, 'addressed': 5}
    assert dest.read_text(encoding='utf-8') == golden(EXAMPLES / 'expected-auth.jsonl')


def test_sample_access_log_matches_golden(tmp_path):
    dest = tmp_path / 'access.jsonl'
    summary = ingest(EXAMPLES / 'sample-access.log', dest, prefix='WEB')
    assert summary == {'records': 4, 'dated': 4, 'addressed': 3}
    assert dest.read_text(encoding='utf-8') == golden(EXAMPLES / 'expected-access.jsonl')


def test_golden_output_feeds_analytics():
    from analytics import summarize
    from retrieval import read_records
    rows = read_records(EXAMPLES / 'expected-auth.jsonl')
    result = summarize(rows, service='sshd', outcome='failure', source_ip='192.0.2.10')
    assert result['matching_records'] == 3
    # The preauth close line has no outcome and the CRON line is not sshd, so
    # neither inflates the failure count; the unstructured line has no fields.
    assert result['structured_records'] == 7
    assert result['corpus_records'] == 8
def test_sample_gateway_log_matches_golden(tmp_path):
    dest = tmp_path / 'gateway.jsonl'
    # No --year/--utc-offset: RFC3164 records must stay undated end to end.
    summary = ingest(EXAMPLES / 'sample-gateway.log', dest, prefix='GW')
    assert summary == {'records': 8, 'dated': 0, 'addressed': 3}
    assert dest.read_text(encoding='utf-8') == golden(EXAMPLES / 'expected-gateway.jsonl')


def test_golden_gateway_output_feeds_analytics():
    from analytics import summarize
    from retrieval import read_records
    rows = read_records(EXAMPLES / 'expected-gateway.jsonl')
    result = summarize(rows, source_ip='2001:db8::10')
    assert result['matching_records'] == 2
    # Only the failure line counts for that address; the preauth error line has
    # no outcome, and the UFW SRC= field is never treated as a source address.
    failed = summarize(rows, outcome='failure', source_ip='2001:db8::10')
    assert failed['matching_records'] == 1
    assert result['corpus_records'] == 8
