"""The full study cannot silently become a success-only or pilot-sized study."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

from scripts_evolve import main_preflight as preflight
from scripts_evolve.full_corpus_v2 import sha256
from scripts_evolve.main_preflight import (
    attach_leakage_components, audit_document, check_roster, group_evidence, summarize, usage_inventory,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def original_parser():
    path = ROOT / 'ECC_harness_v3_txt/scripts/parse_txt.py'
    spec = importlib.util.spec_from_file_location('original_txt_preflight_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.chunk_summary_doc


def make_document(tmp_path, domain='us_loan', text='Borrower shall pay interest.\n' * 80, status='success'):
    source = tmp_path / f'{domain}.txt'
    source.write_bytes(text.encode('utf-8'))
    digest = sha256(source.read_bytes())
    return {'doc_id': f'{domain}-{digest[:20]}', 'domain': domain,
            'source_path': source.name, 'source_sha256': digest,
            'text_path': source.name, 'text_sha256': digest,
            'status': status, 'characters': len(text), 'pilot_membership': [],
            'mechanical_issues': [] if status == 'success' else ['under_1000_characters']}


def test_roster_checks_identity_and_complete_domain_denominators(tmp_path):
    rows = [make_document(tmp_path, domain=d) for d in ('kr_insurance', 'us_card', 'us_loan')]
    assert check_roster(rows, deepcopy(rows), per_domain=1) is None
    with pytest.raises(ValueError, match='domain counts'):
        check_roster(rows, rows, per_domain=1000)
    for broken in (rows[:-1], rows + [rows[0]]):
        with pytest.raises(ValueError, match='extraction roster'):
            check_roster(rows, broken, per_domain=1)
    changed = deepcopy(rows)
    changed[0]['source_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='source identity'):
        check_roster(rows, changed, per_domain=1)
    changed = deepcopy(rows)
    changed[0]['pilot_membership'] = [{'doc_id': 'hidden_exposure'}]
    with pytest.raises(ValueError, match='source identity'):
        check_roster(rows, changed, per_domain=1)


def test_review_rows_survive_without_becoming_model_ready(tmp_path, original_parser):
    row = make_document(tmp_path, text='Short supplementary example.', status='needs_review')
    result = audit_document(row, tmp_path, original_parser, {})
    assert result['doc_id'] == row['doc_id']
    assert result['status'] == 'preprocessing_review'
    assert result['minimum_calls_if_current_ready_pipeline_completes'] == 0
    assert result['main_model_status'] == 'not_started'


def test_us_windows_cover_tail_and_card_report_call(tmp_path, original_parser):
    row = make_document(tmp_path, 'us_card', 'Agreement and conditions.\n' * 2100 + 'FINAL CLAUSE')
    result = audit_document(row, tmp_path, original_parser, {})
    assert result['source_covered_characters'] == row['characters']
    assert result['windows'] >= 3
    assert result['minimum_calls_if_current_ready_pipeline_completes'] == result['windows'] + 1
    assert result['conditional_card_validation_calls'] == 1


def test_original_kr_parser_truncation_measured_not_repaired(tmp_path, original_parser):
    row = make_document(tmp_path, 'kr_insurance', '◆ 보험금 지급사유\n' + '보험금 지급제한 조항입니다.\n' * 220)
    result = audit_document(row, tmp_path, original_parser, {})
    assert result['parsed_clauses'] == 1
    assert result['source_covered_characters'] == 1600
    assert result['source_coverage_fraction'] < 0.5
    assert result['minimum_calls_if_current_ready_pipeline_completes'] == 3
    assert result['parser_at_1600_character_clauses'] == 1


def test_unsupported_kr_format_not_counted_as_success(tmp_path, original_parser):
    row = make_document(tmp_path, 'kr_insurance', '계약 내용을 설명하는 머리말입니다.\n' * 100)
    result = audit_document(row, tmp_path, original_parser, {})
    assert result['status'] == 'parser_unsupported'
    assert result['source_coverage_fraction'] == 0


def test_corruption_or_path_escape_fails_closed(tmp_path, original_parser):
    row = make_document(tmp_path)
    (tmp_path / row['source_path']).write_text('changed', encoding='utf-8')
    with pytest.raises(ValueError, match='hash'):
        audit_document(row, tmp_path, original_parser, {})
    row['source_path'] = '../outside.txt'
    with pytest.raises(ValueError, match='outside'):
        audit_document(row, tmp_path, original_parser, {})


def test_metadata_groups_are_provenance_labels_not_verified_issuer_claims():
    row = {'domain': 'kr_insurance', 'source_sha256': 'abc', 'source_path': 'raw/41879_3.pdf'}
    record = {'sha256': 'abc', 'product_name': 'L51 라이나생명 L510000 상품',
              'source_url': 'https://pub.insure.or.kr/FileDown.do?fileNo=41879&seq=3'}
    group = group_evidence(row, {'kr': [record], 'loan': [], 'card': []})
    assert group['labels'] == ['kr_insurer:라이나생명']
    assert group['identity_verified'] is False
    assert group['evidence'][0]['source_url'] == record['source_url']
    assert group['evaluation_split'] is None


def test_loan_group_uses_cik_not_company_filename_or_accession_filer():
    row = {'domain': 'us_loan', 'source_sha256': 'abc', 'source_path': 'data/loan_data/us_loan_corpus/loan.txt'}
    record = {'out': 'loan.txt', 'cik': '0001805077', 'accession': '0001628280-22-021392',
              'url': 'https://www.sec.gov/Archives/edgar/data/1805077/000162828022021392/ex101.htm'}
    group = group_evidence(row, {'loan': [record], 'kr': [], 'card': []})
    assert group['labels'] == ['sec_registrant:1805077']
    record['sha256'] = 'changed'
    with pytest.raises(ValueError, match='metadata hash'):
        group_evidence(row, {'loan': [record], 'kr': [], 'card': []})


def test_blank_extraction_collision_does_not_create_contract_group(tmp_path, original_parser):
    row = make_document(tmp_path, 'us_card', '\n\f\n', 'needs_review')
    result = audit_document(row, tmp_path, original_parser, {})
    assert result['nonempty_exact_text_group'] is None


def test_summary_keeps_all_inputs_and_does_not_promote_calls_to_results(tmp_path, original_parser):
    rows = [audit_document(make_document(tmp_path, d), tmp_path, original_parser, {})
            for d in ('kr_insurance', 'us_card', 'us_loan')]
    result = summarize(rows, {'call_count': 1099, 'observed_tokens': 50, 'unknown_usage_calls': 1})
    assert result['main_cohort_inputs'] == 3
    assert result['main_model_documents_completed'] == 0
    assert result['fits_remaining_historical_call_envelope'] is False
    assert result['cost_usd'] is None
    assert result['held_out_evaluation_ready'] is False


def test_usage_keeps_failures_and_unknown_tokens(tmp_path):
    folder = tmp_path / 'research/harness_v3/example/calls/one'
    folder.mkdir(parents=True)
    (folder / 'record.json').write_text(json.dumps({'status': 'failure'}), encoding='utf-8')
    value = usage_inventory(tmp_path)
    assert value['call_count'] == value['unknown_usage_calls'] == 1
    assert value['records'][0]['status'] == 'failure'
    assert value['observed_tokens'] == 0
    assert value['total_tokens_known'] is False


@pytest.mark.parametrize('domain', ['kr_insurance', 'us_card'])
def test_raw_carriage_returns_not_mistaken_for_tampering(tmp_path, original_parser, domain):
    text = '◆ 보험금 지급사유\r\n' + '보험금 지급제한입니다.\r\n' * 100
    row = make_document(tmp_path, domain)
    (tmp_path / row['text_path']).write_bytes(text.encode())
    row.update(source_sha256=sha256(text.encode()), text_sha256=sha256(text.encode()), characters=len(text))
    result = audit_document(row, tmp_path, original_parser, {})
    assert result['source_characters'] == len(text)
    if domain == 'kr_insurance':
        assert result['parser_input_characters'] == len(text.replace('\r\n', '\n'))
        assert result['parser_input_newline_normalized'] is True
    else:
        assert result['source_covered_characters'] == len(text)


def test_leakage_components_propagate_pilot_exposure_transitively():
    rows = [{'doc_id': str(i), 'grouping': {'labels': labels}, 'pilot_membership': pilot,
             'nonempty_exact_text_group': exact}
            for i, (labels, pilot, exact) in enumerate([
                (['issuer:a'], [{'old': 'pilot'}], None), (['issuer:a'], [], 'text:x'),
                (['issuer:b'], [], 'text:x'), ([], [], None), ([], [], None)])]
    attach_leakage_components(rows)
    assert len({r['leakage_component_id'] for r in rows[:3]}) == 1
    assert all(r['leakage_component_has_pilot_member'] for r in rows[:3])
    assert rows[3]['leakage_component_id'] != rows[4]['leakage_component_id']
    assert all(r['evaluation_split'] is None for r in rows)


def test_invalid_sec_url_not_used_as_group_evidence():
    row = {'domain': 'us_loan', 'source_sha256': 'abc', 'source_path': 'loan.txt'}
    record = {'out': 'loan.txt', 'cik': '00123', 'url': 'https://www.sec.gov/Archives/edgar/data/999/ex10.htm'}
    with pytest.raises(ValueError, match='CIK'):
        group_evidence(row, {'loan': [record]})


def test_missing_extracted_text_is_failure_not_an_empty_success(tmp_path, original_parser):
    row = make_document(tmp_path)
    del row['text_path']
    with pytest.raises(ValueError, match='lacks text'):
        audit_document(row, tmp_path, original_parser, {})
    row['status'] = 'failure'
    assert audit_document(row, tmp_path, original_parser, {})['status'] == 'preprocessing_review'


def test_character_count_and_original_parser_alignment_are_checked(tmp_path, original_parser):
    row = make_document(tmp_path, 'kr_insurance')
    row['characters'] += 1
    with pytest.raises(ValueError, match='character count'):
        audit_document(row, tmp_path, original_parser, {})
    row['characters'] -= 1
    def wrong_parser(*args, **kwargs):
        return [{'raw_text': 'not in source'}]
    with pytest.raises(ValueError, match='aligned'):
        audit_document(row, tmp_path, wrong_parser, {})


def test_cli_rejects_output_outside_research(tmp_path, monkeypatch):
    monkeypatch.setattr('sys.argv', ['preflight', '--output', str(tmp_path)])
    with pytest.raises(SystemExit) as exc:
        preflight.main()
    assert exc.value.code == 2


def test_offline_cli_writes_once_and_rejects_snapshot_tampering(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    root.mkdir()
    rows = [make_document(root, domain=d) for d in ('kr_insurance', 'us_card', 'us_loan')]
    for relative, value in [
        ('research/dataset_3000_v2/source_manifest.json', {'documents': rows}),
        ('research/dataset_3000_v2/extraction_manifest.json', {'documents': rows}),
        ('data/us_card_supplement_cfpb_current/_manifest.json', {'records': []}),
    ]:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')
    for relative in ('scripts_evolve/main_preflight.py', 'scripts_evolve/us_tasks.py',
                     'scripts_evolve/native_schemas.py', 'scripts_evolve/full_corpus_v2.py',
                     'ECC_harness_v3_txt/data/raw/contracts/_collection_manifest.jsonl',
                     'data/loan_data/us_loan_corpus/_manifest.jsonl'):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'')
    path = root / 'ECC_harness_v3_txt/scripts/parse_txt.py'
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / 'ECC_harness_v3_txt/scripts/parse_txt.py', path)
    output = root / 'research/preflight'
    monkeypatch.setattr(preflight, 'ROOT', root)
    monkeypatch.setattr(preflight, '__file__', str(root / 'scripts_evolve/main_preflight.py'))
    # Exercise the real roster check on a deliberately small unit-test cohort.
    monkeypatch.setattr(preflight, 'check_roster', lambda a, b: check_roster(a, b, per_domain=1))
    monkeypatch.setattr('sys.argv', ['preflight', '--output', str(output)])
    assert preflight.main() == 0
    original = (output / 'manifest.json').read_bytes()
    assert preflight.main() == 0
    assert (output / 'manifest.json').read_bytes() == original
    (output / 'snapshot/scripts_evolve/us_tasks.py').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='snapshot changed'):
        preflight.main()
