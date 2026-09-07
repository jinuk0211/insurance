"""Actual three-role Stage-1 refinement, followed by a fixed 3,000-source E1 pass.

This implements only the compact preprocessing search space. Stage-2/3 model
grading and retrieval refinement are not simulated or reported as complete.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import re
import shutil

import jsonschema

from scripts.pilot.codex_client import CodexClient, MINI_MODEL, canonical, verify_codex_storage
from scripts_evolve.e1_cohort import ORIGINALS, load_originals
from scripts_evolve.full_corpus_v2 import DOMAINS, ROOT, sha256, write_once
from scripts_evolve.main_preflight import check_roster, checked_path, read, usage_inventory
from scripts_evolve.native_schemas import obj
from scripts_evolve.refinement_stage1 import BASELINE, CONFIG_SCHEMA, GATES, better, evaluate, line_evidence, validate_config

SHORT = {'type': 'string', 'minLength': 1, 'maxLength': 1500}
ITEMS = {'type': 'array', 'maxItems': 8, 'items': SHORT}
SCHEMAS = {
    'meta_review': obj({'failure_patterns': ITEMS, 'do_not_repeat': ITEMS}),
    'evolution': obj({'direction': SHORT, 'reason': SHORT}),
    'generation': obj({'candidates': {'type': 'array', 'minItems': 1, 'maxItems': 3,
                                    'items': obj({'rationale': SHORT, 'configuration': CONFIG_SCHEMA})}}),
}
SYSTEMS = {
    'meta_review': 'You are the Meta-review role in a preprocessing harness refinement experiment. Read the entire supplied '
                   'attempt history and identify repeated failures and do-not-repeat constraints. Do not invent attempts or results.',
    'evolution': 'You are the Evolution role. Use current configuration, measured development metrics, full attempt history and '
                 'Meta-review feedback to direct a distinct next search in the declared compact preprocessing space. No legal-accuracy claims.',
    'generation': 'You are the Generation role. Propose 1-3 concrete complete configuration rewrites using ONLY the supplied schema. '
                  'Use Meta-review constraints and Evolution direction. Exact-line and prefix rules are case-insensitive literal strings, '
                  'not regular expressions. Remove only defensible boilerplate, never substantive terms or numerical financial information. '
                  'A candidate is actually run on every fixed development input and must pass ALL immutable gates. Minimize total whitespace '
                  'units, then characters. Prefer small general edits. Do not target document IDs or invent corpus statistics. '
                  'If no supported improvement is apparent, return the current configuration with an honest explanation.',
}


def compact_metrics(metrics: dict) -> dict:
    return {k: v for k, v in metrics.items() if k != 'document_result_sha256'}


def refine_domain(domain: str, cases: list[dict], keywords: list[str], call_role,
                  directory: Path, max_iterations: int = 3) -> dict:
    if (not cases or any(c['allocation'] != 'development_exposed_or_linked' or c['domain'] != domain for c in cases)
            or len({c['doc_id'] for c in cases}) != len(cases)):
        raise ValueError('Refinement requires unique fixed development inputs from the selected domain')
    if not 1 <= max_iterations <= 3:
        raise ValueError('This Stage-1 protocol permits one to three iterations')
    current = deepcopy(BASELINE)
    baseline = evaluate(cases, current, keywords, directory / 'baseline')
    seen, history = {canonical(current)}, []
    evidence = line_evidence(cases)
    write_once(directory / 'development_line_evidence.json', {'lines': evidence})
    stop_reason = 'iteration_limit'
    for iteration in range(1, max_iterations + 1):
        folder = directory / f'iteration_{iteration:03d}'
        measured = evaluate(cases, current, keywords, folder / 'current')
        best_metrics, best_config, best_index = measured, current, None
        context = {'domain': domain, 'iteration': iteration, 'current_configuration': current,
                   'current_metrics': compact_metrics(measured), 'history': history,
                   'immutable_gates': GATES, 'objective': 'Minimize total whitespace units, then characters, subject to every per-document gate.',
                   'input_scope': 'All development-exposed/linked sources, including extraction-review rows; no reserved inputs.'}
        meta = call_role('meta_review', context, SCHEMAS['meta_review'])
        jsonschema.validate(meta, SCHEMAS['meta_review'])
        write_once(folder / 'meta_review.json', meta)
        direction = call_role('evolution', {**context, 'meta_review': meta}, SCHEMAS['evolution'])
        jsonschema.validate(direction, SCHEMAS['evolution'])
        write_once(folder / 'evolution_direction.json', direction)
        proposals = call_role('generation', {**context, 'meta_review': meta, 'evolution_direction': direction,
                                             'frequent_development_lines': evidence}, SCHEMAS['generation'])
        jsonschema.validate(proposals, SCHEMAS['generation'])
        write_once(folder / 'proposals.json', proposals)
        outcomes = []
        for index, proposal in enumerate(proposals['candidates']):
            config = proposal['configuration']
            outcome = {'candidate_index': index, **proposal, 'selected': False}
            try:
                validate_config(config)
            except ValueError as exc:
                outcome.update(status='invalid_configuration', error=str(exc))
                outcomes.append(outcome)
                continue
            identifier = canonical(config)
            if identifier in seen:
                outcome['status'] = 'duplicate_configuration'
            else:
                seen.add(identifier)
                candidate = evaluate(cases, config, keywords, folder / f'candidate_{index:02d}')
                outcome.update(status='evaluated', metrics=compact_metrics(candidate),
                               whitespace_unit_delta=candidate['output_whitespace_units'] - measured['output_whitespace_units'],
                               character_delta=candidate['output_characters'] - measured['output_characters'])
                if better(candidate, best_metrics):
                    best_metrics, best_config, best_index = candidate, config, index
            outcomes.append(outcome)
        if best_index is not None:
            outcomes[best_index]['selected'] = True
        history.append({'iteration': iteration, 'input_configuration': current, 'input_metrics': compact_metrics(measured),
                        'meta_review': meta, 'evolution_direction': direction, 'candidates': outcomes,
                        'retained_configuration': best_config, 'retained_metrics': compact_metrics(best_metrics)})
        write_once(folder / 'decision.json', history[-1])
        current = deepcopy(best_config)
        print({'stage1_domain': domain, 'iteration': iteration, 'candidates': len(outcomes),
               'selected_candidate': best_index, 'development_inputs': len(cases)}, flush=True)
        if best_index is None:
            stop_reason = 'no_strictly_improving_eligible_candidate'
            break
    result = {'domain': domain, 'development_inputs': len(cases), 'baseline_metrics': compact_metrics(baseline),
              'iterations_completed': len(history), 'stop_reason': stop_reason,
              'selected_configuration': current, 'selected_metrics': history[-1]['retained_metrics'], 'history': history,
              'scope': 'Executed constrained Stage-1 proxy refinement, not Stage-2/3 refinement, legal accuracy or evidence of ten-iteration convergence.'}
    write_once(directory / 'selected_configuration.json', current)
    write_once(directory / 'summary.json', result)
    return result


def load_cases(rows: list[dict], tasks: dict, root: Path) -> list[dict]:
    cases = []
    for row in rows:
        if not re.fullmatch(r'(kr_insurance|us_card|us_loan)-[a-f0-9]{20}', row['doc_id']):
            raise ValueError('Unsafe or unrecognized frozen source ID')
        checked_path(root, row['source_path'], row['source_sha256'])
        text = checked_path(root, row['text_path'], row['text_sha256']).read_bytes().decode('utf-8')
        if len(text) != row['characters']:
            raise ValueError('Frozen extraction length changed')
        cases.append({k: row[k] for k in ('doc_id', 'domain', 'source_sha256', 'text_sha256', 'allocation')})
        cases[-1].update(raw=text, baseline=tasks[row['domain']]['strategy_ours'](text), extraction_status=row['status'])
    return cases


class Roles:
    def __init__(self, client, root: Path, directory: Path):
        self.client, self.root, self.directory = client, root, directory

    def __call__(self, role: str, payload: dict, schema: dict) -> dict:
        usage = usage_inventory(self.root)
        if usage['call_count'] >= 1100 or usage['observed_tokens'] >= 30_000_000:
            raise ValueError('Historical call/observed-token envelope reached; no launch')
        label = f"stage1_{payload['domain']}_{payload['iteration']:03d}_{role}"
        record = self.client.call(label=label, model=MINI_MODEL, system=SYSTEMS[role],
                                  prompt=canonical(payload), max_tokens=4800, schema=schema)
        path = self.client.directory / record['request_id'] / 'record.json'
        verified = verify_codex_storage(path, MINI_MODEL)
        if record['output'] != verified['output']:
            raise ValueError('Role response differs from native evidence')
        write_once(self.directory / 'role_records' / (label + '.json'),
                   {'request_id': record['request_id'], 'record_path': path.relative_to(self.root).as_posix(),
                    'record_sha256': sha256(path.read_bytes()), 'output': verified['output']})
        return verified['output']


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--codex', type=Path, required=True)
    parser.add_argument('--max-iterations', type=int, choices=(1, 2, 3), default=3)
    parser.add_argument('--max-calls', type=int, default=27)
    parser.add_argument('--token-stop', type=int, default=750_000)
    args = parser.parse_args()
    output = args.run_dir.resolve()
    if output.parent != ROOT / 'research/harness_v3':
        parser.error('Run must be a direct child of research/harness_v3 for global accounting')
    if not 0 <= args.max_calls <= 27 or not 0 <= args.token_stop <= 750_000:
        parser.error('This development protocol is bounded to 27 calls and a 750,000 observed-token prelaunch stop')
    paths = [ROOT / 'research/dataset_3000_v2/source_manifest.json', ROOT / 'research/dataset_3000_v2/extraction_manifest.json',
             ROOT / 'research/main_3000_groups_v1/allocation_manifest.json']
    source, extraction, allocation = [read(p) for p in paths]
    check_roster(source['documents'], extraction['documents'])
    check_roster(source['documents'], allocation['documents'])
    by_id = {r['doc_id']: r for r in extraction['documents']}
    for row in allocation['documents']:
        if any(row[k] != value for k, value in by_id[row['doc_id']].items()):
            raise ValueError('Allocation/extraction identity changed')
    client = CodexClient(output / 'calls', args.codex, max_calls=args.max_calls,
                         token_stop_threshold=args.token_stop, model=MINI_MODEL)
    implementations = [ROOT / p for p in ('evolve.py', 'scripts_evolve/refinement_loop.py', 'scripts_evolve/refinement_stage1.py',
                        'scripts_evolve/e1_cohort.py', 'scripts_evolve/full_corpus_v2.py', 'scripts_evolve/main_preflight.py',
                        'scripts_evolve/us_tasks.py', 'scripts_evolve/native_schemas.py',
                        'scripts/pilot/codex_client.py', 'scripts/pilot/client.py', *ORIGINALS.values())]
    protocol = {'stage': 'preprocessing_only', 'cohort_inputs': 3000, 'per_domain': 1000,
                'input_sha256': {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()) for p in paths},
                'implementation_sha256': {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()) for p in implementations},
                'provenance': client.provenance(), 'max_iterations_per_domain': args.max_iterations,
                'max_calls': args.max_calls, 'observed_token_stop': args.token_stop, 'immutable_gates': GATES,
                'search_space': CONFIG_SCHEMA, 'roles': SYSTEMS, 'role_schemas': SCHEMAS,
                'selection': 'Same full development-exposed/linked inputs at every iteration; no reserved tuning; minimize total whitespace units then characters.',
                'stop': 'First iteration with no strictly improving eligible novel candidate, or the iteration/call/token limit. Never pad a trajectory.',
                'application': 'Configuration mutations execute original E1 filter or raw text plus typed literal line/whitespace operations. No original file overwritten.',
                'limitations': 'Proxy-constrained Stage-1 search, not legal information-preservation verification. Fixed 3,000-source E1 evaluation follows frozen selections. '
                               'Native TXT parser and downstream model pipelines are not changed by this Stage-1-only run. '
                               'Groups/languages are provisional; no verified held-out claim. No paid API fallback, retry, model substitution or credit redemption.'}
    write_once(output / 'protocol.json', protocol)
    for path in implementations:
        target = output / 'snapshot' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != path.read_bytes():
            raise ValueError('Refinement snapshot changed')
        if not target.exists():
            shutil.copyfile(path, target)
    before_path = output / 'historical_usage_before.json'
    if not before_path.exists():
        write_once(before_path, usage_inventory(ROOT))
    tasks = load_originals(output / 'snapshot')
    development = [r for r in allocation['documents'] if r['allocation'] == 'development_exposed_or_linked']
    write_once(output / 'development_manifest.json', {'documents': development, 'allocation_sha256': sha256(paths[2].read_bytes())})
    roles = Roles(client, ROOT, output)
    results = {}
    try:
        for domain in DOMAINS:
            rows = [r for r in development if r['domain'] == domain]
            cases = load_cases(rows, tasks, ROOT)
            results[domain] = refine_domain(domain, cases, tasks[domain]['keywords'], roles,
                                            output / 'development' / domain, args.max_iterations)
        # Freeze all selected configurations before ANY reserved-corpus evaluation.
        write_once(output / 'selected_configurations.json', {d: results[d]['selected_configuration'] for d in DOMAINS})
        main_e1 = {}
        for domain in DOMAINS:
            rows = [r for r in allocation['documents'] if r['domain'] == domain]
            cases = load_cases(rows, tasks, ROOT)
            main_e1[domain] = evaluate(cases, results[domain]['selected_configuration'], tasks[domain]['keywords'],
                                       output / 'main_e1' / domain)
            print({'frozen_stage1_main_domain': domain, 'inputs': len(cases), 'new_evaluation_model_calls': 0}, flush=True)
        summary = {'status': 'stage1_complete', 'development': results, 'main_e1': main_e1,
                   'stage1_main_inputs': sum(m['input_documents'] for m in main_e1.values()),
                   'usage': client.usage_summary(), 'main_model_experiment_complete': False,
                   'stage2_stage3_refinement_complete': False, 'cost_usd': None}
        write_once(output / 'summary.json', summary)
    except Exception as exc:
        write_once(output / 'interruption.json', {'status': 'failed_or_stopped', 'error': f'{type(exc).__name__}: {exc}',
                                                 'completed_domains': list(results), 'usage': client.usage_summary(),
                                                 'main_model_experiment_complete': False})
        raise
    print({'status': summary['status'], 'stage1_main_inputs': summary['stage1_main_inputs'], 'usage': summary['usage']}, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
