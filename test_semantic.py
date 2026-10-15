"""Optional real-model integration tests. Excluded from offline CI by default."""
import os
from pathlib import Path
import pytest

pytestmark = pytest.mark.skipif(os.getenv('RUN_MODEL_TESTS') != '1', reason='Explicit opt-in for public model download')


def test_real_bge_retrieves_paraphrase_and_keeps_evidence():
    from semantic import SemanticIndex
    from retrieval import read_records
    index = SemanticIndex(read_records(Path(__file__).with_name('demo.jsonl')))
    try:
        result = index.search('Multiple unsuccessful remote shell authentications')
        assert result['evidence'][0]['event_id'] == 'AUTH-002'
        assert result['evidence'][0]['source_line'] == 2
        assert index.search('quantum pineapple tractor recipe')['evidence'] == []
        with pytest.raises(ValueError):
            index.search(' ')
    finally:
        index.close()


def test_real_bge_exact_ip_filter_before_limit_and_ipv6():
    from semantic import SemanticIndex
    rows = [
        {'id':'wrong','text':'SSH repeated login failures from 203.0.113.90','line':1},
        {'id':'right','text':'SSH failure from 203.0.113.9','line':2},
        {'id':'v6','text':'SSH failure from 2001:db8::1','line':3},
    ]
    index = SemanticIndex(rows)
    try:
        assert index.search('SSH repeated login failures 203.0.113.9', limit=1, min_score=0)['evidence'][0]['event_id'] == 'right'
        assert index.search('SSH login failures 203.0.113.99')['evidence'] == []
        assert index.search('SSH [2001:0db8:0:0:0:0:0:1]', min_score=0)['evidence'][0]['event_id'] == 'v6'
        assert index.search('203.0.113.9 and 2001:db8::1', min_score=0)['evidence'] == []
    finally:
        index.close()
