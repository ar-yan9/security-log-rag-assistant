"""Optional real CPU-model integration; downloads weights only in model CI."""
import os
from pathlib import Path
import pytest

pytestmark = pytest.mark.skipif(not os.getenv('SMOKE_GGUF_MODEL'), reason='Requires an explicitly selected local GGUF model')


def test_real_generation_has_provenance_and_unrelated_query_abstains():
    from generation import LocalGenerator, answer
    from semantic import SemanticIndex
    from retrieval import read_records
    index=SemanticIndex(read_records(Path(__file__).with_name('demo.jsonl')))
    generator=LocalGenerator(os.environ['SMOKE_GGUF_MODEL'])
    try:
        result=answer(index,generator,'What DNS request occurred?')
        assert result['status']=='answer_ready'
        assert result['model_invoked'] is True
        assert any(f['event_id']=='DNS-001' for f in result['findings'])
        for f in result['findings']:
            event=next(e for e in result['evidence'] if e['event_id']==f['event_id'])
            assert f['quote'] in event['text']
        result=answer(index,generator,'What is the office lunch menu?')
        assert result['status']=='insufficient_evidence'
        assert not result['model_invoked']
    finally:
        generator.close()
        index.close()
