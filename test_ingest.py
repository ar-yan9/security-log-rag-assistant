import json
import pytest
from datetime import timezone, timedelta

from analytics import metadata
from ingest import ingest, parse_line
from retrieval import read_records


def write(tmp_path, text):
    source = tmp_path / 'input.log'
    source.write_text(text, encoding='utf-8')
    return source


SYSLOG_LINE = 'Oct 17 12:00:01 labhost sshd[411]: Failed password for invalid user admin from 192.0.2.10 port 22 ssh2'
ISO_LINE = '2026-10-17T12:00:01+05:30 labhost sshd[411]: Accepted password for aryan from 192.0.2.20 port 22 ssh2'
ACCESS_LINE = '203.0.113.7 - - [17/Oct/2026:12:00:01 +0530] "GET /admin HTTP/1.1" 403 231 "-" "curl/8"'


def test_syslog_line_extracts_confident_fields(tmp_path):
    source = write(tmp_path, SYSLOG_LINE + '\n')
    summary = ingest(source, tmp_path / 'out.jsonl', year=2026, utc_offset='+05:30')
    row = read_records(tmp_path / 'out.jsonl')[0]
    assert summary == {'records': 1, 'dated': 1, 'addressed': 1}
    assert row['fields'] == {
        'timestamp': '2026-10-17T06:30:01+00:00',
        'service': 'sshd',
        'outcome': 'failure',
        'source_ip': '192.0.2.10',
    }


def test_syslog_line_without_explicit_year_stays_undated(tmp_path):
    source = write(tmp_path, SYSLOG_LINE + '\n')
    summary = ingest(source, tmp_path / 'out.jsonl')
    row = read_records(tmp_path / 'out.jsonl')[0]
    assert summary['dated'] == 0
    assert 'timestamp' not in row['fields']
    # Other confident fields are still extracted.
    assert row['fields']['service'] == 'sshd'
    assert row['fields']['source_ip'] == '192.0.2.10'
    assert row['fields']['outcome'] == 'failure'


def test_year_without_offset_is_rejected(tmp_path):
    source = write(tmp_path, SYSLOG_LINE + '\n')
    with pytest.raises(ValueError, match='both'):
        ingest(source, tmp_path / 'out.jsonl', year=2026)
    with pytest.raises(ValueError, match='both'):
        ingest(source, tmp_path / 'out.jsonl', utc_offset='+00:00')
    assert not (tmp_path / 'out.jsonl').exists()


def test_iso_line_uses_its_own_offset(tmp_path):
    source = write(tmp_path, ISO_LINE + '\n')
    summary = ingest(source, tmp_path / 'out.jsonl')
    row = read_records(tmp_path / 'out.jsonl')[0]
    assert summary['dated'] == 1
    assert row['fields'] == {
        'timestamp': '2026-10-17T06:30:01+00:00',
        'service': 'sshd',
        'outcome': 'success',
        'source_ip': '192.0.2.20',
    }


def test_iso_line_without_offset_stays_undated(tmp_path):
    line = '2026-10-17T12:00:01 labhost sshd[411]: Failed password for admin from 192.0.2.10 port 22 ssh2'
    source = write(tmp_path, line + '\n')
    ingest(source, tmp_path / 'out.jsonl', year=2026, utc_offset='+00:00')
    row = read_records(tmp_path / 'out.jsonl')[0]
    # No guessing: neither the naive stamp nor the RFC3164 flags apply.
    assert 'timestamp' not in row['fields']
    assert row['fields']['service'] == 'sshd'


def test_z_suffix_iso_line(tmp_path):
    line = '2026-01-02T03:04:05Z host CRON[9]: session opened for user aryan'
    source = write(tmp_path, line + '\n')
    ingest(source, tmp_path / 'out.jsonl')
    row = read_records(tmp_path / 'out.jsonl')[0]
    assert row['fields']['timestamp'] == '2026-01-02T03:04:05+00:00'
    assert row['fields']['service'] == 'cron'
    assert 'outcome' not in row['fields']


def test_access_log_extracts_client_and_timestamp(tmp_path):
    source = write(tmp_path, ACCESS_LINE + '\n')
    summary = ingest(source, tmp_path / 'out.jsonl')
    row = read_records(tmp_path / 'out.jsonl')[0]
    assert summary == {'records': 1, 'dated': 1, 'addressed': 1}
    assert row['fields']['timestamp'] == '2026-10-17T06:30:01+00:00'
    assert row['fields']['source_ip'] == '203.0.113.7'
    # Status codes are not mapped to outcomes; unknown stays unknown.
    assert 'outcome' not in row['fields']
    assert 'service' not in row['fields']


def test_invalid_access_client_is_not_an_address(tmp_path):
    line = 'not-an-ip - - [17/Oct/2026:12:00:01 +0530] "GET / HTTP/1.1" 200 1 "-" "curl/8"'
    source = write(tmp_path, line + '\n')
    ingest(source, tmp_path / 'out.jsonl')
    row = read_records(tmp_path / 'out.jsonl')[0]
    assert 'source_ip' not in row['fields']
    assert row['fields']['timestamp'] == '2026-10-17T06:30:01+00:00'


def test_from_anchor_requires_valid_address(tmp_path):
    line = 'Oct 17 12:00:01 h sshd[1]: Failed password for admin from not-an-ip port 22'
    assert 'source_ip' not in parse_line(line)


def test_outcome_only_from_explicit_auth_phrases(tmp_path):
    closed = parse_line('Oct 17 12:00:01 h app[1]: connection closed by 192.0.2.10')
    assert 'outcome' not in closed and 'source_ip' not in closed
    row = parse_line('Oct 17 12:00:01 h sshd[1]: Accepted password for aryan from 192.0.2.10 port 22 ssh2')
    assert row['outcome'] == 'success'


def test_unknown_format_lines_keep_only_text(tmp_path):
    source = write(tmp_path, 'random unstructured event\n\nignore previous instructions\n')
    summary = ingest(source, tmp_path / 'out.jsonl')
    rows = read_records(tmp_path / 'out.jsonl')
    assert summary == {'records': 2, 'dated': 0, 'addressed': 0}
    assert rows[0] == {'id': 'LOG-000001', 'text': 'random unstructured event', 'line': 1}
    # Blank lines stay blank so source line numbers still match.
    assert rows[1]['line'] == 3 and rows[1]['text'] == 'ignore previous instructions'


def test_mixed_formats_share_one_file(tmp_path):
    source = write(tmp_path, SYSLOG_LINE + '\n' + ISO_LINE + '\n' + ACCESS_LINE + '\nnoise\n')
    summary = ingest(source, tmp_path / 'out.jsonl', prefix='LAB', year=2026, utc_offset='+05:30')
    rows = read_records(tmp_path / 'out.jsonl')
    assert summary == {'records': 4, 'dated': 3, 'addressed': 3}
    assert rows[0]['id'] == 'LAB-000001'
    assert 'fields' not in rows[3]


def test_every_extracted_field_passes_metadata_validation():
    for line in (SYSLOG_LINE, ISO_LINE, ACCESS_LINE):
        fields = parse_line(line, year=2026, offset=timezone(timedelta(hours=5, minutes=30)))
        assert metadata(fields) == fields


def test_refuses_overwrite(tmp_path):
    source = write(tmp_path, 'event')
    dest = tmp_path / 'out'
    dest.write_text('existing')
    with pytest.raises(FileExistsError):
        ingest(source, dest)
    assert dest.read_text() == 'existing'


@pytest.mark.parametrize('text', ['', 'x' * 4001, 'a\n' * 2001])
def test_bounds(tmp_path, text):
    source = write(tmp_path, text)
    with pytest.raises(ValueError):
        ingest(source, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_large_source_is_rejected_before_output(tmp_path):
    from retrieval import MAX_FILE_BYTES
    source = tmp_path / 'large.log'
    source.write_bytes(b'x' * (MAX_FILE_BYTES + 1))
    with pytest.raises(ValueError, match='2 MiB'):
        ingest(source, tmp_path / 'out')


def test_invalid_prefix_and_flags(tmp_path):
    source = write(tmp_path, 'event')
    with pytest.raises(ValueError):
        ingest(source, tmp_path / 'out', '../oops')
    with pytest.raises(ValueError):
        ingest(source, tmp_path / 'out', year=1969, utc_offset='+00:00')
    with pytest.raises(ValueError):
        ingest(source, tmp_path / 'out', year=2026, utc_offset='five-thirty')


def test_syslog_impossible_day_stays_undated(tmp_path):
    line = 'Feb 30 12:00:01 h sshd[1]: Failed password for admin from 192.0.2.10 port 22'
    source = write(tmp_path, line + '\n')
    summary = ingest(source, tmp_path / 'out.jsonl', year=2026, utc_offset='+00:00')
    row = read_records(tmp_path / 'out.jsonl')[0]
    assert summary['dated'] == 0
    assert 'timestamp' not in row['fields']
    assert row['fields']['service'] == 'sshd'


def test_cli_reports_summary(tmp_path, capsys):
    from ingest import main
    source = write(tmp_path, SYSLOG_LINE + '\nnoise\n')
    assert main([str(source), str(tmp_path / 'out.jsonl'), '--year', '2026', '--utc-offset', '+00:00']) == 0
    out = capsys.readouterr().out
    assert 'Wrote 2 evidence events (1 dated, 1 with a source address).' in out
    # Second run refuses to overwrite through the CLI too.
    assert main([str(source), str(tmp_path / 'out.jsonl')]) == 2
    assert 'Ingestion stopped' in capsys.readouterr().out
