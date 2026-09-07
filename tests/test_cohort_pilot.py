"""Existing KR development PDFs must use the actual main-cohort text version."""
from copy import deepcopy

import pytest

from scripts_evolve.cohort_pilot import bridge_documents


def fixtures():
    old = [{'doc_id': f'old-{i}', 'domain': 'kr_insurance', 'split': 'dev',
            'source_sha256': str(i), 'text_sha256': f'oldtext-{i}'} for i in range(4)]
    main = [{'doc_id': f'main-{i}', 'domain': 'kr_insurance', 'source_sha256': str(i),
             'source_path': f'{i}.pdf', 'text_sha256': f'newtext-{i}', 'text_path': f'{i}.txt',
             'status': 'success'} for i in range(4)]
    groups = [{'doc_id': r['doc_id'], 'source_sha256': r['source_sha256'],
               'allocation': 'development_exposed_or_linked'} for r in main]
    return old, main, groups


def test_bridge_keeps_same_originals_but_changes_to_main_text():
    old, main, groups = fixtures()
    baseline = deepcopy((old, main, groups))
    result = bridge_documents(old, main, groups)
    assert {r['source_sha256'] for r in result} == {r['source_sha256'] for r in old}
    assert {r['text_sha256'] for r in result} == {r['text_sha256'] for r in main}
    assert all(r['split'] == 'dev' for r in result)
    assert all(r['historical_pilot']['text_version_changed'] for r in result)
    assert (old, main, groups) == baseline


@pytest.mark.parametrize('fault', ['reserved', 'not_kr', 'missing', 'review', 'duplicate'])
def test_bridge_rejects_scope_or_readiness_changes(fault):
    old, main, groups = fixtures()
    if fault == 'reserved':
        groups[0]['allocation'] = 'evaluation_reserved'
    elif fault == 'not_kr':
        old[0]['domain'] = 'us_card'
    elif fault == 'missing':
        main.pop()
    elif fault == 'review':
        main[0]['status'] = 'needs_review'
    else:
        old[-1] = deepcopy(old[0])
    with pytest.raises(ValueError):
        bridge_documents(old, main, groups)
