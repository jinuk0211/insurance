"""Freeze original retrieval chunks without treating full-paragraph tags as gold."""
from copy import deepcopy
import json
import sys

import pytest

from scripts_evolve import loan_reference as reference
from scripts_evolve.full_corpus_v2 import sha256
from scripts_evolve.main_preflight import check_roster


@pytest.fixture(scope='module')
def original():
    return reference.load_original(reference.ROOT)


def source(root, name, text, status='success', allocation='evaluation_reserved'):
    path = root / (name + '.txt')
    path.write_bytes(text.encode())
    digest = sha256(path.read_bytes())
    return {'doc_id': name, 'domain': 'us_loan', 'source_path': path.name,
            'source_sha256': digest, 'text_path': path.name, 'text_sha256': digest,
            'characters': len(text), 'status': status, 'mechanical_issues': [],
            'component_id': name, 'allocation': allocation, 'held_out_verified': False}


def test_original_loading_omits_api_initializers(original):
    assert set(original) == {'LOAN_TAXONOMY', 'build_candidate_pool'}
    assert callable(original['build_candidate_pool'])


def test_original_hash_is_checked_before_ast_execution(tmp_path):
    path = tmp_path / reference.ORIGINAL_PATH
    path.parent.mkdir(parents=True)
    path.write_text('raise RuntimeError("must not execute")', encoding='utf-8')
    with pytest.raises(ValueError, match='hash'):
        reference.load_original(tmp_path)


@pytest.mark.parametrize('separator', ['\n\n', '\r\n\r\n', '\n\n\n', '\r', '\f\n'])
def test_exact_original_chunks_preserve_raw_newline_offsets(tmp_path, original, separator):
    para = '  immediately due ' + 'contract ' * 30 + '  '
    text = '\t' + para + separator + para + '\r\n'
    row = source(tmp_path, 'loan', text)
    frozen = deepcopy(row)
    report, pool, audits = reference.audit_document(row, tmp_path, original)
    assert pool == original['build_candidate_pool']({'loan': text}, set())
    assert row == frozen and report['characters'] == len(text)
    assert report['chunks'] == len(pool) == len(audits)
    for chunk, audit in zip(pool, audits, strict=True):
        assert text[audit['source_start']:audit['source_end']] == chunk['text']
        assert audit['text_sha256'] == sha256(chunk['text'].encode())
        assert audit['tags_missing_from_visible_text'] == []


def test_tags_after_1500_are_flagged_without_repairing_original_output(tmp_path, original):
    text = 'ordinary contract terms ' * 90 + ' cross-default'
    row = source(tmp_path, 'loan', text)
    report, pool, audits = reference.audit_document(row, tmp_path, original)
    assert len(pool) == 1 and len(pool[0]['text']) == 1500
    assert pool[0]['tags'] == ['LOAN-04']
    assert audits[0]['visible_tags'] == []
    assert audits[0]['tags_missing_from_visible_text'] == ['LOAN-04']
    assert audits[0]['paragraph_end'] == len(text)
    assert report['chunks_with_missing_visible_tags'] == 1


def test_mixed_visible_and_cutoff_tags_are_distinguished(tmp_path, original):
    text = 'immediately due ' + 'ordinary contract terms ' * 90 + ' cross-default'
    _, pool, audits = reference.audit_document(source(tmp_path, 'loan', text), tmp_path, original)
    assert pool[0]['tags'] == ['LOAN-01', 'LOAN-04']
    assert audits[0]['visible_tags'] == ['LOAN-01']
    assert audits[0]['tags_missing_from_visible_text'] == ['LOAN-04']


def test_original_filters_short_paragraphs_and_caps_before_tagging(tmp_path, original):
    text = '\n\n'.join(['immediately due'] + ['ordinary text ' * 20] * 40 + ['cross-default ' * 30])
    report, pool, audits = reference.audit_document(source(tmp_path, 'loan', text), tmp_path, original)
    assert report['eligible_paragraphs'] == 41
    assert report['considered_paragraphs'] == 40
    assert report['paragraphs_beyond_original_cap'] == 1
    assert pool == audits == []


def test_paragraph_ids_include_untagged_eligible_paragraphs(tmp_path, original):
    text = 'ordinary text ' * 20 + '\n\n' + 'cross-default ' * 30
    _, pool, audits = reference.audit_document(source(tmp_path, 'loan', text), tmp_path, original)
    assert pool[0]['chunk_id'] == audits[0]['chunk_id'] == 'loan#p1'


@pytest.mark.parametrize('status', ['needs_review', 'failure'])
def test_quality_flags_never_drop_a_document_or_silently_admit_it(tmp_path, original, status):
    row = source(tmp_path, 'loan', 'cross-default ' * 30, status=status)
    row['mechanical_issues'] = ['example_quality_flag']
    report, pool, _ = reference.audit_document(row, tmp_path, original)
    assert report['status'] == status and report['mechanical_issues'] == row['mechanical_issues']
    assert report['reference_quality_eligible'] is False and len(pool) == 1


def test_missing_failed_text_retains_zero_chunk_row_and_success_missing_text_fails(tmp_path, original):
    row = source(tmp_path, 'loan', '', status='failure')
    row.pop('text_path')
    report, pool, audits = reference.audit_document(row, tmp_path, original)
    assert report['text_available'] is False and report['chunks'] == 0
    assert pool == audits == []
    row['status'] = 'success'
    with pytest.raises(ValueError, match='missing text'):
        reference.audit_document(row, tmp_path, original)


@pytest.mark.parametrize('field,value', [('source_sha256', '0' * 64), ('text_sha256', '0' * 64),
                                        ('characters', 1), ('source_path', '../outside.txt')])
def test_source_tampering_and_outside_paths_fail(tmp_path, original, field, value):
    row = source(tmp_path, 'loan', 'cross-default ' * 30)
    row[field] = value
    with pytest.raises(ValueError):
        reference.audit_document(row, tmp_path, original)


def test_original_output_mismatch_is_rejected(tmp_path, original):
    changed = {**original, 'build_candidate_pool': lambda *_: []}
    with pytest.raises(ValueError, match='Original pool'):
        reference.audit_document(source(tmp_path, 'loan', 'cross-default ' * 30), tmp_path, changed)


def test_wrong_domain_is_rejected_before_source_access(tmp_path, original):
    with pytest.raises(ValueError, match='Loan source'):
        reference.audit_document({'domain': 'us_card'}, tmp_path, original)


def test_summary_rejects_missing_chunk_audit():
    with pytest.raises(ValueError, match='counts differ'):
        reference.summarize([{'chunks': 1}], [])


def test_summary_retains_zero_chunks_and_reports_tag_document_denominators(tmp_path, original):
    rows = [source(tmp_path, 'a', 'ordinary terms ' * 30),
            source(tmp_path, 'b', 'ordinary terms ' * 150 + ' cross-default', allocation='development_exposed_or_linked'),
            source(tmp_path, 'c', 'immediately due ' * 30, status='needs_review')]
    results = [reference.audit_document(r, tmp_path, original) for r in rows]
    summary = reference.summarize([r[0] for r in results], [a for r in results for a in r[2]])
    assert summary['loan_documents'] == 3 and summary['documents_without_chunks'] == 1
    assert summary['chunks'] == 2 and summary['chunks_with_missing_visible_tags'] == 1
    assert summary['documents_with_missing_visible_tags'] == 1
    assert summary['missing_visible_tag_assignments'] == {'LOAN-04': 1}
    assert summary['development_documents'] == 1 and summary['evaluation_reserved_documents'] == 2
    assert summary['model_calls'] == 0 and summary['runtime_pool_admitted'] is False


@pytest.fixture
def manifests(tmp_path, monkeypatch):
    rows = []
    for domain in reference.DOMAINS:
        row = source(tmp_path, domain, 'cross-default ' * 30)
        row['domain'] = domain
        rows.append(row)
    paths = {'sources': 'sources.json', 'extractions': 'extractions.json', 'allocation': 'allocation.json'}
    for path in paths.values():
        (tmp_path / path).write_text(json.dumps({'documents': rows}), encoding='utf-8')
    monkeypatch.setattr(reference, 'INPUTS', paths)
    monkeypatch.setattr(reference, 'INPUT_SHA256', {k: sha256((tmp_path / p).read_bytes()) for k, p in paths.items()})
    monkeypatch.setattr(reference, 'check_roster', lambda a, b: check_roster(a, b, per_domain=1))
    return rows, paths


def test_load_inputs_checks_full_three_domain_roster_before_selecting_loans(tmp_path, manifests):
    rows, _ = manifests
    selected = reference.load_inputs(tmp_path)
    assert selected == [rows[-1]]


@pytest.mark.parametrize('target', ['extractions', 'allocation'])
def test_roster_loss_and_group_identity_tampering_fail_even_with_matching_file_hash(tmp_path, monkeypatch, manifests, target):
    rows, paths = manifests
    changed = deepcopy(rows)
    changed[-1]['source_sha256'] = '0' * 64
    path = tmp_path / paths[target]
    path.write_text(json.dumps({'documents': changed}), encoding='utf-8')
    monkeypatch.setitem(reference.INPUT_SHA256, target, sha256(path.read_bytes()))
    with pytest.raises(ValueError, match='identity'):
        reference.load_inputs(tmp_path)


def test_input_manifest_hash_change_is_rejected(tmp_path, manifests):
    _, paths = manifests
    (tmp_path / paths['sources']).write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='hash'):
        reference.load_inputs(tmp_path)


@pytest.mark.parametrize('change', ['missing', 'repeated'])
def test_missing_or_repeated_source_row_is_rejected(tmp_path, monkeypatch, manifests, change):
    rows, paths = manifests
    changed = rows[:-1] if change == 'missing' else rows + [rows[-1]]
    path = tmp_path / paths['allocation']
    path.write_text(json.dumps({'documents': changed}), encoding='utf-8')
    monkeypatch.setitem(reference.INPUT_SHA256, 'allocation', sha256(path.read_bytes()))
    with pytest.raises(ValueError, match='roster'):
        reference.load_inputs(tmp_path)


def test_direct_freeze_also_refuses_existing_output(tmp_path):
    output = tmp_path / 'research' / 'exists'
    output.mkdir(parents=True)
    with pytest.raises(ValueError, match='new direct child'):
        reference.freeze(tmp_path, output)


def test_main_refuses_existing_or_outside_output_before_input_load(tmp_path, monkeypatch):
    monkeypatch.setattr(reference, 'ROOT', tmp_path)
    for output in (tmp_path / 'research', tmp_path / 'outside'):
        monkeypatch.setattr(sys, 'argv', ['loan_reference', '--output', str(output)])
        with pytest.raises(SystemExit):
            reference.main()
    existing = tmp_path / 'research' / 'existing'
    existing.mkdir(parents=True)
    monkeypatch.setattr(sys, 'argv', ['loan_reference', '--output', str(existing)])
    with pytest.raises(SystemExit):
        reference.main()


def test_freeze_writes_protocol_before_results_and_binds_each_output(tmp_path, monkeypatch, original):
    row = source(tmp_path, 'loan', 'cross-default ' * 30)
    monkeypatch.setattr(reference, 'load_inputs', lambda _: [row])
    monkeypatch.setattr(reference, 'load_original', lambda _: original)
    monkeypatch.setattr(reference, 'INPUTS', {})
    monkeypatch.setattr(reference, 'IMPLEMENTATIONS', [])
    seen = []
    writer = reference.write_once

    def ordered_write(path, value):
        seen.append(path.name)
        writer(path, value)

    monkeypatch.setattr(reference, 'write_once', ordered_write)
    output = tmp_path / 'research' / 'run'
    result = reference.freeze(tmp_path, output)
    assert seen[0] == 'protocol.json' and seen[-1] == 'manifest.json'
    assert result['summary']['loan_documents'] == 1
    assert result['summary']['runtime_pool_admitted'] is False
    for relative, digest in result['artifact_sha256'].items():
        assert sha256((output / relative).read_bytes()) == digest
    assert json.loads((output / 'candidate_pool.json').read_text())['chunks'][0]['doc'] == 'loan'
