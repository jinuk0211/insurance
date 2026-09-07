"""The main cohort must not shrink when preprocessing fails."""
import json
import sys

import pymupdf
import pytest

from scripts_evolve import full_corpus_v2 as corpus


def inventory_row(value='a'):
    return {'path': f'data/{value}.txt', 'sha256': value * 64, 'bytes': 1001,
            'duplicate_of': None, 'mechanical_issues': []}


def test_cohort_keeps_all_inputs_and_marks_old_pilot_membership():
    row = inventory_row()
    inventory = {'domains': [{'domain': 'kr_insurance', 'records': [row]}]}
    pilots = [{'manifest': 'old/manifest.json', 'documents': [
        {'doc_id': 'pilot-1', 'original_pdf_sha256': row['sha256'], 'split': 'test'}]}]
    cohort = corpus.build_cohort(inventory, pilots, domains=('kr_insurance',), per_domain=1)
    assert len(cohort) == 1
    assert cohort[0]['pilot_membership'][0]['doc_id'] == 'pilot-1'
    assert cohort[0]['held_out_eligible'] is False
    assert cohort[0]['evaluation_split'] is None


def test_cohort_rejects_wrong_count_instead_of_silently_sampling():
    inventory = {'domains': [{'domain': 'kr_insurance', 'records': [inventory_row()]}]}
    with pytest.raises(ValueError, match='expected 2'):
        corpus.build_cohort(inventory, [], domains=('kr_insurance',), per_domain=2)


def test_cohort_rejects_duplicate_hash_claims():
    inventory = {'domains': [{'domain': 'kr_insurance', 'records': [inventory_row(), inventory_row()]}]}
    with pytest.raises(ValueError, match='duplicate'):
        corpus.build_cohort(inventory, [], domains=('kr_insurance',), per_domain=2)


def test_cohort_rejects_missing_domain_and_does_not_assert_unseen_status():
    with pytest.raises(ValueError, match='Missing'):
        corpus.build_cohort({'domains': []}, [])
    inventory = {'domains': [{'domain': 'us_card', 'records': [inventory_row()]}]}
    row = corpus.build_cohort(inventory, [], domains=('us_card',), per_domain=1)[0]
    assert row['held_out_eligible'] is None


@pytest.mark.parametrize('text,issue', [
    ('short', 'under_1000_characters'),
    ('a' * 1000 + '\x01', 'unexpected_control_characters'),
    ('a' * 1000 + '\ufffd', 'replacement_character'),
    ('a' * 1000 + '\ue001' * 3, 'private_use_character_density'),
])
def test_quality_flags_do_not_modify_raw_text(text, issue):
    assert issue in corpus.quality_flags(text)


def test_expected_page_break_controls_are_not_corruption():
    assert corpus.quality_flags('text \t\r\n\f' * 200) == []


def test_real_pdf_extracts_every_page_and_preserves_cache(tmp_path):
    source = tmp_path / 'source.pdf'
    with pymupdf.open() as doc:
        for marker in ('FIRST', 'SECOND'):
            page = doc.new_page()
            page.insert_textbox((30, 30, 500, 750), (marker + ' complete text\n') * 40)
        doc.save(source)
    row = {'doc_id': 'kr_insurance-test', 'domain': 'kr_insurance',
           'source_path': 'source.pdf', 'source_sha256': corpus.sha256(source.read_bytes())}
    fingerprint = {'test': True}
    result = corpus.extract(row, str(tmp_path), str(tmp_path / 'out'), fingerprint)
    text = (tmp_path / result['text_path']).read_text(encoding='utf-8')
    assert result['status'] == 'success'
    assert result['pages'] == 2
    assert 'FIRST' in text and 'SECOND' in text and '\n\f\n' in text
    assert corpus.extract(row, str(tmp_path), str(tmp_path / 'out'), fingerprint) == result
    source.write_bytes(b'changed')
    with pytest.raises(ValueError, match='source hash'):
        corpus.extract(row, str(tmp_path), str(tmp_path / 'out'), fingerprint)


def test_short_text_is_preserved_but_not_promoted_to_ready(tmp_path):
    (tmp_path / 'short.txt').write_text('short', encoding='utf-8')
    row = {'doc_id': 'us_loan-short', 'domain': 'us_loan', 'source_path': 'short.txt',
           'source_sha256': corpus.sha256(b'short')}
    result = corpus.extract(row, str(tmp_path), str(tmp_path / 'out'), {})
    assert result['status'] == 'needs_review'
    assert (tmp_path / result['text_path']).read_text(encoding='utf-8') == 'short'
    assert json.loads((tmp_path / 'out/documents/us_loan' / (row['source_sha256'] + '.json')).read_text()) == result


def test_broken_pdf_is_a_record_not_a_missing_document(tmp_path):
    (tmp_path / 'bad.pdf').write_bytes(b'%PDF-broken')
    row = {'doc_id': 'kr_insurance-bad', 'domain': 'kr_insurance', 'source_path': 'bad.pdf',
           'source_sha256': corpus.sha256(b'%PDF-broken')}
    result = corpus.extract(row, str(tmp_path), str(tmp_path / 'out'), {})
    assert result['status'] == 'failure'
    assert result['error_type']


def test_cached_text_tampering_is_rejected(tmp_path):
    source = tmp_path / 'input.txt'
    source.write_text('content ' * 200, encoding='utf-8')
    row = {'doc_id': 'us_loan-text', 'domain': 'us_loan', 'source_path': 'input.txt',
           'source_sha256': corpus.sha256(source.read_bytes())}
    result = corpus.extract(row, str(tmp_path), str(tmp_path / 'out'), {})
    (tmp_path / result['text_path']).write_text('changed', encoding='utf-8')
    with pytest.raises(ValueError, match='text hash'):
        corpus.extract(row, str(tmp_path), str(tmp_path / 'out'), {})


def test_cached_protocol_change_and_outside_source_are_rejected(tmp_path):
    (tmp_path / 'input.txt').write_text('content ' * 200, encoding='utf-8')
    row = {'doc_id': 'us_loan-text', 'domain': 'us_loan', 'source_path': 'input.txt',
           'source_sha256': corpus.sha256((tmp_path / 'input.txt').read_bytes())}
    corpus.extract(row, str(tmp_path), str(tmp_path / 'out'), {})
    with pytest.raises(ValueError, match='identity'):
        corpus.extract(row, str(tmp_path), str(tmp_path / 'out'), {'changed': True})
    with pytest.raises(ValueError, match='Unsupported source'):
        corpus.extract({**row, 'source_path': '../outside.txt'}, str(tmp_path), str(tmp_path / 'out'), {})


def test_write_once_never_overwrites_different_evidence(tmp_path):
    path = tmp_path / 'evidence.json'
    corpus.write_once(path, {'value': 1})
    corpus.write_once(path, {'value': 1})
    with pytest.raises(ValueError, match='Existing evidence differs'):
        corpus.write_once(path, {'value': 2})
    assert json.loads(path.read_text()) == {'value': 1}


@pytest.mark.parametrize('orphan_text,expected_status', [('short', 'needs_review'), ('different', 'failure')])
def test_orphan_text_reuse_never_overwrites_mismatched_bytes(tmp_path, orphan_text, expected_status):
    (tmp_path / 'short.txt').write_text('short', encoding='utf-8')
    digest = corpus.sha256(b'short')
    folder = tmp_path / 'out/documents/us_loan'
    folder.mkdir(parents=True)
    orphan = folder / f'{digest}.txt'
    orphan.write_text(orphan_text, encoding='utf-8')
    row = {'doc_id': 'us_loan-short', 'domain': 'us_loan', 'source_path': 'short.txt',
           'source_sha256': digest}
    result = corpus.extract(row, str(tmp_path), str(tmp_path / 'out'), {})
    assert result['status'] == expected_status
    assert orphan.read_text(encoding='utf-8') == orphan_text


def test_cli_rejects_output_outside_research_before_reading_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['full_corpus_v2', '--inventory', 'missing.json', '--output', str(tmp_path)])
    with pytest.raises(SystemExit) as error:
        corpus.main()
    assert error.value.code == 2


def test_snapshot_denominator_includes_failures_and_duplicate_texts():
    cohort = [{'doc_id': str(i), 'domain': 'us_card'} for i in range(3)]
    results = [{'doc_id': '0', 'domain': 'us_card', 'status': 'success', 'text_sha256': 'same'},
               {'doc_id': '1', 'domain': 'us_card', 'status': 'success', 'text_sha256': 'same'},
               {'doc_id': '2', 'domain': 'us_card', 'status': 'failure'}]
    snapshot = corpus.summarize(cohort, results)
    assert snapshot['total_inputs'] == 3
    assert snapshot['status_counts']['us_card'] == {'success': 2, 'failure': 1}
    assert snapshot['exact_text_duplicate_groups'] == [['0', '1']]
    assert snapshot['all_inputs_mechanically_ready'] is False
    with pytest.raises(ValueError, match='Missing or repeated'):
        corpus.summarize(cohort, results[:2])
