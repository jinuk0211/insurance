"""Structural reference refinement, not a legal-relevance evaluator."""
from copy import deepcopy
from pathlib import Path

import pytest

from scripts_evolve import loan_reference_refinement as refine
from scripts.pilot.client import write_json

TAXONOMY = {'A': {'keywords': ['event of default']}, 'B': {'keywords': ['prepayment fee']}}


def parent(text, start=0):
    tags = refine.keyword_tags(text[start:], TAXONOMY)
    return {'doc_id': 'us_loan-test', 'chunk_id': 'us_loan-test#p0',
            'paragraph_start': start, 'paragraph_end': len(text), 'original_tags': tags}


def test_late_tag_recovered_without_dropping_original_tag():
    text = 'event of default ' + 'x ' * 900 + 'prepayment fee'
    original = parent(text)
    frozen = deepcopy(original)
    variants = refine.refine_parent(original, text, TAXONOMY)
    assert variants['original'][0]['tags'] == ['A', 'B']
    assert refine.keyword_tags(variants['original'][0]['text'], TAXONOMY) == ['A']
    for method in ('full_windows', 'compact_cover'):
        pool = variants[method]
        assert {tag for row in pool for tag in row['tags']} == {'A', 'B'}
        for row in pool:
            assert text[row['source_start']:row['source_end']] == row['text']
            assert len(row['text']) <= 1500
            assert row['tags'] == refine.keyword_tags(row['text'], TAXONOMY)
    assert original == frozen


def test_overlapping_windows_keep_boundary_keyword_and_raw_offsets():
    prefix = 'HEADER\r\n\r\n'
    text = prefix + 'x' * 1496 + 'EVENT OF DEFAULT' + 'x' * 80
    variants = refine.refine_parent(parent(text, len(prefix)), text, TAXONOMY)
    assert len(variants['full_windows']) == 1  # First window has no complete keyword.
    row = variants['full_windows'][0]
    assert row['source_start'] > len(prefix)
    assert text[row['source_start']:row['source_end']] == row['text']
    assert row['tags'] == ['A']


def test_compact_cover_reduces_duplicate_windows_not_tag_denominator():
    text = ('event of default prepayment fee ' + 'x' * 1400) * 8
    variants = refine.refine_parent(parent(text), text, TAXONOMY)
    assert len(variants['full_windows']) > 2
    assert len(variants['compact_cover']) == 1
    assert variants == refine.refine_parent(parent(text), text, TAXONOMY)
    expected = {'us_loan-test#p0': {'A', 'B'}}
    base = refine.measure(variants['full_windows'], expected, TAXONOMY)
    compact = refine.measure(variants['compact_cover'], expected, TAXONOMY)
    assert base['original_parent_tag_pairs'] == compact['original_parent_tag_pairs'] == 2
    assert base['visible_parent_tag_pairs'] == compact['visible_parent_tag_pairs'] == 2
    assert compact['indexed_characters'] < base['indexed_characters']
    assert compact['union_source_characters'] < base['union_source_characters']
    assert compact['parent_tag_retention'] == compact['visible_tag_consistency'] == 1


@pytest.mark.parametrize('corruption', ['tags', 'start', 'end', 'empty'])
def test_invalid_parent_cannot_be_silently_repaired(corruption):
    text = 'event of default ' + 'x' * 300
    record = parent(text)
    if corruption == 'tags':
        record['original_tags'] = ['B']
    elif corruption == 'start':
        record['paragraph_start'] = -1
    elif corruption == 'end':
        record['paragraph_end'] += 1
    else:
        record['paragraph_end'] = record['paragraph_start']
    with pytest.raises(ValueError):
        refine.refine_parent(record, text, TAXONOMY)


def test_empty_and_too_long_keywords_fail():
    record = parent('event of default ' + 'x' * 300)
    for taxonomy in ({}, {'A': {'keywords': ['']}}, {'A': {'keywords': ['x' * 1501]}}):
        with pytest.raises(ValueError):
            refine.refine_parent(record, 'event of default ' + 'x' * 300, taxonomy)


def test_lowercase_expansion_does_not_corrupt_offsets():
    text = '\u0130' * 20 + 'event of default' + 'x' * 1600 + 'prepayment fee'
    variants = refine.refine_parent(parent(text), text, TAXONOMY)
    for rows in variants.values():
        for row in rows:
            assert text[row['source_start']:row['source_end']] == row['text']


def test_empty_measurements_are_undefined_not_perfect():
    result = refine.measure([], {}, TAXONOMY)
    assert result['visible_tag_consistency'] is None
    assert result['parent_tag_retention'] is None
    assert result['chunks'] == 0


def test_selection_requires_both_retention_and_consistency():
    text = 'event of default ' + 'x' * 2000 + 'prepayment fee'
    variants = refine.refine_parent(parent(text), text, TAXONOMY)
    expected = {'us_loan-test#p0': {'A', 'B'}}
    scores = {name: refine.measure(rows, expected, TAXONOMY) for name, rows in variants.items()}
    chosen = refine.select_candidate(scores)
    assert chosen in ('full_windows', 'compact_cover')
    scores[chosen]['parent_tag_retention'] = 0.5
    other = 'full_windows' if chosen == 'compact_cover' else 'compact_cover'
    assert refine.select_candidate(scores) == other
    scores[other]['visible_tag_consistency'] = 0.5
    with pytest.raises(ValueError, match='structural'):
        refine.select_candidate(scores)


def test_measurement_rejects_changed_parent_identity_and_duplicate_chunk():
    text = 'event of default ' + 'x' * 300
    rows = refine.refine_parent(parent(text), text, TAXONOMY)['compact_cover']
    expected = {'us_loan-test#p0': {'A'}}
    with pytest.raises(ValueError):
        refine.measure(rows + rows, expected, TAXONOMY)
    rows[0]['parent_chunk_id'] = 'unknown'
    with pytest.raises(ValueError):
        refine.measure(rows, expected, TAXONOMY)


@pytest.fixture
def run_inputs(tmp_path, monkeypatch):
    text = 'event of default ' + 'x' * 2000 + 'prepayment fee'
    path = tmp_path / 'source.txt'
    path.write_text(text, encoding='utf-8')
    digest = refine.sha256(path.read_bytes())
    documents = [{'doc_id': f'us_loan-{i:04}', 'domain': 'us_loan',
                  'source_path': 'source.txt', 'text_path': 'source.txt',
                  'source_sha256': digest, 'text_sha256': digest,
                  'status': 'needs_review' if i == 999 else 'success',
                  'allocation': refine.DEVELOPMENT if i < 22 else 'evaluation_reserved'} for i in range(1000)]
    parents = [{**parent(text), 'doc_id': r['doc_id'], 'chunk_id': r['doc_id'] + '#p0'} for r in documents[:-1]]
    baseline = [{'doc': r['doc_id'], 'chunk_id': r['chunk_id'], 'tags': r['original_tags'],
                 'text': text[:1500]} for r in parents]
    pool_path, audit_path = list(refine.PARENTS)
    write_json(tmp_path / pool_path, {'chunks': baseline})
    write_json(tmp_path / audit_path, {'chunks': parents})
    monkeypatch.setattr(refine, 'PARENTS', {p: refine.sha256((tmp_path / p).read_bytes()) for p in (pool_path, audit_path)})
    for relative in ('scripts_evolve/loan_reference_refinement.py', 'scripts_evolve/loan_reference.py',
                     'scripts_evolve/main_preflight.py', 'scripts_evolve/full_corpus_v2.py', refine.ORIGINAL_PATH):
        p = tmp_path / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('# fake snapshot fixture', encoding='utf-8')
    monkeypatch.setattr(refine, 'ORIGINAL_SHA256', refine.sha256((tmp_path / refine.ORIGINAL_PATH).read_bytes()))
    plan = tmp_path / 'research/loan_reference_refinement_plan.md'
    plan.write_text('Frozen fixture plan', encoding='utf-8')
    monkeypatch.setattr(refine, 'load_inputs', lambda _: deepcopy(documents))
    monkeypatch.setattr(refine, 'load_original', lambda _: {'LOAN_TAXONOMY': TAXONOMY})
    return tmp_path, documents, parents, baseline


def test_full_loan_run_keeps_zero_and_flagged_rows_and_frozen_dev_choice(run_inputs):
    root, documents, _, _ = run_inputs
    output = root / 'research/result'
    result = refine.run(root, output)
    assert len(result['documents']) == 1000
    assert result['development']['documents'] == 22
    assert result['evaluation_reserved_not_held_out']['documents'] == 978
    assert result['all_loans']['zero_original_chunk_documents'] == 1
    assert result['all_loans']['quality_flagged_documents'] == 1
    assert result['selected_structural_candidate'] == 'compact_cover'
    assert [r['doc_id'] for r in result['documents']] == [r['doc_id'] for r in documents]
    assert result['runtime_default_changed'] is False
    selection = refine.read(output / 'selection.json')
    assert refine.read(output / 'development.json')['document_ids'] == [r['doc_id'] for r in documents[:22]]
    assert selection['development_sha256'] == refine.sha256((output / 'development.json').read_bytes())
    assert selection['runtime_admitted'] is False
    with pytest.raises(ValueError, match='new direct child'):
        refine.run(root, output)


def test_compare_document_rejects_parent_identity_and_changed_baseline(run_inputs):
    root, docs, parents, baseline = run_inputs
    with pytest.raises(ValueError, match='another source'):
        refine.compare_document(docs[0], [parents[1]], [baseline[0]], TAXONOMY, root)
    with pytest.raises(ValueError, match='not reproduced'):
        refine.compare_document(docs[0], [parents[0]], [], TAXONOMY, root)


def test_run_rejects_changed_development_roster_before_freeze(run_inputs, monkeypatch):
    root, docs, _, _ = run_inputs
    docs[0]['allocation'] = 'evaluation_reserved'
    monkeypatch.setattr(refine, 'load_inputs', lambda _: docs)
    with pytest.raises(ValueError, match='roster'):
        refine.run(root, root / 'research/result')
    assert not (root / 'research/result').exists()


def test_cli_uses_separate_candidate_output(monkeypatch, tmp_path):
    import sys
    from unittest.mock import Mock
    run = Mock()
    monkeypatch.setattr(refine, 'run', run)
    monkeypatch.setattr(refine, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['loan_reference_refinement'])
    assert refine.main() == 0
    run.assert_called_once_with(tmp_path, tmp_path / 'research/loan_reference_refinement_01')
    assert isinstance(run.call_args.args[1], Path)


def test_compare_document_rejects_faulty_candidate_source_ranges(run_inputs, monkeypatch):
    root, docs, parents, baseline = run_inputs
    source = (root / 'source.txt').read_text(encoding='utf-8')
    variants = refine.refine_parent(parents[0], source, TAXONOMY)
    variants['compact_cover'][0]['text'] = 'not the source'
    monkeypatch.setattr(refine, 'refine_parent', lambda *args: variants)
    with pytest.raises(ValueError, match='source span differs'):
        refine.compare_document(docs[0], [parents[0]], [baseline[0]], TAXONOMY, root)


def test_lost_tag_invariant_fails_closed(monkeypatch):
    from unittest.mock import Mock
    matcher = Mock(side_effect=[['A', 'B'], ['A'], ['A']])
    monkeypatch.setattr(refine, 'keyword_tags', matcher)
    record = {'doc_id': 'us_loan-test', 'chunk_id': 'us_loan-test#p0',
              'paragraph_start': 0, 'paragraph_end': 2000, 'original_tags': ['A', 'B']}
    with pytest.raises(ValueError, match='lost an original'):
        refine.refine_parent(record, 'x' * 2000, TAXONOMY)
