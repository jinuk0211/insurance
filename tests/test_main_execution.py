"""Main-cohort scheduling tests; no model or network calls."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts.pilot.client import ModelFailure, write_json
from scripts.pilot.codex_client import inference_request, request_id
from scripts_evolve import main_execution as main
from scripts_evolve.full_corpus_v2 import DOMAINS, sha256


@pytest.fixture
def inputs():
    documents, preflight = [], []
    for domain in DOMAINS:
        for i in range(2):
            row = dict(doc_id=f'{domain}-{i}', domain=domain, source_path=f'{domain}-{i}.txt',
                       source_sha256='a', text_path=f'{domain}-{i}.txt', text_sha256='a',
                       status='success', mechanical_issues=[], component_id=f'g{i}',
                       allocation=main.DEVELOPMENT if i == 0 else main.RESERVED)
            documents.append(row)
            preflight.append({k: row[k] for k in ('doc_id', 'domain', 'source_path',
                                                  'source_sha256', 'text_path', 'text_sha256')})
            preflight[-1].update(status='runtime_candidate', extraction_status='success',
                                 minimum_calls_if_current_ready_pipeline_completes=3,
                                 conditional_card_validation_calls=int(domain == 'us_card'))
    return documents, preflight


def test_order_and_full_denominator(inputs):
    documents, preflight = inputs
    preflight[0]['status'] = 'parser_unsupported'
    preflight[0]['minimum_calls_if_current_ready_pipeline_completes'] = 0
    rows = main.ordered_roster(documents[::-1], preflight[::-1], per_domain=2)
    assert [r['doc_id'] for r in rows] == [f'{d}-{i}' for i in range(2) for d in DOMAINS]
    assert rows[0]['preflight_status'] == 'parser_unsupported'
    assert rows[1]['maximum_calls'] == 4
    assert 'maximum_calls' not in documents[0]


@pytest.mark.parametrize('corruption', ['missing', 'duplicate', 'identity', 'text', 'allocation'])
def test_changed_roster_rejected(inputs, corruption):
    documents, preflight = deepcopy(inputs)
    if corruption == 'missing':
        preflight.pop()
    elif corruption == 'duplicate':
        documents[-1] = documents[-2]
    elif corruption == 'identity':
        preflight[0]['source_sha256'] = 'changed'
    elif corruption == 'text':
        preflight[0]['text_sha256'] = 'changed'
    else:
        documents[0]['allocation'] = 'test'
    with pytest.raises(ValueError):
        main.ordered_roster(documents, preflight, per_domain=2)


def test_reference_excludes_reserved_failed_self_and_group(inputs):
    documents, _ = inputs
    query = documents[-2]
    other = {**query, 'doc_id': 'us_loan-other', 'component_id': 'other'}
    failed = {**other, 'doc_id': 'us_loan-failed', 'status': 'needs_review'}
    related = {**query, 'doc_id': 'us_loan-related'}
    documents += [other, failed, related]
    pool = [{'doc': r['doc_id'], 'chunk_id': r['doc_id'] + '#p0', 'text': 'source', 'tags': []}
            for r in documents if r['domain'] == 'us_loan']
    admitted = main.admit_loan_pool(pool, documents)
    assert {r['doc'] for r in admitted} == {query['doc_id'], other['doc_id'], related['doc_id']}
    assert [r['doc'] for r in main.query_loan_pool(admitted, documents, query['doc_id'])] == [other['doc_id']]
    assert len(pool) == 5


def test_unknown_reference_rejected(inputs):
    with pytest.raises(ValueError, match='reference'):
        main.admit_loan_pool([{'doc': 'missing', 'chunk_id': 'x'}], inputs[0])


@pytest.fixture
def envelope(tmp_path):
    client = Mock()
    client.directory = tmp_path / 'research/harness_v3/main_3000_baseline_01/calls'
    client.model = 'gpt-5.4-mini'
    client.provenance.return_value = {'cli_version': 'test', 'cli_sha256': 'test'}
    client.usage_summary.return_value = {'incomplete_calls': 0, 'unknown_usage_calls': 0}
    return main.EnvelopeClient(client, tmp_path, {'records': []}), client


@pytest.mark.parametrize('count,tokens,reserve,blocked', [
    (1099, 1, 1, False), (1100, 1, 1, True), (1098, 1, 3, True),
    (1, 30_000_000, 1, True), (1, 29_999_999, 1, False),
])
def test_budget_prelaunch(envelope, monkeypatch, count, tokens, reserve, blocked):
    wrapper, client = envelope
    monkeypatch.setattr(main, 'usage_inventory', lambda _: {
        'records': [], 'call_count': count, 'observed_tokens': tokens})
    if blocked:
        with pytest.raises(ModelFailure, match='envelope'):
            wrapper.guard(reserve)
    else:
        wrapper.guard(reserve)
    client.call.assert_not_called()


def test_history_change_and_incomplete_call_block(envelope, monkeypatch):
    wrapper, client = envelope
    monkeypatch.setattr(main, 'usage_inventory', lambda _: {
        'records': [{'path': 'research/harness_v3/other/calls/x/record.json'}],
        'call_count': 1, 'observed_tokens': 0})
    with pytest.raises(ModelFailure, match='history'):
        wrapper.guard()
    monkeypatch.setattr(main, 'usage_inventory', lambda _: {
        'records': [], 'call_count': 0, 'observed_tokens': 0})
    client.usage_summary.return_value = {'incomplete_calls': 1, 'unknown_usage_calls': 1}
    with pytest.raises(ModelFailure, match='reconciliation'):
        wrapper.guard()


@pytest.mark.parametrize('cached', [True, False])
def test_only_exact_cache_bypasses_budget(envelope, monkeypatch, cached):
    wrapper, client = envelope
    request = dict(label='doc/spot', model=client.model, system='s', prompt='p', max_tokens=100, schema={})
    identifier = request_id(inference_request(**{k: v for k, v in request.items() if k != 'label'},
                                            provenance=client.provenance()))
    if cached:
        write_json(client.directory / identifier / 'record.json', {'status': 'success'})
    monkeypatch.setattr(main, 'usage_inventory', lambda _: {
        'records': [], 'call_count': 1100, 'observed_tokens': 30_000_000})
    if cached:
        wrapper.call(**request)
        client.call.assert_called_once_with(**request)
    else:
        with pytest.raises(ModelFailure):
            wrapper.call(**request)
        client.call.assert_not_called()


class FakeRuntime:
    def __init__(self, directory: Path, status: str = 'success'):
        self.directory, self.status, self.calls = directory, status, []

    def run_document(self, *args):
        doc_id = args[1] if isinstance(args[0], Path) else args[0]['doc_id']
        path = self.directory / 'documents' / doc_id / 'result.json'
        if path.exists():
            return main.read(path)
        self.calls.append(doc_id)
        result = {'identity': {'doc_id': doc_id}, 'status': self.status, 'artifact_sha256': {}}
        write_json(path, result)
        return result


@pytest.fixture
def batch(tmp_path, inputs):
    docs, preflight = inputs
    for row in docs:
        (tmp_path / row['source_path']).write_text('sample', encoding='utf-8')
        row['source_sha256'] = row['text_sha256'] = sha256(b'sample')
    for row, source in zip(preflight, docs, strict=True):
        row['source_sha256'] = row['text_sha256'] = source['source_sha256']
    preflight[-1]['status'] = 'preprocessing_review'
    preflight[-1]['minimum_calls_if_current_ready_pipeline_completes'] = 0
    output = tmp_path / 'research/harness_v3/main_3000_baseline_01'
    write_json(output / 'protocol.json', {'test': True})
    runtimes = {d: FakeRuntime(output / d) for d in DOMAINS}
    client = Mock()
    client.usage_summary.return_value = {'call_count': 0}
    return dict(rows=main.ordered_roster(docs, preflight, per_domain=2), runtimes=runtimes,
                client=client, output=output, root=tmp_path)


def test_resume_keeps_all_rows_without_rerun(batch):
    first = main.run_batch(**batch, batch_documents=3)
    assert first['status_counts'] == {'success': 3, 'not_started': 2, 'input_blocked': 1}
    second = main.run_batch(**batch, batch_documents=1)
    assert second['status_counts'] == {'success': 4, 'not_started': 1, 'input_blocked': 1}
    assert second['main_experiment_complete'] is False
    assert sum(len(r.calls) for r in batch['runtimes'].values()) == 4
    assert len(second['documents']) == 6


@pytest.mark.parametrize('status', ['failure', 'partial'])
def test_failure_stops_without_retry(batch, status):
    batch['runtimes']['kr_insurance'].status = status
    main.run_batch(**batch, batch_documents=3)
    result = main.run_batch(**batch, batch_documents=3)
    assert result['status_counts'][status] == 1
    assert result['stop_reason'] == 'native_result_requires_reconciliation'
    assert sum(len(r.calls) for r in batch['runtimes'].values()) == 1


def test_orphan_not_assumed_dead_or_restarted(batch):
    runtime = batch['runtimes']['kr_insurance']
    (runtime.directory / 'documents' / batch['rows'][0]['doc_id']).mkdir(parents=True)
    result = main.run_batch(**batch, batch_documents=3)
    assert result['stop_reason'] == 'interrupted_document_requires_reconciliation'
    assert result['status_counts']['interrupted_needs_reconciliation'] == 1
    assert not runtime.calls


def test_changed_checkpoint_result_rejected(batch):
    main.run_batch(**batch, batch_documents=1)
    path = batch['runtimes']['kr_insurance'].directory / 'documents' / batch['rows'][0]['doc_id'] / 'result.json'
    write_json(path, {'status': 'success', 'changed': True})
    with pytest.raises(ValueError, match='checkpoint'):
        main.run_batch(**batch, batch_documents=1)


def test_budget_stop_keeps_unstarted(batch):
    batch['client'].guard.side_effect = ModelFailure('envelope reached')
    result = main.run_batch(**batch, batch_documents=3)
    assert result['status_counts'] == {'not_started': 5, 'input_blocked': 1}
    assert result['stop_reason'] == 'envelope reached'
    batch['client'].guard.assert_called_once_with(3)


def test_zero_batch_and_completed_native_reconciliation(batch):
    result = main.run_batch(**batch, batch_documents=0)
    assert result['status_counts'] == {'not_started': 5, 'input_blocked': 1}
    batch['client'].guard.assert_not_called()
    batch['runtimes']['kr_insurance'].run_document(Path('unused'), batch['rows'][0]['doc_id'], {})
    result = main.run_batch(**batch, batch_documents=0)
    assert result['status_counts']['success'] == 1
    assert len(batch['runtimes']['kr_insurance'].calls) == 1


def test_lock_exclusive_and_exception_cleanup(tmp_path):
    path = tmp_path / 'runner.lock'
    with pytest.raises(RuntimeError):
        with main.run_lock(path):
            with pytest.raises(FileExistsError):
                with main.run_lock(path):
                    pytest.fail('Second owner entered')
            assert path.exists()
            raise RuntimeError('test')
    assert not path.exists()


@pytest.fixture
def preparation(tmp_path, monkeypatch):
    """Real-shaped 3000-row parent manifests with fake native transports."""
    (tmp_path / 'source.txt').write_text('source', encoding='utf-8')
    digest = sha256(b'source')
    documents = [dict(doc_id=f'{domain}-{i:04}', domain=domain, source_path='source.txt',
                      source_sha256=digest, text_path='source.txt', text_sha256=digest,
                      status='success', mechanical_issues=[], component_id=f'{domain}-{i}',
                      allocation=main.DEVELOPMENT if i == 0 else main.RESERVED)
                 for domain in DOMAINS for i in range(1000)]
    preflight = [{**row, 'extraction_status': 'success', 'status': 'runtime_candidate',
                  'minimum_calls_if_current_ready_pipeline_completes': 3,
                  'conditional_card_validation_calls': 0} for row in documents]
    payloads = {**{p: {'documents': documents} for p in main.INPUTS.values()},
        main.RECONCILIATION: {'existing_stop_evidence': {}, 'stopped_pending_records': {}},
        'research/main_3000_preflight_v2/manifest.json': {'documents': preflight},
        'research/loan_reference_1000_v1/candidate_pool.json': {'chunks': [
            {'doc': 'us_loan-0000', 'chunk_id': 'us_loan-0000#p0', 'text': 'source', 'tags': []}]}}
    for relative, payload in payloads.items():
        write_json(tmp_path / relative, payload)
    monkeypatch.setattr(main, 'PARENTS', {p: sha256((tmp_path / p).read_bytes()) for p in payloads})
    for name in ('main_execution', 'main_preflight', 'loan_reference', 'full_corpus_v2'):
        path = tmp_path / 'scripts_evolve' / (name + '.py')
        path.parent.mkdir(exist_ok=True)
        path.write_text('# test code snapshot\n', encoding='utf-8')

    def make_client(directory, executable, **kwargs):
        client = Mock()
        client.directory, client.model = directory, kwargs['model']
        client.usage_summary.return_value = {'call_count': 0, 'incomplete_calls': 0, 'unknown_usage_calls': 0}
        assert kwargs == dict(max_calls=1100, token_stop_threshold=30_000_000, model='gpt-5.4-mini')
        return client

    monkeypatch.setattr(main, 'CodexClient', make_client)
    kr, us = Mock(protocol={'native': 'kr'}), Mock(protocol={'native': 'us'})
    monkeypatch.setattr(main, 'NativeHarness', Mock(return_value=kr))
    monkeypatch.setattr(main, 'GroupScopedUSRuntime', Mock(return_value=us))
    output = tmp_path / 'research/harness_v3/main_3000_baseline_01'
    return tmp_path, output


def test_prepare_real_archive_shape_and_resume(preparation):
    root, output = preparation
    rows, runtimes, client = main.prepare(output, root / 'fake.exe', root)
    assert len(rows) == 3000
    assert set(runtimes) == set(DOMAINS)
    protocol = main.read(output / 'protocol.json')
    assert protocol['reference_chunks'] == protocol['reference_sources'] == 1
    assert protocol['target_total'] == 3000
    client.native.call.assert_not_called()
    assert main.prepare(output, root / 'fake.exe', root)[0] == rows


def test_prepare_rejects_source_and_snapshot_drift(preparation):
    root, output = preparation
    main.prepare(output, root / 'fake.exe', root)
    snapshot = output / 'snapshot/scripts_evolve/main_execution.py'
    snapshot.write_text('changed', encoding='utf-8')
    with pytest.raises(ValueError, match='snapshot'):
        main.prepare(output, root / 'fake.exe', root)
    (root / 'source.txt').write_text('changed', encoding='utf-8')
    with pytest.raises(ValueError, match='hash'):
        main.prepare(output, root / 'fake.exe', root)


def test_prepare_rejects_unfrozen_output_and_pending_history(preparation):
    root, output = preparation
    output.mkdir(parents=True)
    (output / 'unknown.txt').write_text('orphan', encoding='utf-8')
    with pytest.raises(ValueError, match='Unfrozen'):
        main.prepare(output, root / 'fake.exe', root)
    (output / 'unknown.txt').unlink()
    write_json(root / 'research/harness_v3/other/calls/x/record.json', {'status': 'pending'})
    with pytest.raises(ValueError, match='Pending'):
        main.prepare(output, root / 'fake.exe', root)


@pytest.mark.parametrize('raises', [True, False])
def test_group_scoped_native_retrieval_restores_pool(inputs, tmp_path, monkeypatch, raises):
    docs = inputs[0]
    query = docs[-2]['doc_id']
    other = {**docs[-2], 'doc_id': 'us_loan-other', 'component_id': 'other'}
    runtime = main.GroupScopedUSRuntime.__new__(main.GroupScopedUSRuntime)
    runtime.reference_documents = docs + [other]
    original = [{'doc': query, 'chunk_id': query + '#p0'},
                {'doc': other['doc_id'], 'chunk_id': other['doc_id'] + '#p0'}]
    runtime.loan_pool = original

    def native(self, work, trace, drafts):
        assert [r['doc'] for r in self.loan_pool] == [other['doc_id']]
        if raises:
            raise ValueError('native failure')
        return True

    monkeypatch.setattr(main.USRuntime, 'run_loan', native)
    if raises:
        with pytest.raises(ValueError, match='native failure'):
            runtime.run_loan(tmp_path, {'identity': {'doc_id': query}}, [])
    else:
        assert runtime.run_loan(tmp_path, {'identity': {'doc_id': query}}, [])
    assert runtime.loan_pool is original
    assert main.read(tmp_path / 'reference_selection.json')['chunk_ids'] == [other['doc_id'] + '#p0']


def test_interrupted_status_survives_missing_work_directory(batch):
    runtime = batch['runtimes']['kr_insurance']
    work = runtime.directory / 'documents' / batch['rows'][0]['doc_id']
    work.mkdir(parents=True)
    main.run_batch(**batch, batch_documents=0)
    work.rmdir()  # Only this test's empty work directory, simulating lost evidence.
    result = main.run_batch(**batch, batch_documents=1)
    assert result['status_counts']['interrupted_needs_reconciliation'] == 1
    assert not runtime.calls


def test_orphan_request_blocks_even_when_another_request_is_next(envelope):
    wrapper, client = envelope
    (client.directory / 'orphan').mkdir(parents=True)
    with pytest.raises(ModelFailure, match='Orphaned'):
        wrapper.guard()
    client.call.assert_not_called()


@pytest.mark.parametrize('field,value', [('status', 'unexpected'),
    ('minimum_calls_if_current_ready_pipeline_completes', -2)])
def test_invalid_preflight_rejected(inputs, field, value):
    docs, preflight = inputs
    preflight[0][field] = value
    with pytest.raises(ValueError):
        main.ordered_roster(docs, preflight, per_domain=2)


def test_invalid_batch_or_changed_checkpoint_roster_rejected(batch):
    with pytest.raises(ValueError, match='nonnegative'):
        main.run_batch(**batch, batch_documents=-1)
    main.run_batch(**batch, batch_documents=0)
    with pytest.raises(ValueError, match='checkpoint'):
        main.run_batch(**{**batch, 'rows': batch['rows'][::-1]}, batch_documents=0)


def test_blocked_source_cannot_acquire_native_result(batch):
    row = batch['rows'][-1]
    batch['runtimes'][row['domain']].run_document(row)
    with pytest.raises(ValueError, match='blocked source'):
        main.run_batch(**batch, batch_documents=0)


def test_scoped_runtime_constructor_preserves_original_parameters(inputs, tmp_path, monkeypatch):
    original_init = Mock(return_value=None)
    monkeypatch.setattr(main.USRuntime, '__init__', original_init)
    docs, client, pool = inputs[0], Mock(), []
    runtime = main.GroupScopedUSRuntime(tmp_path, client, pool, docs, root=tmp_path)
    assert runtime.reference_documents == docs
    original_init.assert_called_once_with(tmp_path, client, pool, root=tmp_path)


def test_cli_default_prepares_without_launch(monkeypatch, tmp_path):
    import sys
    monkeypatch.setattr(main, 'ROOT', tmp_path)
    monkeypatch.setattr(main, 'OUTPUT', tmp_path / 'run')
    prepare = Mock(return_value=([], {}, Mock()))
    batch = Mock(return_value={'documents': [], 'stop_reason': 'batch_document_limit'})
    monkeypatch.setattr(main, 'prepare', prepare)
    monkeypatch.setattr(main, 'run_batch', batch)
    monkeypatch.setattr(sys, 'argv', ['main_execution', '--codex', 'test.exe'])
    assert main.main() == 0
    assert batch.call_args.args[-1] == 0
    monkeypatch.setattr(sys, 'argv', ['main_execution', '--codex', 'test.exe', '--batch-documents', '-1'])
    with pytest.raises(SystemExit) as error:
        main.main()
    assert error.value.code == 2


@pytest.mark.parametrize('mutation', [None, 'missing', 'status', 'stop_evidence'])
def test_only_exact_reconciled_old_pending_is_preserved_not_retried(preparation, monkeypatch, mutation):
    root, output = preparation
    relative = 'research/pilot_v1/run_old/calls/x/record.json'
    write_json(root / relative, {'status': 'pending'})
    record_hash = sha256((root / relative).read_bytes())
    evidence = root / 'stopped.md'
    evidence.write_text('Old run stopped; do not retry.', encoding='utf-8')
    write_json(root / main.RECONCILIATION, {
        'existing_stop_evidence': {'stopped.md': sha256(evidence.read_bytes())},
        'stopped_pending_records': {relative: record_hash}})
    monkeypatch.setitem(main.PARENTS, main.RECONCILIATION,
                        sha256((root / main.RECONCILIATION).read_bytes()))
    if mutation == 'missing':
        (root / relative).unlink()  # This fixture's single synthetic request only.
    elif mutation == 'status':
        write_json(root / relative, {'status': 'success'})
    elif mutation == 'stop_evidence':
        evidence.write_text('changed', encoding='utf-8')
    if mutation:
        with pytest.raises((ValueError, FileNotFoundError)):
            main.prepare(output, root / 'fake.exe', root)
        assert not (output / 'prior_usage.json').exists()
        return
    _, _, client = main.prepare(output, root / 'fake.exe', root)
    assert main.read(output / 'prior_usage.json')['unknown_usage_calls'] == 1
    assert sha256((root / relative).read_bytes()) == record_hash
    client.native.call.assert_not_called()
