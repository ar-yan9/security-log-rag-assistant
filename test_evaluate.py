"""Offline metric/label checks. No model download or production-quality claims."""
import json
import pytest
from evaluate import DEFAULT_CASES, evaluate, main, read_cases
from retrieval import EvidenceIndex, read_records
from pathlib import Path


class FakeIndex:
    def search(self, question, limit, min_score):
        ids = {'multi': ['wrong', 'A', 'B'], 'miss': [], 'absent': [], 'false': ['C']}[question]
        return {'evidence': [{'event_id': x} for x in ids[:limit]]}


def case(query, ids):
    return {'id': query, 'query': query, 'expected_ids': ids}


def test_metrics_include_multi_relevance_misses_and_false_evidence():
    result = evaluate(FakeIndex(), [case('multi', ['A','B']), case('miss', ['C']),
                                   case('absent', []), case('false', [])])
    s = result['summary']
    assert s['hit_at_1'] == 0
    assert s['hit_at_k'] == 0.5
    assert s['recall_at_k'] == 0.5
    assert s['precision_at_k'] == pytest.approx(1/3)
    assert s['reciprocal_rank'] == 0.25
    assert s['correct_abstentions'] == 1
    assert s['false_evidence_rate'] == 0.5
    assert 'Not held out' in result['limitation']


def test_undefined_metrics_are_null_not_perfect():
    assert evaluate(FakeIndex(), [case('absent', [])])['summary']['hit_at_1'] is None
    assert evaluate(FakeIndex(), [case('multi', ['A'])])['summary']['false_evidence_rate'] is None


@pytest.mark.parametrize('rows', [[], {}, [case('x', ['UNKNOWN'])], [case('x',['A','A'])],
                                      [case('x', 'A')], [case('x', [2])],
                                      [case('x', []), case('x', [])],
                                      [{'id':'x','query':' ','expected_ids':[]}],
                                      [{'id':'x','query':'ok'}]])
def test_invalid_labels_rejected(tmp_path, rows):
    path = tmp_path/'cases.json'
    path.write_text(json.dumps(rows))
    with pytest.raises(ValueError):
        read_cases(path, {'A'})


def test_fixture_matches_actual_corpus():
    records = read_records(Path(__file__).with_name('demo.jsonl'))
    cases = read_cases(DEFAULT_CASES, {r['id'] for r in records})
    assert len(cases) == 14
    index = EvidenceIndex(records)
    try:
        result = evaluate(index, cases)
        assert result['summary']['answerable_cases'] == 10
        assert result['summary']['unanswerable_cases'] == 4
        # Near-match text can retrieve irrelevant events; expose rather than hide it.
        assert result['cases'][-1]['correct_abstention'] is False
    finally:
        index.close()


def test_cli_lexical_report_is_json(capsys):
    assert main(['--mode','lexical']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['mode'] == 'lexical'
    assert result['configuration'] == {'k':3, 'minimum_similarity':0.05}


@pytest.mark.parametrize('limit,score', [(0,.1),(11,.1),(True,.1),(3,-.1),(3,1.1),(3,float('nan'))])
def test_invalid_configuration(limit,score):
    with pytest.raises(ValueError):
        evaluate(FakeIndex(), [], limit=limit, min_score=score)
