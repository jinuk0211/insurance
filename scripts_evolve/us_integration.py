"""Run the original US task adaptations on existing development inputs only.

This validates execution before the full 3,000-document study; never claims
accuracy or substitutes this small development selection for the main cohort.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.pilot.client import write_json
from scripts.pilot.codex_client import CodexClient, MINI_MODEL
from scripts_evolve.us_runtime import ROOT, USRuntime, digest, read
from scripts_evolve.us_tasks import load_original_tasks


def select_development(cohort: dict, pilot: dict) -> list[dict]:
    by_source = {row['source_sha256']: row for row in cohort['documents']}
    selected = []
    for row in pilot['documents']:
        if row['domain'] not in ('us_card', 'us_loan') or row['split'] != 'dev':
            continue
        current = by_source.get(row['source_sha256'])
        if current is None or current['domain'] != row['domain']:
            raise ValueError('Existing development input missing from fixed 3,000-source cohort')
        selected.append(current)
    if {row['domain'] for row in selected} != {'us_card', 'us_loan'}:
        raise ValueError('Both existing US development domains required')
    if len({row['doc_id'] for row in selected}) != len(selected):
        raise ValueError('Repeated development input')
    return sorted(selected, key=lambda row: (row['domain'], row['doc_id']))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--codex', type=Path, required=True)
    parser.add_argument('--max-calls', type=int, default=24)
    parser.add_argument('--token-stop', type=int, default=750000)
    parser.add_argument('--reuse-calls', type=Path, action='append', default=[])
    parser.add_argument('--domain', choices=('all', 'us_card', 'us_loan'), default='all')
    args = parser.parse_args()
    directory = args.run_dir.resolve()
    if not directory.is_relative_to(ROOT / 'research/harness_v3'):
        parser.error('Run directory must be under research/harness_v3')
    inventory = ROOT / 'research/dataset_3000_v2/extraction_manifest.json'
    pilot = ROOT / 'research/pilot_v1/data_v3/manifest.json'
    documents = select_development(read(inventory), read(pilot))
    if args.domain != 'all':
        documents = [row for row in documents if row['domain'] == args.domain]
    history = []
    paths = list((ROOT / 'research/pilot_v1').glob('run_*/calls/*/record.json'))
    paths += [p for p in (ROOT / 'research/harness_v3').glob('*/calls/*/record.json')
              if not p.resolve().is_relative_to(directory)]
    for path in sorted(paths):
        record = read(path)
        history.append({'path': path.relative_to(ROOT).as_posix(), 'sha256': digest(path),
                        'status': record['status'], 'usage_known': 'usage' in record,
                        'observed_tokens': sum(record.get('usage', {}).get(k, 0) for k in ('input_tokens', 'output_tokens'))})
    if len(history) + args.max_calls > 1100 or sum(r['observed_tokens'] for r in history) + args.token_stop > 30000000:
        parser.error('Development integration would exceed the existing cumulative operational envelope')
    texts = {}
    for row in documents:
        if row['domain'] == 'us_loan' and row['status'] == 'success':
            path = ROOT / row['text_path']
            if digest(path) != row['text_sha256']:
                raise ValueError('Loan pool source hash mismatch')
            texts[row['doc_id']] = path.read_text(encoding='utf-8')
    original = load_original_tasks(ROOT)
    pool = original['loan']['build_candidate_pool'](texts, set())
    client = CodexClient(directory / 'calls', args.codex, max_calls=args.max_calls,
                         token_stop_threshold=args.token_stop, model=MINI_MODEL)
    runtime = USRuntime(directory, client, pool, reuse_calls=tuple(args.reuse_calls))
    selection = {'cohort_manifest_sha256': digest(inventory), 'pilot_manifest_sha256': digest(pilot),
                 'documents': documents, 'loan_pool_policy': 'Existing development loans only; self excluded per query',
                 'history': history, 'max_calls': args.max_calls, 'token_stop': args.token_stop,
                 'billing_kind': 'chatgpt_subscription', 'cost_usd': None,
                 'scope': 'Original US task runtime integration only; not the 3,000-input main experiment'}
    if (directory / 'selection.json').exists() and read(directory / 'selection.json') != selection:
        raise ValueError('Selection or prior usage changed; reconcile before inference')
    write_json(directory / 'selection.json', selection)
    results = []
    for document in documents:
        result = runtime.run_document(document)
        results.append({'doc_id': document['doc_id'], 'domain': document['domain'], 'status': result['status'],
                        'result_path': (directory / 'documents' / document['doc_id'] / 'result.json').relative_to(ROOT).as_posix()})
        write_json(directory / 'summary.json', {'results': results, 'usage': client.usage_summary(),
                                              'scope': selection['scope'], 'main_experiment_complete': False})
        if client.usage_summary()['incomplete_calls']:
            return 1
    return int(any(row['status'] != 'success' for row in results))


if __name__ == '__main__':
    raise SystemExit(main())
