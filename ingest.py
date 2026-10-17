"""Ingest common real log formats into corpus JSONL with confident metadata only.

Supported line formats, detected per line:

- RFC3164 syslog: ``Oct 17 12:00:01 host sshd[123]: message``. This format
  carries no year or timezone, so timestamps are written only when the operator
  passes both --year and --utc-offset explicitly. Without them, records stay
  undated rather than borrowing a guessed date.
- ISO-8601 prefixed lines: ``2026-10-17T12:00:01+05:30 host service: message``.
  A timestamp without an explicit offset is not used; the record stays undated.
- Apache/Nginx combined access lines:
  ``192.0.2.10 - - [17/Oct/2026:12:00:01 +0530] "GET /admin HTTP/1.1" 403 231 ...``

Extraction is positional and conservative. source_ip comes only from the
access-log client field or a syslog ``from <address>`` anchor, outcome only
from explicit authentication phrases, and service only from a simple syslog
tag. Lines in any other format are preserved as plain text records with no
metadata: unknown stays unknown. Every extracted field is validated through
analytics.metadata before writing, so invalid values stop ingestion instead of
silently guessing. This is not a PCAP parser and runs no shell commands.
"""
import argparse
import json
import ipaddress
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

from analytics import metadata
from retrieval import MAX_FILE_BYTES, MAX_RECORDS

PREFIX = re.compile(r'[A-Za-z0-9_-]{1,40}')
SYSLOG = re.compile(
    r'^([A-Z][a-z]{2})\s+(\d{1,2}) (\d{2}):(\d{2}):(\d{2}) (\S+) ([^\s:\[]+)(?:\[\d+\])?: (.*)$'
)
ISO_LINE = re.compile(
    r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)(Z|[+-]\d{2}:?\d{2})? (\S+) ([^\s:\[]+)(?:\[\d+\])?: (.*)$'
)
ACCESS = re.compile(
    r'^(\S+) - \S+ \[([^\]]+)\] "[A-Z]+ [^"]*" \d{3} '
)
FROM_IP = re.compile(r'\bfrom (\S+)')
MONTHS = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12,
}
FAILURE_PHRASES = ('failed password', 'authentication failure')
SUCCESS_PHRASES = ('accepted password', 'authentication succeeded')
TAG = re.compile(r'^[A-Za-z0-9_.-]{1,40}$')


def _offset(value):
    if not re.fullmatch(r'[+-](\d{2}):?(\d{2})', value):
        raise ValueError('UTC offset must look like +05:30')
    hours, minutes = int(value[1:3]), int(value[-2:])
    if hours > 23 or minutes > 59:
        raise ValueError('UTC offset must look like +05:30')
    sign = 1 if value[0] == '+' else -1
    return timezone(sign * timedelta(hours=hours, minutes=minutes))


def _service(tag):
    if TAG.fullmatch(tag):
        return tag.lower()
    return None


def _outcome(message):
    lowered = message.lower()
    if any(phrase in lowered for phrase in FAILURE_PHRASES):
        return 'failure'
    if any(phrase in lowered for phrase in SUCCESS_PHRASES):
        return 'success'
    return None


def _from_address(message):
    match = FROM_IP.search(message)
    if not match:
        return None
    try:
        return str(ipaddress.ip_address(match.group(1)))
    except ValueError:
        return None


def parse_line(text, year=None, offset=None):
    """Return a fields dict for one line, possibly empty. Never raises."""
    fields = {}
    message = text
    match = ISO_LINE.match(text)
    if match:
        stamp, zone, _host, tag, message = match.groups()
        if zone:
            candidate = stamp + ('+00:00' if zone == 'Z' else zone)
            try:
                fields['timestamp'] = metadata(
                    {'timestamp': candidate.replace('Z', '+00:00')}
                )['timestamp']
            except ValueError:
                pass
        service = _service(tag)
        if service:
            fields['service'] = service
    else:
        match = SYSLOG.match(text)
        if match:
            month, day, hour, minute, second, _host, tag, message = match.groups()
            if year is not None and offset is not None:
                try:
                    stamp = datetime(
                        year, MONTHS[month], int(day), int(hour), int(minute), int(second),
                        tzinfo=offset,
                    )
                    fields['timestamp'] = metadata(
                        {'timestamp': stamp.isoformat()}
                    )['timestamp']
                except (ValueError, OverflowError):
                    pass
            service = _service(tag)
            if service:
                fields['service'] = service
        else:
            match = ACCESS.match(text)
            if match:
                client, stamp = match.groups()
                try:
                    fields['source_ip'] = str(ipaddress.ip_address(client))
                except ValueError:
                    pass
                try:
                    parsed = datetime.strptime(stamp, '%d/%b/%Y:%H:%M:%S %z')
                    fields['timestamp'] = metadata(
                        {'timestamp': parsed.isoformat()}
                    )['timestamp']
                except (ValueError, OverflowError):
                    pass
    if 'source_ip' not in fields:
        address = _from_address(message)
        if address:
            fields['source_ip'] = address
    outcome = _outcome(message)
    if outcome:
        fields['outcome'] = outcome
    # Final validation: any invalid extracted value stops ingestion loudly.
    return metadata(fields) if fields else {}


def ingest(source, destination, prefix='LOG', year=None, utc_offset=None):
    if not PREFIX.fullmatch(prefix):
        raise ValueError('Prefix must contain 1-40 letters, numbers, underscores or dashes')
    if (year is None) != (utc_offset is None):
        raise ValueError('RFC3164 dating needs both --year and --utc-offset')
    offset = _offset(utc_offset) if utc_offset else None
    if year is not None and not 1970 <= year <= 9999:
        raise ValueError('Year must be between 1970 and 9999')
    with Path(source).open('rb') as handle:
        data = handle.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError('Input exceeds 2 MiB')
    lines = data.decode('utf-8').splitlines()
    nonempty = [text for text in lines if text.strip()]
    if not nonempty or len(nonempty) > MAX_RECORDS or any(len(text) > 4000 for text in nonempty):
        raise ValueError('Input must have 1-2000 nonempty lines, each at most 4000 characters')
    rows = []
    dated = addressed = 0
    for i, text in enumerate(lines, 1):
        if not text.strip():
            rows.append('')
            continue
        fields = parse_line(text, year=year, offset=offset)
        dated += bool(fields.get('timestamp'))
        addressed += bool(fields.get('source_ip'))
        row = {'id': f'{prefix}-{i:06d}', 'text': text}
        if fields:
            row['fields'] = fields
        rows.append(json.dumps(row, ensure_ascii=True))
    content = '\n'.join(rows) + '\n'
    if len(content.encode('utf-8')) > MAX_FILE_BYTES:
        raise ValueError('Ingested output exceeds 2 MiB; use a smaller input')
    # Exclusive creation avoids accidental overwrite of an existing/private file.
    with Path(destination).open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(content)
    return {'records': len(nonempty), 'dated': dated, 'addressed': addressed}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('destination')
    parser.add_argument('--prefix', default='LOG')
    parser.add_argument('--year', type=int,
                        help='Explicit year for RFC3164 syslog lines, which carry none')
    parser.add_argument('--utc-offset',
                        help='Explicit offset for RFC3164 syslog lines, for example +05:30')
    args = parser.parse_args(argv)
    try:
        summary = ingest(args.source, args.destination, args.prefix, args.year, args.utc_offset)
        print(
            f"Wrote {summary['records']} evidence events "
            f"({summary['dated']} dated, {summary['addressed']} with a source address). "
            'Review locally before indexing.'
        )
        return 0
    except (OSError, ValueError, UnicodeError) as exc:
        print(f'Ingestion stopped: {exc}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
