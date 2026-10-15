"""Convert a bounded UTF-8 text log to one evidence event per source line.

No year/timezone guessing, incident classification, or shell execution. Source
line and raw text are preserved. Blank lines stay blank so JSONL source line
numbers still match the original text file. This is not a PCAP parser.
"""
import argparse
import json
from pathlib import Path
import re
from retrieval import MAX_FILE_BYTES, MAX_RECORDS


def normalize(source, destination, prefix='LOG'):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', prefix):
        raise ValueError('Prefix must contain 1-40 letters, numbers, underscores or dashes')
    with Path(source).open('rb') as handle:
        data = handle.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError('Input exceeds 2 MiB')
    lines = data.decode('utf-8').splitlines()
    nonempty = [text for text in lines if text.strip()]
    if not nonempty or len(nonempty) > MAX_RECORDS or any(len(text) > 4000 for text in nonempty):
        raise ValueError('Input must have 1-2000 nonempty lines, each at most 4000 characters')
    rows = [json.dumps({'id': f'{prefix}-{i:06d}', 'text': text}, ensure_ascii=True) if text.strip() else ''
            for i, text in enumerate(lines, 1)]
    content = '\n'.join(rows) + '\n'
    if len(content.encode('utf-8')) > MAX_FILE_BYTES:
        raise ValueError('Normalized output exceeds 2 MiB; use a smaller input')
    # Exclusive creation avoids accidental overwrite of an existing/private file.
    with Path(destination).open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(content)
    return len(nonempty)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('destination')
    parser.add_argument('--prefix', default='LOG')
    args = parser.parse_args(argv)
    try:
        count = normalize(args.source, args.destination, args.prefix)
        print(f'Wrote {count} evidence events. Review locally before indexing.')
        return 0
    except (OSError, ValueError, UnicodeError) as exc:
        print(f'Normalization stopped: {exc}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
