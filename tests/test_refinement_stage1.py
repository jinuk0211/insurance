"""Constrained preprocessing candidates must not win by hiding failures."""
from copy import deepcopy

import pytest

from scripts_evolve import refinement_stage1 as stage


def test_baseline_configuration_preserves_exact_original_filter_output():
    raw = 'raw source'
    baseline = 'original\r\nfiltered  text\n'
    assert stage.transform(raw, baseline, stage.BASELINE) == baseline


def test_candidate_really_changes_only_declared_line_rules():
    config = deepcopy(stage.BASELINE)
    config['drop_exact_lines'] = ['Member FDIC']
    config['collapse_spaces'] = True
    text = 'Member FDIC\nThe fee is  $35.\nMember FDIC insurance terms'
    assert stage.transform(text, text, config) == 'The fee is $35.\nMember FDIC insurance terms'


def test_raw_base_can_restore_original_filter_losses():
    config = deepcopy(stage.BASELINE)
    config['base'] = 'raw'
    assert stage.transform('fee terms', 'terms', config) == 'fee terms'


@pytest.mark.parametrize('change', [
    {'drop_line_prefixes': ['']}, {'drop_line_prefixes': ['fee']},
    {'drop_exact_lines': ['a\nb']}, {'base': 'python_exec'}, {'invented': True},
    {'drop_exact_lines': ['Member FDIC', 'member fdic']},
])
def test_arbitrary_or_underspecified_mutation_is_rejected(change):
    config = {**deepcopy(stage.BASELINE), **change}
    with pytest.raises(ValueError):
        stage.validate_config(config)


def test_keyword_deletion_fails_even_when_compression_improves():
    violations = stage.guard('fee terms\nboilerplate', 'terms', ['fee'], False)
    assert 'lost_source_keyword' in violations


def test_financial_values_and_occurrences_cannot_be_dropped():
    assert 'lost_financial_value' in stage.guard('The fee is $35 and $35.', 'The fee is $35.', ['fee'], False)
    assert 'lost_financial_value' in stage.guard('금액은 100만원입니다.', '금액은 입니다.', ['금액'], True)


def test_baseline_is_not_punished_for_preexisting_extraction_issues():
    assert stage.guard('', '', ['fee'], False) == []
    assert stage.guard('No keyword here.', 'No keyword here.', ['fee'], False) == []


def test_empty_or_aggressively_reduced_output_is_ineligible():
    assert 'empty_output' in stage.guard('some meaningful text', '', [], False)
    assert 'excessive_unit_loss' in stage.guard('one two three four five six seven eight', 'one', [], False)


def test_better_candidate_must_be_feasible_and_strictly_better():
    incumbent = {'eligible': True, 'output_whitespace_units': 100, 'output_characters': 900}
    assert stage.better({'eligible': True, 'output_whitespace_units': 99, 'output_characters': 999}, incumbent)
    assert not stage.better({**incumbent}, incumbent)
    assert not stage.better({'eligible': False, 'output_whitespace_units': 1, 'output_characters': 1}, incumbent)


def test_evaluation_keeps_all_rows_and_marks_gate_failure(tmp_path):
    cases = [
        {'doc_id': 'a', 'domain': 'us_card', 'raw': 'fee $35 and terms', 'baseline': 'fee $35 and terms',
         'source_sha256': 'a', 'text_sha256': 'b', 'extraction_status': 'success', 'allocation': 'development_exposed_or_linked'},
        {'doc_id': 'b', 'domain': 'us_card', 'raw': '', 'baseline': '', 'source_sha256': 'c', 'text_sha256': 'd',
         'extraction_status': 'needs_review', 'allocation': 'development_exposed_or_linked'},
    ]
    config = {**deepcopy(stage.BASELINE), 'drop_exact_lines': ['fee $35 and terms']}
    result = stage.evaluate(cases, config, ['fee'], tmp_path)
    assert result['input_documents'] == 2
    assert not result['eligible']
    assert result['gate_failed_documents'] == 1
    assert result['extraction_status_counts'] == {'success': 1, 'needs_review': 1}
    assert (tmp_path / 'documents/a.json').exists()
    assert (tmp_path / 'documents/b.json').exists()


def test_line_evidence_counts_documents_not_repetitions():
    cases = [{'baseline': 'boilerplate\nboilerplate\nfee 123'}, {'baseline': 'boilerplate\nother text'}]
    evidence = stage.line_evidence(cases)
    assert evidence == [{'line': 'boilerplate', 'document_count': 2}]


def test_declared_blank_and_separator_rules_and_raw_passthrough():
    config = {**deepcopy(stage.BASELINE), 'base': 'raw', 'drop_separator_lines': True, 'collapse_blank_lines': True}
    assert stage.transform('legal text\n\n\nnext text\n-----', 'unused baseline', config) == 'legal text\n\nnext text'


def test_financial_whitespace_normalization_keeps_values():
    assert 'lost_financial_value' not in stage.guard('fee is $  35 and 12  %', 'fee is $ 35 and 12 %', ['fee'], False)


def test_punctuation_cannot_mask_loss_of_all_lexical_content():
    text = 'Important obligations apply.\n' + ' '.join(['!'] * 100)
    config = {**deepcopy(stage.BASELINE), 'drop_exact_lines': ['Important obligations apply.']}
    output = stage.transform(text, text, config)
    assert 'lexical_drift' in stage.guard(text, output, ['fee'], False)
