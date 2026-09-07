"""Offline original-versus-prepared retrieval and frozen reference-context diagnostic."""
from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
from statistics import mean
from time import perf_counter_ns

from scripts_evolve.full_corpus_v2 import ROOT, sha256, write_once
from scripts_evolve.loan_reference import INPUTS, INPUT_SHA256, load_inputs, keyword_tags
from scripts_evolve.loan_reference_refinement import DEVELOPMENT, METHODS
from scripts_evolve.loan_retrieval import PreparedLoanRetriever, load_retrieval
from scripts_evolve.main_execution import admit_loan_pool, query_loan_pool
from scripts_evolve.main_preflight import checked_path, read

REFINEMENT = 'research/loan_reference_refinement_01'
PARENTS = {
    f'{REFINEMENT}/original_pool.json': '45828c089188d10cc2208fb53ebca6ac674de062b267ae2a1ece6740cb738bf4',
    f'{REFINEMENT}/full_windows_pool.json': '669cf9671cc24e6278c73de693c86f4aa1c8a76fd3bbaed54e4633941f37314b',
    f'{REFINEMENT}/compact_cover_pool.json': 'e47eefefe2acd80b4fe17868e996014491b14e516bbf37517bc8a030d25287d3',
    f'{REFINEMENT}/manifest.json': '3a5754b2a7f88f75463cc860840801d4348b929c40c24f5f90b8ef8e5efde5e0',
    f'{REFINEMENT}/selection.json': '6e98e35da0f954cc5cc806f706949fdfc2ccb67667cab133fbfc450cea7b02c0',
    'research/harness_v3/main_3000_baseline_01/protocol.json':
        '6abf2703e3fc1bb09f614d1ec69cf3c43971f653ecaace146c42d58a76ef0bb5',
    'research/harness_v3/main_3000_baseline_01/progress.json':
        'c56cc40f5ece2592dbd38b4335e2face1f17c3b19152d88b527e4f2870cf80e8',
}
REPETITIONS = 3


def digest(value: object) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode())


def timed_pair(fresh: Callable, prepared: Callable, alternate: bool) -> tuple[dict, list[dict] | None]:
    """Keep both failures of equivalence and individual timings, without result retries."""
    callbacks = {'fresh': fresh, 'prepared': prepared}
    values, timing, errors = {}, {}, {}
    for name in (('prepared', 'fresh') if alternate else ('fresh', 'prepared')):
        start = perf_counter_ns()
        try:
            values[name] = callbacks[name]()
        except Exception as error:
            values[name] = None
            errors[name] = {'type': type(error).__name__, 'message': str(error)[:300]}
        timing[name + '_ns'] = perf_counter_ns() - start
    match = not errors and values['fresh'] == values['prepared']
    return {**timing, 'errors': errors, 'exact_match': match, 'fresh_sha256': digest(values['fresh']),
            'prepared_sha256': digest(values['prepared']),
            'prepared_mismatch_result': None if match else values['prepared']}, values['fresh']


def percentile(values: list[int], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


def timing_summary(observed: list[dict], first: list[dict], cold_ns: int) -> dict:
    """Include one-pass cold cost; no-query and mismatching runs cannot pass."""
    failures = sum(not r['exact_match'] for r in observed)
    unstable = sum(not r['repeat_stable'] for r in observed)
    violations = sum(r['exclusion_violations'] for r in observed)
    error_arms = sum(len(r.get('errors', {})) for r in observed)
    fresh_first = sum(r['fresh_ns'] for r in first)
    prepared_first = cold_ns + sum(r['prepared_ns'] for r in first)
    successful = [r for r in observed if not r.get('errors')]
    result = {'paired_retrievals': len(observed), 'successful_paired_retrievals': len(successful),
              'execution_error_arms': error_arms, 'exact_mismatches': failures,
              'unstable_original_repetitions': unstable, 'exclusion_violations': violations,
              'cold_preparation_ns': cold_ns, 'fresh_first_pass_ns': fresh_first,
              'prepared_first_pass_with_cold_ns': prepared_first,
              'prepared_identical_pool_gate_passed': bool(observed) and not (failures or unstable or violations)
                  and prepared_first < fresh_first}
    for name in ('fresh', 'prepared'):
        values = [r[name + '_ns'] for r in successful]
        result.update({name + '_sum_ns': sum(values), name + '_p50_ns': percentile(values, .5),
                       name + '_p95_ns': percentile(values, .95)})
    return result


def context_metrics(query: dict, rows: list[dict], taxonomy: dict) -> dict:
    """Literal visible keywords and context size are not legal relevance labels."""
    return {'returned_chunks': len(rows),
            'unique_parents': len({r.get('parent_chunk_id', r['chunk_id']) for r in rows}),
            'returned_characters': sum(len(r['text']) for r in rows),
            'literal_query_category_keyword_chunks':
                sum(query['taxonomy'] in keyword_tags(r['text'], taxonomy) for r in rows)}


def visible_payload(rows: list[dict]) -> list[dict]:
    """Ignore window-ID renaming and scores when comparing ordered source context."""
    return [{k: r.get(k) for k in ('doc', 'source_start', 'source_end', 'text')} for r in rows]


def prepare_inputs(root: Path, output: Path) -> tuple[list, list, dict, dict]:
    """Freeze every identity, query, reference policy and implementation before timing."""
    if output.resolve().parent != root.resolve() / 'research' or output.exists():
        raise ValueError('Use a new direct child of research; do not overwrite or restart evidence')
    if os.environ.get('PYTHONHASHSEED') != '0':
        raise ValueError('Launch Python with PYTHONHASHSEED=0')
    documents = load_inputs(root)
    values = {name: read(checked_path(root, name, expected)) for name, expected in PARENTS.items()}
    manifest = values[f'{REFINEMENT}/manifest.json']
    if len(documents) != 1000 or sum(r['allocation'] == DEVELOPMENT for r in documents) != 22:
        raise ValueError('Original loan/development counts differ')
    by_id = {r['doc_id']: r for r in manifest['documents']}
    if set(by_id) != {r['doc_id'] for r in documents} or any(
            any(by_id[r['doc_id']].get(k) != v for k, v in r.items()) for r in documents):
        raise ValueError('Structural comparison substituted a source')
    original = load_retrieval(root)
    queries = []
    for row in documents:
        checked_path(root, row['source_path'], row['source_sha256'])
        text = checked_path(root, row['text_path'], row['text_sha256']).read_bytes().decode('utf-8')
        queries.extend(original['extract_queries']({row['doc_id']: text}))
    pools = {m: admit_loan_pool(values[f'{REFINEMENT}/{m}_pool.json']['chunks'], documents) for m in METHODS}
    implementations = ['scripts_evolve/loan_retrieval.py', 'scripts_evolve/loan_retrieval_benchmark.py',
        'scripts_evolve/loan_reference.py', 'scripts_evolve/loan_reference_refinement.py',
        'scripts_evolve/main_execution.py', 'scripts_evolve/main_preflight.py',
        'scripts_evolve/full_corpus_v2.py', 'eval_US_loan/eval_loan.py']
    import rank_bm25
    protocol = {'main_cohort_documents': 3000, 'loan_documents': 1000, 'development_documents': 22,
        'methods': list(METHODS), 'repetitions': REPETITIONS, 'query_limit_per_document': 3,
        'queries_sha256': digest(queries), 'query_count': len(queries), 'model_calls': 0,
        'parents_sha256': {**PARENTS, **{INPUTS[k]: v for k, v in INPUT_SHA256.items()}},
        'code_sha256': {p: sha256((root / p).read_bytes()) for p in implementations},
        'plan_sha256': sha256((root / 'research/loan_retrieval_refinement_plan.md').read_bytes()),
        'environment': {'python': platform.python_version(), 'platform': platform.platform(),
            'python_hash_seed': os.environ['PYTHONHASHSEED'],
            'rank_bm25_version': importlib.metadata.version('rank-bm25'),
            'rank_bm25_source_sha256': sha256(Path(rank_bm25.__file__).read_bytes())},
        'admitted_chunks': {m: len(p) for m, p in pools.items()},
        'reference_policy': 'Successful development references only; exclude query and provisional component.',
        'scope': 'Keyword-generated query diagnostic; NOT human relevance, neural baseline or full model study.',
        'runtime_default_changed': False, 'semantic_quality_verified': False}
    write_once(output / 'protocol.json', protocol)
    write_once(output / 'queries.json', {'queries': queries})
    for path in implementations:
        destination = output / 'snapshot' / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / path, destination)
    return documents, queries, pools, protocol


def benchmark(root: Path, output: Path) -> dict:
    """Evaluate all available original diagnostic queries without dropping no-query sources."""
    documents, queries, pools, protocol = prepare_inputs(root, output)
    original = load_retrieval(root)
    by_id = {r['doc_id']: r for r in documents}
    caches, preparations = {m: {} for m in METHODS}, {m: [] for m in METHODS}
    records = []
    for index, query in enumerate(queries):
        record = {'query': query, 'allocation': by_id[query['doc']]['allocation'], 'methods': {}}
        scopes = {m: query_loan_pool(pools[m], documents, query['doc']) for m in METHODS}
        for repetition in range(REPETITIONS):
            offset = (index + repetition) % len(METHODS)
            for method in METHODS[offset:] + METHODS[:offset]:
                scoped = scopes[method]
                key = tuple(r['chunk_id'] for r in scoped)
                if key not in caches[method]:
                    start = perf_counter_ns()
                    preparation_error = None
                    try:
                        engine = PreparedLoanRetriever(scoped, root)
                    except Exception as error:
                        engine = None
                        preparation_error = {'type': type(error).__name__, 'message': str(error)[:300]}
                    cold_ns = perf_counter_ns() - start
                    caches[method][key] = engine
                    preparations[method].append({'pool_id': digest(key), 'chunk_ids': list(key),
                        'cold_ns': cold_ns, 'backend': engine.backend if engine else None,
                        'error': preparation_error})
                engine = caches[method][key]
                def prepared_call():
                    if engine is None:
                        raise RuntimeError('Prepared pool construction failed; see preparations.json')
                    return engine.retrieve(query, top_k=5)
                observation, result = timed_pair(
                    lambda: original['retrieve']('Ours', query, scoped, top_k=5),
                    prepared_call, bool((index + repetition) % 2))
                result = result or []
                if repetition == 0:
                    record['methods'][method] = {'result': result, 'pool_id': digest(key),
                        'context': context_metrics(query, result, original['LOAN_TAXONOMY']), 'observations': []}
                observation['repetition'] = repetition
                previous = record['methods'][method]['observations']
                initial_failed = previous and 'fresh' in previous[0]['errors']
                observation['repeat_stable'] = not initial_failed and 'fresh' not in observation['errors'] \
                    and result == record['methods'][method]['result']
                query_group = by_id[query['doc']]['component_id']
                checked_results = result + (observation['prepared_mismatch_result'] or [])
                observation['exclusion_violations'] = sum(
                    r['doc'] == query['doc'] or by_id[r['doc']]['component_id'] == query_group
                    or by_id[r['doc']]['allocation'] != DEVELOPMENT for r in checked_results)
                record['methods'][method]['observations'].append(observation)
        records.append(record)
        if (index + 1) % 100 == 0:
            print(json.dumps({'completed_queries': index + 1, 'total_queries': len(queries)}), flush=True)
    timing, context = {}, {}
    for method in METHODS:
        for preparation in preparations[method]:
            engine = caches[method][tuple(preparation['chunk_ids'])]
            preparation['scoring_calls'] = engine.scoring_calls if engine else 0
            preparation['fallback_scoring_calls'] = engine.fallback_scoring_calls if engine else 0
        observed = [o for r in records for o in r['methods'][method]['observations']]
        first = [o for o in observed if o['repetition'] == 0]
        timing[method] = timing_summary(observed, first, sum(r['cold_ns'] for r in preparations[method]))
    for allocation in ('all', DEVELOPMENT, 'evaluation_reserved'):
        selected = [r for r in records if allocation == 'all' or r['allocation'] == allocation]
        context[allocation] = {'queries': len(selected), 'methods': {}}
        for method in METHODS:
            values = [r['methods'][method]['context'] for r in selected
                      if 'fresh' not in r['methods'][method]['observations'][0]['errors']]
            context[allocation]['methods'][method] = {
                k: mean(r[k] for r in values) if values else None for k in (
                    'returned_chunks', 'unique_parents', 'returned_characters',
                    'literal_query_category_keyword_chunks')}
            context[allocation]['methods'][method]['defined_first_pass_queries'] = len(values)
            context[allocation]['methods'][method]['failed_fresh_first_pass_queries'] = len(selected) - len(values)
    changes = {}
    for left, right in (('original', 'full_windows'), ('original', 'compact_cover'), ('full_windows', 'compact_cover')):
        shared, changed, context_changed, unavailable = [], 0, 0, 0
        for row in records:
            if any('fresh' in row['methods'][m]['observations'][0]['errors'] for m in (left, right)):
                unavailable += 1
                continue
            a, b = row['methods'][left]['result'], row['methods'][right]['result']
            changed += a != b
            context_changed += visible_payload(a) != visible_payload(b)
            shared.append(len({r.get('parent_chunk_id', r['chunk_id']) for r in a}
                              & {r.get('parent_chunk_id', r['chunk_id']) for r in b}))
        changes[left + '_vs_' + right] = {'queries': len(records), 'changed_ordered_results': changed,
                                         'changed_ordered_source_context': context_changed,
                                         'unavailable_first_pass_queries': unavailable,
                                         'mean_shared_parent_ids': mean(shared) if shared else None}
    counts = Counter(q['doc'] for q in queries)
    for name, expected in protocol.get('parents_sha256', {}).items():
        checked_path(root, name, expected)
    summary = {'protocol': protocol, 'all_queries': len(queries), 'timing': timing,
               'context_means_not_relevance': context, 'cross_structure_changes_not_quality': changes,
               'documents': [{**r, 'queries': counts[r['doc_id']]} for r in documents],
               'model_calls': 0, 'runtime_default_changed': False, 'semantic_quality_verified': False,
               'main_experiment_complete': False}
    write_once(output / 'preparations.json', preparations)
    write_once(output / 'query_results.json', {'queries': records})
    write_once(output / 'summary.json', summary)
    print(json.dumps({'all_queries': len(queries), 'timing': timing, 'model_calls': 0}), flush=True)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'research/loan_retrieval_refinement_01')
    args = parser.parse_args()
    benchmark(ROOT, args.output.resolve())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
