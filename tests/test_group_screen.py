"""Prevent blank collisions, related-source leakage and denominator shrinkage."""
from copy import deepcopy
import json

import pytest

from scripts_evolve import group_screen as screen
from scripts_evolve.full_corpus_v2 import sha256
from scripts_evolve.group_screen import (
    add_path_group, allocate, fingerprint, near_edges, sketch_jaccard, token_shingles,
)


def words(count=300):
    return ' '.join(f'word{i}' for i in range(count))


def source(tmp_path, identity, text, group, domain='us_card', pilot=False, status='success'):
    path = tmp_path / f'{identity}.txt'
    path.write_bytes(text.encode())
    digest = sha256(path.read_bytes())
    return {'doc_id': identity, 'domain': domain, 'source_path': path.name,
            'source_sha256': digest, 'text_path': path.name, 'text_sha256': digest,
            'status': status, 'pilot_membership': [{'old': 'dev'}] if pilot else [],
            'grouping': {'labels': [group] if group else [], 'evidence': [], 'identity_verified': False},
            'leakage_component_id': group or identity, 'nonempty_exact_text_group': None}


def test_shingles_retain_numbers_but_normalize_case_spacing_and_unicode():
    assert token_shingles('Loan   ＲＡＴＥ 10 payable monthly') == token_shingles('loan rate 10 payable monthly')
    assert token_shingles('loan rate 11 payable monthly') != token_shingles('loan rate 10 payable monthly')
    assert token_shingles('보험금 면책 지급 제한 해지')
    assert token_shingles('\n\f\n') == set()


def test_sketch_jaccard_is_exact_when_sets_fit():
    assert sketch_jaccard({1, 2, 3}, {2, 3, 4}) == .5
    assert sketch_jaccard(set(), set()) == 0
    assert sketch_jaccard({1, 2, 3}, {1, 2, 3}) == 1


def test_fingerprint_keeps_original_identity_and_blocks_empty_collision(tmp_path):
    row = source(tmp_path, 'blank', '\n\f\n', None, status='needs_review')
    value = fingerprint(row, tmp_path)
    assert value['sketch'] == []
    assert value['screenable'] is False
    assert value['source_sha256'] == row['source_sha256']
    assert value['extraction_status'] == 'needs_review'


def test_fingerprint_rejects_text_tampering_and_paths_outside_root(tmp_path):
    row = source(tmp_path, 'a', words(), 'issuer:a')
    row['text_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='hash'):
        fingerprint(row, tmp_path)
    row['source_path'] = '../outside.txt'
    with pytest.raises(ValueError, match='outside'):
        fingerprint(row, tmp_path)


def test_missing_text_still_has_a_row(tmp_path):
    row = source(tmp_path, 'a', words(), None, status='failure')
    row.pop('text_path')
    assert fingerprint(row, tmp_path)['screenable'] is False
    row['status'] = 'success'
    with pytest.raises(ValueError, match='missing text'):
        fingerprint(row, tmp_path)


def test_nested_product_path_recovers_only_provisional_insurer_label():
    row = {'domain': 'kr_insurance', 'source_path': 'ECC_harness_v3_txt/data/raw/contracts/종신보험/푸본현대생명_상품/일부지급형.pdf',
           'grouping': {'labels': [], 'evidence': [], 'identity_verified': False}}
    original = deepcopy(row)
    result = add_path_group(row)
    assert result['grouping']['labels'] == ['kr_insurer:푸본현대생명']
    assert result['grouping']['identity_verified'] is False
    assert row == original
    numeric = deepcopy(original)
    numeric['source_path'] = 'ECC_harness_v3_txt/data/raw/contracts/종신보험/41879_3.pdf'
    assert add_path_group(numeric)['grouping']['labels'] == []


def test_near_copy_is_verified_from_full_shingle_sets(tmp_path):
    rows = [source(tmp_path, 'a', words(1000), 'issuer:a', pilot=True),
            source(tmp_path, 'b', words(1000) + ' changed clause wording', 'issuer:b'),
            source(tmp_path, 'c', 'unrelated letters words example enough characters ' * 40, 'issuer:c')]
    prints = [fingerprint(row, tmp_path) for row in rows]
    edges, counts = near_edges(rows, prints, tmp_path)
    assert len(edges) == 1
    assert edges[0]['documents'] == ['a', 'b']
    assert edges[0]['hashed_shingle_jaccard'] >= .9
    assert counts['accepted_cross_component_edges'] == 1


def test_candidates_below_exact_threshold_or_in_same_component_not_accepted(tmp_path):
    rows = [source(tmp_path, 'a', words(), 'same'), source(tmp_path, 'b', words(), 'same')]
    assert near_edges(rows, [fingerprint(r, tmp_path) for r in rows], tmp_path)[0] == []
    rows[1]['leakage_component_id'] = 'other'
    (tmp_path / rows[1]['source_path']).write_bytes(('totally different ' + words(500)).encode())
    digest = sha256((tmp_path / rows[1]['source_path']).read_bytes())
    rows[1].update(source_sha256=digest, text_sha256=digest)
    prints = [fingerprint(r, tmp_path) for r in rows]
    # A permissive candidate screen is still followed by the fixed exact gate.
    assert near_edges(rows, prints, tmp_path, candidate_threshold=0)[0] == []


def test_allocation_keeps_every_input_and_propagates_development_exposure(tmp_path):
    rows = [source(tmp_path, 'a', words(), 'issuer:a', pilot=True),
            source(tmp_path, 'b', words(), 'issuer:b'),
            source(tmp_path, 'c', words(), 'issuer:b'),
            source(tmp_path, 'd', words(), 'issuer:d'),
            source(tmp_path, 'e', '\n\f\n', None, status='needs_review')]
    original = deepcopy(rows)
    result = allocate(rows, [{'documents': ['a', 'b']}])
    assert len(result) == 5
    assert {r['doc_id'] for r in result} == {r['doc_id'] for r in rows}
    assert {r['allocation'] for r in result[:3]} == {'development_exposed_or_linked'}
    assert result[3]['allocation'] == 'evaluation_reserved'
    assert result[4]['allocation'] == 'group_review_required'
    assert all(r['held_out_verified'] is False for r in result)
    assert rows == original


def test_allocation_rejects_foreign_or_cross_domain_edges(tmp_path):
    rows = [source(tmp_path, 'a', words(), 'x'), source(tmp_path, 'b', words(), 'y', domain='us_loan')]
    for pair in (['a', 'foreign'], ['a', 'b'], ['a', 'a']):
        with pytest.raises(ValueError, match='edge'):
            allocate(rows, [{'documents': pair}])


def test_fingerprint_replay_is_deterministic_json(tmp_path):
    row = source(tmp_path, 'a', words(), 'issuer:a')
    first = fingerprint(row, tmp_path)
    assert json.loads(json.dumps(first)) == fingerprint(row, tmp_path)
    assert len(first['sketch']) == 128


def test_allocation_is_order_independent(tmp_path):
    rows = [source(tmp_path, 'a', words(), 'x'), source(tmp_path, 'b', words(), 'x', pilot=True)]
    first = {r['doc_id']: (r['component_id'], r['allocation']) for r in allocate(rows, [])}
    second = {r['doc_id']: (r['component_id'], r['allocation']) for r in allocate(list(reversed(rows)), [])}
    assert first == second


def test_fingerprint_roster_identity_and_duplicate_allocations_rejected(tmp_path):
    row = source(tmp_path, 'a', words(), 'x')
    value = fingerprint(row, tmp_path)
    with pytest.raises(ValueError, match='roster mismatch'):
        near_edges([row], [], tmp_path)
    value['source_sha256'] = 'tampered'
    with pytest.raises(ValueError, match='identity mismatch'):
        near_edges([row], [value], tmp_path)
    with pytest.raises(ValueError, match='Duplicate allocation'):
        allocate([row, row], [])


def test_cli_rejects_outside_output(tmp_path, monkeypatch):
    monkeypatch.setattr('sys.argv', ['group_screen', '--output', str(tmp_path)])
    with pytest.raises(SystemExit) as exc:
        screen.main()
    assert exc.value.code == 2


@pytest.mark.parametrize('fault,message', [
    ('parent', 'parent identity'), ('roster', 'roster differs'),
    ('exposure', 'source/exposure identity'), ('snapshot', 'snapshot changed'),
])
def test_cli_frozen_evidence_guards(tmp_path, monkeypatch, fault, message):
    rows = [{'doc_id': f'{d}-{i}', 'domain': d, 'source_path': f'{d}/{i}.txt',
             'source_sha256': sha256(f'{d}/{i}'.encode()), 'pilot_membership': []}
            for d in screen.DOMAINS for i in range(1000)]
    source_path = tmp_path / 'research/dataset_3000_v2/source_manifest.json'
    extraction_path = source_path.with_name('extraction_manifest.json')
    source_path.parent.mkdir(parents=True)
    for path in (source_path, extraction_path):
        path.write_text(json.dumps({'documents': rows}), encoding='utf-8')
    previous = {'protocol': {'source_manifest_sha256': sha256(source_path.read_bytes()),
                            'extraction_manifest_sha256': sha256(extraction_path.read_bytes())},
                'documents': [{**row, 'grouping': {'labels': ['group'], 'evidence': []},
                               'leakage_component_id': row['doc_id'], 'nonempty_exact_text_group': None} for row in rows]}
    if fault == 'parent':
        previous['protocol']['source_manifest_sha256'] = 'wrong'
    elif fault == 'roster':
        previous['documents'].pop()
    elif fault == 'exposure':
        previous['documents'][0]['pilot_membership'] = [{'hidden': True}]
    path = tmp_path / 'research/main_3000_preflight_v2/manifest.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(previous), encoding='utf-8')
    output = tmp_path / 'research/groups'
    if fault == 'snapshot':
        for name in ('group_screen.py', 'main_preflight.py', 'full_corpus_v2.py'):
            path = tmp_path / 'scripts_evolve' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'original')
        path = output / 'snapshot/scripts_evolve/group_screen.py'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'tampered')
    monkeypatch.setattr(screen, 'ROOT', tmp_path)
    monkeypatch.setattr(screen, '__file__', str(tmp_path / 'scripts_evolve/group_screen.py'))
    monkeypatch.setattr('sys.argv', ['group_screen', '--output', str(output)])
    with pytest.raises(ValueError, match=message):
        screen.main()
