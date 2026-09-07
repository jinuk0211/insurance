from scripts_evolve.prepare_full_corpus import check_text, source_group, select_documents
import json

import pytest

from scripts_evolve import prepare_full_corpus as prep


def test_text_screening_rejects_broken_inputs():
    assert check_text('normal English loan agreement ' * 100) == []
    assert 'replacement_character' in check_text('A' * 2000 + '\ufffd')
    assert 'nul_character' in check_text('A' * 2000 + '\x00')
    assert 'under_1000_characters' in check_text('short')


def test_existing_issuer_directory_is_used_as_source_group():
    record = {'domain': 'us_card', 'path': 'data/2025_Q2/EXAMPLE_BANK/card.pdf'}
    assert source_group(record, {}) == 'us_card:example_bank'


def test_loan_cik_prevents_same_filer_cross_group_leakage():
    record = {'domain': 'us_loan', 'path': 'data/loan_data/us_loan_corpus/a.txt'}
    assert source_group(record, {'a.txt': {'cik': '000123'}}) == 'us_loan:cik:123'


def test_exact_source_hash_duplicates_cannot_fill_target():
    candidates = [{'domain': 'kr_insurance', 'status': 'success', 'source_sha256': 'same', 'text_sha256': 't', 'doc_id': str(i)}
                  for i in range(3)]
    selected = select_documents(candidates, per_domain=2)
    assert len(selected['kr_insurance']) == 1


def test_failed_extractions_do_not_count_as_documents():
    selected = select_documents([{'domain': 'us_card', 'status': 'failure', 'source_sha256': 'bad'}], 1000)
    assert selected['us_card'] == []


def test_text_identical_pdfs_are_not_independent_inputs():
    candidates = [{'domain': 'us_card', 'status': 'success', 'source_sha256': str(i),
                   'text_sha256': 'same-text', 'doc_id': str(i)} for i in range(2)]
    assert len(select_documents(candidates, 1000)['us_card']) == 1


def test_text_extraction_and_resume_validate_cached_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(prep, 'ROOT', tmp_path)
    path = tmp_path / 'loan.txt'
    path.write_text('credit agreement borrower loan terms ' * 100, encoding='utf-8')
    record = {'domain': 'us_loan', 'sha256': prep.sha256(path.read_bytes()),
              'path': 'loan.txt', 'source_group': 'loan:test'}
    output = str(tmp_path / 'research')
    result = prep.extract_record(record, output, {'version': 'test'})
    assert result['status'] == 'success'
    assert prep.extract_record(record, output, {'version': 'test'}) == result
    path.write_text('changed source', encoding='utf-8')
    with pytest.raises(ValueError, match='source hash'):
        prep.extract_record(record, output, {'version': 'test'})


def test_broken_pdf_failure_is_recorded_without_aborting_other_documents(tmp_path, monkeypatch):
    monkeypatch.setattr(prep, 'ROOT', tmp_path)
    path = tmp_path / 'broken.pdf'
    path.write_bytes(b'%PDF-1.7\nbroken')
    record = {'domain': 'us_card', 'sha256': prep.sha256(path.read_bytes()),
              'path': 'broken.pdf', 'source_group': 'card:test'}
    result = prep.extract_record(record, str(tmp_path / 'research'), {'version': 'test'})
    assert result['status'] == 'failure'
    assert result['error_type']
    saved = tmp_path / 'research/documents/us_card' / (record['sha256'] + '.json')
    assert json.loads(saved.read_text(encoding='utf-8')) == result
