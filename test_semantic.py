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
