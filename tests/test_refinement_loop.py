"""Real loop orchestration is tested with explicit mocked model responses."""
from copy import deepcopy
import json
import sys
from types import SimpleNamespace

import pytest

from scripts_evolve import refinement_loop as loop
from scripts_evolve.refinement_stage1 import BASELINE


def case():
    return {'doc_id': 'example', 'domain': 'us_card', 'raw': 'the fee  is $35 and terms apply',
            'baseline': 'the fee  is $35 and terms apply', 'source_sha256': 'source', 'text_sha256': 'text',
            'extraction_status': 'success', 'allocation': 'development_exposed_or_linked'}


def test_real_candidate_execution_selection_history_and_early_stop(tmp_path):
    calls = []

    def fake_role(role, payload, schema):
        calls.append((role, deepcopy(payload)))
        if role == 'meta_review':
            return {'failure_patterns': [], 'do_not_repeat': []}
        if role == 'evolution':
            return {'direction': 'Normalize duplicate spaces.', 'reason': 'Preserve all words.'}
        config = {**deepcopy(BASELINE), 'collapse_spaces': True}
        return {'candidates': [{'rationale': 'Collapse duplicate spaces.', 'configuration': config}]}

    result = loop.refine_domain('us_card', [case()], ['fee'], fake_role, tmp_path, max_iterations=3)
    assert [role for role, _ in calls] == ['meta_review', 'evolution', 'generation'] * 2
    assert result['iterations_completed'] == 2
    assert result['stop_reason'] == 'no_strictly_improving_eligible_candidate'
    assert result['selected_configuration']['collapse_spaces']
    assert result['history'][0]['candidates'][0]['selected']
    assert result['history'][1]['candidates'][0]['status'] == 'duplicate_configuration'
    assert calls[3][1]['history'][0]['candidates'][0]['selected']
    assert (tmp_path / 'iteration_001/candidate_00/texts/example.txt').read_text() == 'the fee is $35 and terms apply'
    assert (tmp_path / 'selected_configuration.json').exists()


def test_gate_rejection_never_changes_selected_configuration(tmp_path):
    def fake_role(role, payload, schema):
        if role == 'meta_review':
            return {'failure_patterns': [], 'do_not_repeat': []}
        if role == 'evolution':
            return {'direction': 'test rejection', 'reason': 'unit test only'}
        return {'candidates': [{'rationale': 'Unsafe deletion test.',
                 'configuration': {**deepcopy(BASELINE), 'drop_line_prefixes': ['the fee']}}]}

    result = loop.refine_domain('us_card', [case()], ['fee'], fake_role, tmp_path, 3)
    assert result['selected_configuration'] == BASELINE
    assert result['history'][0]['candidates'][0]['metrics']['gate_failed_documents'] == 1
    assert not result['history'][0]['candidates'][0]['selected']


def test_reserved_source_cannot_enter_refinement(tmp_path):
    record = case()
    record['allocation'] = 'evaluation_reserved'
    with pytest.raises(ValueError, match='development'):
        loop.refine_domain('us_card', [record], ['fee'], None, tmp_path)


def test_wrong_domain_and_duplicate_inputs_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        loop.refine_domain('us_loan', [case()], ['fee'], None, tmp_path)
    with pytest.raises(ValueError):
        loop.refine_domain('us_card', [case(), case()], ['fee'], None, tmp_path)


def test_invalid_literal_candidate_is_logged_not_executed(tmp_path):
    def fake_role(role, payload, schema):
        if role == 'meta_review':
            return {'failure_patterns': [], 'do_not_repeat': []}
        if role == 'evolution':
            return {'direction': 'test', 'reason': 'test'}
        return {'candidates': [{'rationale': 'invalid literal',
                 'configuration': {**deepcopy(BASELINE), 'drop_exact_lines': ['a\nb']}}]}

    result = loop.refine_domain('us_card', [case()], ['fee'], fake_role, tmp_path)
    assert result['history'][0]['candidates'][0]['status'] == 'invalid_configuration'
    assert not (tmp_path / 'iteration_001/candidate_00/texts').exists()


def test_model_failure_is_not_relabelled_as_success(tmp_path):
    def fake_role(*args):
        raise RuntimeError('deliberate model failure')

    with pytest.raises(RuntimeError, match='deliberate model failure'):
        loop.refine_domain('us_card', [case()], ['fee'], fake_role, tmp_path)
    assert not (tmp_path / 'summary.json').exists()


@pytest.mark.parametrize('usage', [
    {'call_count': 1100, 'observed_tokens': 1}, {'call_count': 1, 'observed_tokens': 30000000},
])
def test_global_historical_envelope_blocks_before_call(tmp_path, monkeypatch, usage):
    monkeypatch.setattr(loop, 'usage_inventory', lambda _: usage)
    roles = loop.Roles(None, tmp_path, tmp_path)
    with pytest.raises(ValueError, match='envelope reached'):
        roles('meta_review', {}, {})


def test_load_cases_checks_source_text_length_and_safe_identity(tmp_path):
    source, text = tmp_path / 'source.pdf', tmp_path / 'source.txt'
    source.write_bytes(b'test source')
    text.write_bytes(b'the fee\r\nterms')
    row = {'doc_id': 'us_card-' + 'a' * 20, 'domain': 'us_card', 'source_path': 'source.pdf', 'text_path': 'source.txt',
           'source_sha256': loop.sha256(source.read_bytes()), 'text_sha256': loop.sha256(text.read_bytes()),
           'characters': len(text.read_bytes()), 'allocation': 'development_exposed_or_linked', 'status': 'needs_review'}
    tasks = {'us_card': {'strategy_ours': lambda value: value}}
    result = loop.load_cases([row], tasks, tmp_path)
    assert result[0]['raw'] == 'the fee\r\nterms'
    assert result[0]['extraction_status'] == 'needs_review'
    with pytest.raises(ValueError, match='length changed'):
        loop.load_cases([{**row, 'characters': 0}], tasks, tmp_path)
    with pytest.raises(ValueError, match='source ID'):
        loop.load_cases([{**row, 'doc_id': '../escape'}], tasks, tmp_path)
    source.write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash changed'):
        loop.load_cases([row], tasks, tmp_path)


def test_invalid_iteration_budget_never_starts(tmp_path):
    with pytest.raises(ValueError, match='one to three'):
        loop.refine_domain('us_card', [case()], ['fee'], None, tmp_path, 4)


def test_role_native_response_mismatch_stops_before_record_publication(tmp_path, monkeypatch):
    monkeypatch.setattr(loop, 'usage_inventory', lambda _: {'call_count': 1, 'observed_tokens': 1})
    client = SimpleNamespace(directory=tmp_path, call=lambda **kwargs: {'request_id': 'example', 'output': {'a': 1}})
    monkeypatch.setattr(loop, 'verify_codex_storage', lambda *args: {'output': {'a': 2}})
    with pytest.raises(ValueError, match='differs from native'):
        loop.Roles(client, tmp_path, tmp_path)('meta_review', {'domain': 'us_card', 'iteration': 1}, {})
    assert not (tmp_path / 'role_records').exists()


@pytest.mark.parametrize('arguments', [
    ['--run-dir', 'outside'], ['--run-dir', 'research/harness_v3/test', '--max-calls', '28'],
])
def test_cli_rejects_unaccounted_path_and_envelope_expansion(monkeypatch, arguments):
    monkeypatch.setattr(sys, 'argv', ['evolve', '--codex', 'unused.exe', *arguments])
    with pytest.raises(SystemExit) as exc:
        loop.main()
    assert exc.value.code == 2


@pytest.mark.parametrize('failure', ['allocation', 'snapshot', 'execution'])
def test_cli_fails_closed_and_preserves_interrupted_execution(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(loop, 'ROOT', tmp_path)
    output = tmp_path / 'research/harness_v3/test'
    monkeypatch.setattr(sys, 'argv', ['evolve', '--run-dir', str(output), '--codex', 'unused.exe'])
    sources = [{'doc_id': f'{d}-{i}', 'domain': d} for d in loop.DOMAINS for i in range(1000)]
    extraction = [dict(row, characters=4) for row in sources]
    allocated = [dict(row, characters=5 if failure == 'allocation' else 4,
                      allocation='development_exposed_or_linked') for row in sources]
    for relative, rows in [('research/dataset_3000_v2/source_manifest.json', sources),
                           ('research/dataset_3000_v2/extraction_manifest.json', extraction),
                           ('research/main_3000_groups_v1/allocation_manifest.json', allocated)]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'documents': rows}), encoding='utf-8')
    implementations = ['evolve.py', 'scripts_evolve/refinement_loop.py', 'scripts_evolve/refinement_stage1.py',
                       'scripts_evolve/e1_cohort.py', 'scripts_evolve/full_corpus_v2.py', 'scripts_evolve/main_preflight.py',
                       'scripts_evolve/us_tasks.py', 'scripts_evolve/native_schemas.py', 'scripts/pilot/codex_client.py',
                       'scripts/pilot/client.py', *loop.ORIGINALS.values()]
    for relative in implementations:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# test fixture only', encoding='utf-8')
    client = SimpleNamespace(provenance=lambda: {}, usage_summary=lambda: {'call_count': 0})
    monkeypatch.setattr(loop, 'CodexClient', lambda *args, **kwargs: client)
    monkeypatch.setattr(loop, 'usage_inventory', lambda _: {'call_count': 0})
    monkeypatch.setattr(loop, 'load_originals', lambda _: {d: {'keywords': ['fee']} for d in loop.DOMAINS})
    monkeypatch.setattr(loop, 'load_cases', lambda *args: [case()])

    def fail(*args):
        raise RuntimeError('deliberate execution interruption')

    monkeypatch.setattr(loop, 'refine_domain', fail)
    if failure == 'snapshot':
        path = output / 'snapshot/evolve.py'
        path.parent.mkdir(parents=True)
        path.write_text('# changed', encoding='utf-8')
    message = {'allocation': 'identity changed', 'snapshot': 'snapshot changed', 'execution': 'deliberate execution'}[failure]
    with pytest.raises((ValueError, RuntimeError), match=message):
        loop.main()
    if failure == 'execution':
        evidence = loop.read(output / 'interruption.json')
        assert evidence['status'] == 'failed_or_stopped'
        assert evidence['usage']['call_count'] == 0
        assert not (output / 'summary.json').exists()
