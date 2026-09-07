"""Failure-inclusive measurements and fixed source restrictions for the benchmark."""
from copy import deepcopy
from pathlib import Path
import json
import shutil

import pytest

from scripts_evolve import loan_retrieval_benchmark as bench

ROOT = Path(__file__).resolve().parents[1]


def test_scope_excludes_reserved_self_and_linked_sources():
    documents = [{'doc_id': doc, 'domain': 'us_loan', 'component_id': group,
                  'allocation': allocation, 'status': 'success'}
                 for doc, group, allocation in [
                     ('q', 'g1', bench.DEVELOPMENT), ('linked', 'g1', bench.DEVELOPMENT),
                     ('ok', 'g2', bench.DEVELOPMENT), ('reserved', 'g3', 'evaluation_reserved')]]
    rows = [{'doc': r['doc_id'], 'chunk_id': r['doc_id'], 'text': 'event of default'} for r in documents]
    admitted = bench.admit_loan_pool(rows, documents)
    scoped = bench.query_loan_pool(admitted, documents, 'q')
    assert [r['doc'] for r in scoped] == ['ok']


def test_timed_pair_keeps_mismatch_and_alternates_execution_order():
    calls = []
    def fresh():
        calls.append('fresh')
        return [{'chunk_id': 'a'}]
    def prepared():
        calls.append('prepared')
        return [{'chunk_id': 'b'}]
    for alternate, expected in [(False, ['fresh', 'prepared']), (True, ['prepared', 'fresh'])]:
        calls.clear()
        row, result = bench.timed_pair(fresh, prepared, alternate)
        assert calls == expected
        assert not row['exact_match']
        assert row['prepared_mismatch_result'] == [{'chunk_id': 'b'}]
        assert result == [{'chunk_id': 'a'}]
        assert row['fresh_ns'] >= 0 and row['prepared_ns'] >= 0


@pytest.mark.parametrize('failed_arm', ['fresh', 'prepared'])
def test_arm_exceptions_keep_failure_and_run_the_other_arm(failed_arm):
    calls = []
    def arm(name):
        calls.append(name)
        if name == failed_arm:
            raise RuntimeError('controlled failure')
        return [{'chunk_id': name}]
    row, result = bench.timed_pair(lambda: arm('fresh'), lambda: arm('prepared'), False)
    assert calls == ['fresh', 'prepared']
    assert not row['exact_match']
    assert row['errors'][failed_arm]['type'] == 'RuntimeError'
    assert result == (None if failed_arm == 'fresh' else [{'chunk_id': 'fresh'}])


def test_summary_includes_cold_cost_and_failed_repetitions():
    observed = [{'fresh_ns': 100, 'prepared_ns': 30, 'exact_match': True, 'repeat_stable': True,
                 'exclusion_violations': 0},
                {'fresh_ns': 100, 'prepared_ns': 30, 'exact_match': False, 'repeat_stable': True,
                 'exclusion_violations': 1}]
    scores = bench.timing_summary(observed, [observed[0]], 80)
    assert scores['paired_retrievals'] == 2
    assert scores['exact_mismatches'] == 1
    assert scores['exclusion_violations'] == 1
    assert scores['prepared_first_pass_with_cold_ns'] == 110
    assert not scores['prepared_identical_pool_gate_passed']
    empty = bench.timing_summary([], [], 0)
    assert empty['fresh_p50_ns'] is None
    assert not empty['prepared_identical_pool_gate_passed']
    failed = {**observed[0], 'fresh_ns': 1, 'prepared_ns': 1, 'exact_match': False,
              'errors': {'prepared': {'type': 'RuntimeError'}}}
    scores = bench.timing_summary([observed[0], failed], [observed[0]], 0)
    assert scores['execution_error_arms'] == 1
    assert scores['fresh_p50_ns'] == 100
    assert scores['prepared_p50_ns'] == 30
    assert not scores['prepared_identical_pool_gate_passed']


def test_context_metrics_do_not_count_invisible_tags_as_keyword_support():
    taxonomy = {'A': {'keywords': ['default']}}
    rows = [{'chunk_id': 'p:w0', 'parent_chunk_id': 'p', 'text': 'default', 'tags': ['A']},
            {'chunk_id': 'p:w1', 'parent_chunk_id': 'p', 'text': 'unrelated', 'tags': ['A']}]
    frozen = deepcopy(rows)
    result = bench.context_metrics({'taxonomy': 'A'}, rows, taxonomy)
    assert result == {'returned_chunks': 2, 'unique_parents': 1, 'returned_characters': 16,
                      'literal_query_category_keyword_chunks': 1}
    assert rows == frozen


def test_window_identifier_changes_are_not_source_context_changes():
    original = [{'doc': 'd', 'chunk_id': 'p', 'text': 'default',
                 'source_start': 0, 'source_end': 7, 'score': 1.2}]
    window = [{**original[0], 'chunk_id': 'p:w0', 'score': 2.1}]
    assert original != window
    assert bench.visible_payload(original) == bench.visible_payload(window)
    window[0]['source_start'] = 1
    assert bench.visible_payload(original) != bench.visible_payload(window)


def test_existing_or_unscoped_output_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='new direct child'):
        bench.prepare_inputs(ROOT, tmp_path)
    with pytest.raises(ValueError, match='new direct child'):
        bench.prepare_inputs(ROOT, ROOT / bench.REFINEMENT)


def test_hash_seed_required_before_source_processing(monkeypatch):
    monkeypatch.delenv('PYTHONHASHSEED', raising=False)
    with pytest.raises(ValueError, match='PYTHONHASHSEED'):
        bench.prepare_inputs(ROOT, ROOT / 'research/not_created_retrieval_seed_test')


@pytest.mark.parametrize('corruption', [None, 'source', 'manifest', 'roster'])
def test_preparation_freezes_all_1000_or_rejects_corruption(monkeypatch, tmp_path, corruption):
    text = 'The borrower acknowledges that an Event of Default makes the loan due and payable.\n'
    source = tmp_path / 'fixture.txt'
    source.write_text(text, encoding='utf-8')
    source_sha = bench.sha256(source.read_bytes())
    documents = [{'doc_id': f'd{i:04}', 'domain': 'us_loan', 'component_id': f'g{i}',
                  'allocation': bench.DEVELOPMENT if i < 22 else 'evaluation_reserved',
                  'status': 'review' if i == 999 else 'success',
                  'source_path': 'fixture.txt', 'source_sha256': source_sha,
                  'text_path': 'fixture.txt', 'text_sha256': source_sha} for i in range(1000)]
    manifest_documents = deepcopy(documents)
    if corruption == 'manifest':
        manifest_documents[0]['component_id'] = 'substituted'
    values = {f'{bench.REFINEMENT}/manifest.json': {'documents': manifest_documents}}
    for method in bench.METHODS:
        values[f'{bench.REFINEMENT}/{method}_pool.json'] = {'chunks': [
            {'doc': 'd0000', 'chunk_id': 'p0', 'text': text, 'tags': ['LOAN-01']}]}
    parents = {}
    for name, value in values.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')
        parents[name] = bench.sha256(path.read_bytes())
    for name in ['loan_retrieval.py', 'loan_retrieval_benchmark.py', 'loan_reference.py',
                 'loan_reference_refinement.py', 'main_execution.py', 'main_preflight.py', 'full_corpus_v2.py']:
        destination = tmp_path / 'scripts_evolve' / name
        destination.parent.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / 'scripts_evolve' / name, destination)
    original = tmp_path / 'eval_US_loan/eval_loan.py'
    original.parent.mkdir()
    shutil.copyfile(ROOT / 'eval_US_loan/eval_loan.py', original)
    (tmp_path / 'research/loan_retrieval_refinement_plan.md').write_text('synthetic test plan')
    monkeypatch.setattr(bench, 'PARENTS', parents)
    monkeypatch.setattr(bench, 'INPUT_SHA256', {})
    monkeypatch.setattr(bench, 'load_inputs', lambda root: documents)
    monkeypatch.setenv('PYTHONHASHSEED', '0')
    if corruption == 'source':
        source.write_text('changed bytes', encoding='utf-8')
    if corruption == 'roster':
        documents.pop()
    output = tmp_path / 'research/benchmark'
    if corruption:
        with pytest.raises(ValueError):
            bench.prepare_inputs(tmp_path, output)
        assert not output.exists()
    else:
        retained, queries, pools, protocol = bench.prepare_inputs(tmp_path, output)
        assert len(retained) == len(queries) == 1000
        assert retained[-1]['status'] == 'review'
        assert protocol['queries_sha256'] == bench.digest(queries)
        assert all(len(p) == 1 for p in pools.values())
        assert (output / 'snapshot/scripts_evolve/loan_retrieval.py').read_bytes() == (
            ROOT / 'scripts_evolve/loan_retrieval.py').read_bytes()


@pytest.mark.parametrize('failure', [None, 'retrieve', 'constructor', 'fresh'])
def test_run_preserves_sources_without_queries_or_valid_input(monkeypatch, tmp_path, failure):
    documents = [{'doc_id': 'd1', 'domain': 'us_loan', 'status': 'success', 'component_id': 'g1',
                  'allocation': bench.DEVELOPMENT},
                 {'doc_id': 'd2', 'domain': 'us_loan', 'status': 'review', 'component_id': 'g2',
                  'allocation': 'evaluation_reserved'}]
    query = {'doc': 'd1', 'query_id': 'q1', 'taxonomy': 'LOAN-01',
             'retrieval_query': 'event of default', 'triggered_by': 'event of default'}
    monkeypatch.setattr(bench, 'prepare_inputs', lambda root, output: (documents, [query],
                        {method: [] for method in bench.METHODS}, {}))
    monkeypatch.setattr(bench, 'ROOT', ROOT)
    if failure:
        def broken(*args, **kwargs):
            raise RuntimeError('controlled prepared failure')
        if failure == 'retrieve':
            monkeypatch.setattr(bench.PreparedLoanRetriever, 'retrieve', broken)
        elif failure == 'constructor':
            monkeypatch.setattr(bench, 'PreparedLoanRetriever', broken)
        else:
            original_loader = bench.load_retrieval
            def fresh_failure(root):
                original = original_loader(root)
                original['retrieve'] = broken
                return original
            monkeypatch.setattr(bench, 'load_retrieval', fresh_failure)
    # Code loading uses the verified workspace; only generated artifacts use tmp_path.
    result = bench.benchmark(ROOT, tmp_path / 'result')
    assert len(result['documents']) == 2
    assert result['documents'][0]['queries'] == 1
    assert result['documents'][1]['queries'] == 0
    assert result['documents'][1]['status'] == 'review'
    assert result['all_queries'] == 1
    assert all(s['paired_retrievals'] == 3 for s in result['timing'].values())
    if failure:
        assert all(s['execution_error_arms'] == 3 for s in result['timing'].values())
        assert all(not s['prepared_identical_pool_gate_passed'] for s in result['timing'].values())
        saved = json.loads((tmp_path / 'result/query_results.json').read_text(encoding='utf-8'))
        arm = 'fresh' if failure == 'fresh' else 'prepared'
        assert all(o['errors'][arm]['type'] == 'RuntimeError'
                   for m in saved['queries'][0]['methods'].values() for o in m['observations'])
        if failure == 'constructor':
            prep = json.loads((tmp_path / 'result/preparations.json').read_text(encoding='utf-8'))
            assert all(p[0]['error']['type'] == 'RuntimeError' for p in prep.values())
