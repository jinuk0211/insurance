"""The full-cohort preprocessing audit must retain failures and honest metrics."""
import math
import json

import numpy as np
import pytest

from scripts_evolve import e1_cohort as e1


@pytest.fixture(scope='module')
def originals():
    return e1.load_originals(e1.ROOT)


def test_keyword_retention_uses_source_present_unique_inventory():
    result = e1.metrics('FEE and arbitration', 'fee', ['fee', 'Fee', 'arbitration', 'default'], False)
    assert result['source_present_keywords'] == ['arbitration', 'fee']
    assert result['lost_keywords'] == ['arbitration']
    assert result['source_keyword_retention'] == 0.5
    assert result['legacy_inventory_hit_rate'] == 0.5
    assert result['inventory_size_with_duplicates'] == 4
    assert result['unique_inventory_size'] == 3


def test_absent_keywords_and_empty_source_are_undefined():
    result = e1.metrics('', '', ['fee'], False)
    assert result['source_keyword_retention'] is None
    assert result['character_ratio'] is None
    assert result['whitespace_unit_ratio'] is None
    assert result['tfidf_pairwise_lexical_cosine'] is None
    assert e1.metrics('plain words', '', ['fee'], False)['character_ratio'] == 0


def test_korean_matching_remains_case_sensitive_and_literal():
    result = e1.metrics('ABC 지급하지 않습니다', 'abc 지급하지\n않습니다', ['ABC', '지급하지 않습니다'], True)
    assert result['source_keyword_retention'] == 0


def test_lexical_cosine_identity_disjoint_and_empty():
    assert e1.lexical_cosine('fee fee interest', 'fee fee interest', False) == pytest.approx(1)
    assert e1.lexical_cosine('fee', 'arbitration', False) == 0
    assert e1.lexical_cosine('123', '', False) is None


@pytest.mark.parametrize('domain', e1.DOMAINS)
def test_original_loading_excludes_api_and_module_initializers(originals, domain):
    task = originals[domain]
    assert callable(task['strategy_ours'])
    assert 'call_claude' not in task
    assert 'ANTHROPIC_KEY' not in task


def test_original_card_rule_removes_only_original_selected_lines(originals):
    text = 'Member FDIC\nThe fee is $35 per late payment.\ncontinued on next page'
    assert originals['us_card']['strategy_ours'](text) == 'The fee is $35 per late payment.'


@pytest.mark.parametrize('domain', e1.DOMAINS)
def test_rank_matches_original_on_nontrivial_sentences(originals, domain):
    rng = np.random.default_rng(912)
    vocabulary = ['fee', 'payment', 'interest', 'default', 'loan', 'penalty', 'apr', 'account']
    sentences = [' '.join(rng.choice(vocabulary, size=int(rng.integers(8, 22)))) + ' Applies.' for _ in range(87)]
    text = '\n\n'.join(sentences) if domain != 'us_card' else ' '.join(sentences)
    actual, details = e1.fast_rank(text, domain, originals[domain]['tokenize'])
    expected = originals[domain]['strategy_textrank'](text)
    assert actual == expected
    assert details['implementation'] == 'algebraic_float64_adaptation_of_original'


@pytest.mark.parametrize('domain', e1.DOMAINS)
def test_rank_short_input_returns_exact_original_bytes(originals, domain):
    text = '  short input\r\n\f'
    actual, _ = e1.fast_rank(text, domain, originals[domain]['tokenize'])
    assert actual == text


def test_card_pairwise_weights_match_original_tfidf(originals):
    sentences = ['fee fee default', 'fee payment interest', 'totally unrelated', '']
    matrix = e1.count_matrix(sentences, originals['us_card']['tokenize'])
    actual = e1.card_weights(matrix, 0, len(sentences))
    expected = [[originals['us_card']['tfidf_cosine'](a, b) if i != j else 0
                 for j, b in enumerate(sentences)] for i, a in enumerate(sentences)]
    assert np.allclose(actual, expected, atol=1e-12)


def test_pagerank_dangling_rows_do_not_redistribute_mass():
    counts = e1.count_matrix(['fee', 'fee fee', 'unique'], str.split)
    scores = e1.pagerank_scores(counts)
    assert scores[2] == pytest.approx(0.15 / 3)
    assert scores[0] == pytest.approx(scores[1])
    assert sum(scores) < 1


def test_summary_keeps_review_failure_and_zero_keyword_denominators():
    rows = [
        {'domain': 'us_card', 'extraction_status': 'success', 'allocation': 'evaluation_reserved',
         'methods': {'raw': {'status': 'completed', 'metrics': e1.metrics('fee', 'fee', ['fee'], False)}}},
        {'domain': 'us_card', 'extraction_status': 'review_required', 'allocation': 'evaluation_reserved',
         'methods': {'raw': {'status': 'completed', 'metrics': e1.metrics('', '', ['fee'], False)}}},
        {'domain': 'us_card', 'extraction_status': 'success', 'allocation': 'development_exposed_or_linked',
         'methods': {'raw': {'status': 'failed', 'error': 'test failure'}}},
    ]
    summary = e1.summarize(rows)['domains']['us_card']['all']['raw']
    assert summary['input_documents'] == 3
    assert summary['status_counts'] == {'completed': 2, 'failed': 1}
    assert summary['extraction_status_counts'] == {'success': 2, 'review_required': 1}
    assert summary['source_keyword_retention']['defined_documents'] == 1
    assert summary['source_keyword_retention']['undefined_or_failed_documents'] == 2
    assert summary['source_keyword_retention']['mean_defined'] == 1


def test_nonfinite_metrics_cannot_be_published(tmp_path):
    with pytest.raises(ValueError):
        e1.write_once(tmp_path / 'bad.json', {'metric': math.nan})


def example_row(tmp_path, domain='kr_insurance', text='◆ 보험금 지급제한\r\n보험금을 지급하지 않습니다.\r\n'):
    source, extracted = tmp_path / 'source.pdf', tmp_path / 'source.txt'
    source.write_bytes(b'fixture source identity')
    extracted.write_bytes(text.encode('utf-8'))
    return {'doc_id': 'fixture', 'domain': domain, 'source_path': 'source.pdf',
            'source_sha256': e1.sha256(source.read_bytes()), 'text_path': 'source.txt',
            'text_sha256': e1.sha256(extracted.read_bytes()), 'characters': len(text),
            'allocation': 'development_exposed_or_linked', 'component_id': 'example',
            'pilot_membership': [], 'status': 'review_required', 'mechanical_issues': ['fixture_review']}


def test_evaluate_retains_review_row_native_clause_cut_and_exact_raw(tmp_path, originals):
    row = example_row(tmp_path)

    def parser(text, source_name):
        assert '\r' not in text
        assert source_name == 'source'
        return [{'raw_text': '보험금을 지급하지 않습니다.'}]

    result = e1.evaluate(row, originals, parser, tmp_path, tmp_path / 'output')
    assert result['extraction_status'] == 'review_required'
    assert result['mechanical_issues'] == ['fixture_review']
    assert len(result['methods']) == 4
    assert result['methods']['raw']['output_sha256'] == row['text_sha256']
    assert result['methods']['native_kr_parser_payload']['details']['parser_newlines_normalized']
    assert result['methods']['native_kr_parser_payload']['metrics']['source_keyword_retention'] == 0.5
    assert result['methods']['native_kr_parser_payload']['metrics']['lost_keywords'] == ['지급제한']
    assert e1.evaluate(row, originals, parser, tmp_path, tmp_path / 'output') == result


def test_no_parser_clauses_are_not_reported_as_success(tmp_path, originals):
    row = example_row(tmp_path)
    result = e1.evaluate(row, originals, lambda *a, **k: [], tmp_path, tmp_path / 'output')
    method = result['methods']['native_kr_parser_payload']
    assert method['status'] == 'no_parser_clauses'
    assert method['metrics']['source_keyword_retention'] == 0


def test_failed_method_not_silently_replaced_and_roster_kept(tmp_path, originals):
    row = example_row(tmp_path, 'us_loan', 'fee payment default')
    task = {d: dict(t) for d, t in originals.items()}

    def fail(_):
        raise RuntimeError('deliberate isolated method failure')

    task['us_loan']['strategy_ours'] = fail
    result = e1.evaluate(row, task, None, tmp_path, tmp_path / 'output')
    assert result['doc_id'] == row['doc_id']
    assert result['methods']['original_rule_filter']['status'] == 'failed'
    assert 'metrics' not in result['methods']['original_rule_filter']
    assert result['methods']['raw']['status'] == 'completed'
    assert len(result['methods']) == 3


def test_changed_source_or_artifact_stops_run(tmp_path, originals):
    row = example_row(tmp_path)
    (tmp_path / 'source.pdf').write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash changed'):
        e1.evaluate(row, originals, None, tmp_path, tmp_path / 'output')
    path = tmp_path / 'artifact.txt'
    e1.save_bytes(path, b'original')
    with pytest.raises(ValueError, match='artifact changed'):
        e1.save_bytes(path, b'different')


def test_reference_audit_does_not_use_reserved_or_select_by_agreement(tmp_path, originals):
    text = ' '.join(f'The payment default fee sentence number {i} applies.' for i in range(8))
    row = example_row(tmp_path, 'us_card', text)
    row['status'] = 'success'
    result = e1.reference_checks([row], originals, tmp_path)
    assert result['checked'] == 1
    assert result['checks'][0]['doc_id'] == 'fixture'
    row['allocation'] = 'evaluation_reserved'
    assert e1.reference_checks([row], originals, tmp_path)['checked'] == 0


@pytest.mark.parametrize('declarations,message', [
    ('tokenize = 1', 'preprocessing declarations'),
    ('\n'.join(f'def {name}(x): return x' for name in ['tokenize', 'strategy_raw', 'strategy_ours', 'strategy_textrank']), 'keyword inventory'),
])
def test_incomplete_originals_fail_closed(tmp_path, monkeypatch, declarations, message):
    (tmp_path / 'original.py').write_text(declarations, encoding='utf-8')
    monkeypatch.setattr(e1, 'ORIGINALS', {'kr_insurance': 'original.py'})
    with pytest.raises(ValueError, match=message):
        e1.load_originals(tmp_path)


def test_changed_character_count_fails_closed(tmp_path, originals):
    row = example_row(tmp_path)
    row['characters'] += 1
    with pytest.raises(ValueError, match='character count changed'):
        e1.evaluate(row, originals, None, tmp_path, tmp_path / 'output')


def test_main_rejects_output_outside_research(tmp_path, monkeypatch):
    monkeypatch.setattr(e1.sys, 'argv', ['e1', '--output', str(tmp_path)])
    with pytest.raises(SystemExit) as exc:
        e1.main()
    assert exc.value.code == 2


@pytest.mark.parametrize('changed', ['extraction', 'snapshot'])
def test_main_rejects_changed_allocation_or_snapshot(tmp_path, monkeypatch, changed):
    monkeypatch.setattr(e1, 'ROOT', tmp_path)
    implementation = tmp_path / 'scripts_evolve/e1_cohort.py'
    monkeypatch.setattr(e1, '__file__', str(implementation))
    output = tmp_path / 'research/result'
    monkeypatch.setattr(e1.sys, 'argv', ['e1', '--output', str(output)])
    sources = [{'doc_id': f'{d}-{i}', 'domain': d} for d in e1.DOMAINS for i in range(1000)]
    extractions = [dict(row, characters=4) for row in sources]
    allocation = [dict(row, characters=5 if changed == 'extraction' else 4) for row in sources]
    for path, rows in [('research/dataset_3000_v2/source_manifest.json', sources),
                       ('research/dataset_3000_v2/extraction_manifest.json', extractions),
                       ('research/main_3000_groups_v1/allocation_manifest.json', allocation)]:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({'documents': rows}), encoding='utf-8')
    for path in ['scripts_evolve/e1_cohort.py', 'scripts_evolve/main_preflight.py', 'scripts_evolve/full_corpus_v2.py',
                 'ECC_harness_v3_txt/scripts/parse_txt.py', *e1.ORIGINALS.values()]:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('# test fixture implementation', encoding='utf-8')
    if changed == 'snapshot':
        target = output / 'snapshot/scripts_evolve/e1_cohort.py'
        target.parent.mkdir(parents=True)
        target.write_text('# changed', encoding='utf-8')
    with pytest.raises(ValueError, match='Allocation extraction identity changed' if changed == 'extraction' else 'Snapshot changed'):
        e1.main()
