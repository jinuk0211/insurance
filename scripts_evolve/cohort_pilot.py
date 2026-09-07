"""Prepare an exact main-input bridge for the four existing KR pilot originals.

This does not run inference or replace the full 3,000-document main cohort.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts_evolve.full_corpus_v2 import ROOT, sha256, write_once
from scripts_evolve.main_preflight import checked_path, read


def bridge_documents(previous: list[dict], cohort: list[dict], allocation: list[dict]) -> list[dict]:
    if len(previous) != 4 or len({r['source_sha256'] for r in previous}) != 4:
        raise ValueError('Exactly four distinct existing KR development sources required')
    by_source = {r['source_sha256']: r for r in cohort if r['domain'] == 'kr_insurance'}
    groups = {r['doc_id']: r for r in allocation}
    documents = []
    for old in previous:
        if old['domain'] != 'kr_insurance' or old['split'] != 'dev':
            raise ValueError('Non-development insurance source in prior selection')
        current = by_source.get(old['source_sha256'])
        if current is None or current['status'] != 'success':
            raise ValueError('Main-cohort source missing or unresolved extraction')
        group = groups.get(current['doc_id'])
        if group is None or group['source_sha256'] != current['source_sha256'] or group['allocation'] != 'development_exposed_or_linked':
            raise ValueError('Development source is not in its verified allocation record')
        documents.append({**current, 'split': 'dev', 'historical_pilot': {
            'doc_id': old['doc_id'], 'text_sha256': old['text_sha256'],
            'text_version_changed': old['text_sha256'] != current['text_sha256']}})
    return documents


def main() -> None:
    paths = {'previous_selection': ROOT / 'research/harness_v3/kr_range_transport_02/selection.json',
             'main_extraction': ROOT / 'research/dataset_3000_v2/extraction_manifest.json',
             'allocation': ROOT / 'research/main_3000_groups_v1/allocation_manifest.json'}
    values = {name: read(path) for name, path in paths.items()}
    documents = bridge_documents(*(values[key]['documents'] for key in paths))
    for row in documents:
        checked_path(ROOT, row['source_path'], row['source_sha256'])
        checked_path(ROOT, row['text_path'], row['text_sha256'])
    result = {'documents': documents, 'source_evidence_sha256': {
        path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()) for path in paths.values()},
        'preparation_script_sha256': sha256(Path(__file__).read_bytes()),
        'scope': 'Same four previously used insurance PDFs, now using exact frozen main-cohort extraction text; not the full main experiment.',
        'main_cohort_inputs': 3000, 'main_cohort_per_domain': 1000, 'model_calls_by_preparation': 0}
    path = ROOT / 'research/harness_v3/kr_main_input_pilot_03/input_manifest.json'
    write_once(path, result)
    print(json.dumps({'path': path.relative_to(ROOT).as_posix(), 'documents': len(documents),
                      'changed_text_versions': sum(r['historical_pilot']['text_version_changed'] for r in documents)}))


if __name__ == '__main__':
    main()
