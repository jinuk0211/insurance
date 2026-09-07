"""Resume one fixed 3,000-source original-task baseline, not grader refinement.

The batch size is a scheduling bound, never a replacement cohort. Input failures,
partial outputs and unstarted rows remain. No model fallback or implicit retry.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from itertools import zip_longest
import json
import os
from pathlib import Path
import shutil
from typing import Iterator

from scripts.pilot.client import ModelFailure, write_json
from scripts.pilot.codex_client import CodexClient, MINI_MODEL, canonical, inference_request, request_id
from scripts_evolve.full_corpus_v2 import DOMAINS, ROOT, sha256, write_once
from scripts_evolve.loan_reference import INPUTS, INPUT_SHA256
from scripts_evolve.main_preflight import check_roster, checked_path, read, usage_inventory
from scripts_evolve.native_runtime import NativeHarness, PROFILE
from scripts_evolve.us_runtime import USRuntime

DEVELOPMENT = 'development_exposed_or_linked'
RESERVED = 'evaluation_reserved'
CALL_CAP, TOKEN_STOP = 1100, 30_000_000
OUTPUT = ROOT / 'research/harness_v3/main_3000_baseline_01'
RECONCILIATION = 'research/main_3000_prelaunch/pending_reconciliation.json'
PARENTS = {**{INPUTS[k]: v for k, v in INPUT_SHA256.items()},
    RECONCILIATION: '352ca741025dbcc511dd4ccb6ff4f21749ba7ccf29c4dbb2b5dd50a2f197d0f5',
    'research/main_3000_preflight_v2/manifest.json':
        '4b602d2c98073baf6750a23e5ac6af77596242b092aee0495ac9d4a1bc800e24',
    'research/loan_reference_1000_v1/candidate_pool.json':
        '4c27ceac3ecea1023b8ac8f296ab1cc9909198723a30b7d7ecd3dfe3ad074b61'}
REFERENCE_POLICY = ('Extraction-success development-linked loan sources only; exclude query source and '
                    'its provisional component. Original tags, text and Ours BM25/MMR unchanged. '
                    'Analogous clauses, not precedents or relevance gold. Reserved is not verified held-out.')


def ordered_roster(documents: list[dict], preflight: list[dict], per_domain: int = 1000) -> list[dict]:
    """Order before inference by exposure, then domain round-robin and doc_id."""
    check_roster(documents, documents, per_domain)
    expected_ids = Counter(r['doc_id'] for r in documents)
    if Counter(r['doc_id'] for r in preflight) != expected_ids:
        raise ValueError('Missing or duplicate preflight roster member')
    by_id = {r['doc_id']: r for r in preflight}
    augmented = []
    for row in documents:
        prior = by_id[row['doc_id']]
        fields = ('domain', 'source_path', 'source_sha256', 'text_path', 'text_sha256')
        if any(prior.get(k) != row.get(k) for k in fields) or prior['extraction_status'] != row['status']:
            raise ValueError('Preflight source/text identity differs')
        if row['allocation'] not in (DEVELOPMENT, RESERVED) or not row['component_id']:
            raise ValueError('Unknown source allocation/component')
        if prior['status'] not in ('runtime_candidate', 'preprocessing_review', 'parser_unsupported'):
            raise ValueError('Unknown preflight status')
        maximum = prior['minimum_calls_if_current_ready_pipeline_completes'] + prior['conditional_card_validation_calls']
        if type(maximum) is not int or maximum < int(prior['status'] == 'runtime_candidate'):
            raise ValueError('Invalid preflight call bound')
        augmented.append({**row, 'preflight_status': prior['status'], 'maximum_calls': maximum})
    result = []
    for allocation in (DEVELOPMENT, RESERVED):
        queues = [sorted((r for r in augmented if r['domain'] == d and r['allocation'] == allocation),
                         key=lambda r: r['doc_id']) for d in DOMAINS]
        result.extend(row for group in zip_longest(*queues) for row in group if row is not None)
    return result


def admit_loan_pool(pool: list[dict], documents: list[dict]) -> list[dict]:
    """Admit only existing development references without changing their tags."""
    loans = {r['doc_id']: r for r in documents if r['domain'] == 'us_loan'}
    if any(r['doc'] not in loans for r in pool) or len({r['chunk_id'] for r in pool}) != len(pool):
        raise ValueError('Unknown or duplicate loan reference')
    return [r for r in pool if loans[r['doc']]['allocation'] == DEVELOPMENT
            and loans[r['doc']]['status'] == 'success']


def query_loan_pool(pool: list[dict], documents: list[dict], query: str) -> list[dict]:
    """Apply query and provisional source-group exclusion, even in development."""
    groups = {r['doc_id']: r['component_id'] for r in documents if r['domain'] == 'us_loan'}
    return [r for r in pool if r['doc'] != query and groups[r['doc']] != groups[query]]


class GroupScopedUSRuntime(USRuntime):
    """Preserve original runtime; add the parent protocol's reference restriction."""

    def __init__(self, directory: Path, client, loan_pool: list[dict], documents: list[dict], root: Path = ROOT):
        self.reference_documents = documents
        super().__init__(directory, client, loan_pool, root=root)

    def run_loan(self, work: Path, trace: dict, drafts: list[dict]) -> bool:
        original_pool = self.loan_pool
        scoped = query_loan_pool(original_pool, self.reference_documents, trace['identity']['doc_id'])
        write_json(work / 'reference_selection.json', {'policy': REFERENCE_POLICY,
            'query_doc_id': trace['identity']['doc_id'], 'chunk_ids': [r['chunk_id'] for r in scoped],
            'pool_sha256': sha256(canonical(scoped).encode())})
        self.loan_pool = scoped
        try:
            return super().run_loan(work, trace, drafts)
        finally:
            self.loan_pool = original_pool


class EnvelopeClient:
    """One native client plus the unchanged cumulative operational envelope."""

    def __init__(self, client: CodexClient, root: Path, history: dict):
        self.native, self.root, self.history = client, root, history
        self.directory, self.model = client.directory, client.model

    def provenance(self) -> dict:
        return self.native.provenance()

    def usage_summary(self) -> dict:
        return self.native.usage_summary()

    def guard(self, reserve: int = 1, *, cached: bool = False) -> dict:
        """No new calls after cap, altered history, or incomplete native evidence."""
        if any(p.is_dir() and not (p / 'record.json').is_file() for p in self.directory.glob('*')):
            raise ModelFailure('Orphaned native request requires reconciliation')
        usage = usage_inventory(self.root)
        prefix = self.directory.relative_to(self.root).as_posix() + '/'
        history = [r for r in usage['records'] if not r['path'].startswith(prefix)]
        if history != self.history['records']:
            raise ModelFailure('Global history changed; reconcile before further inference')
        local = self.usage_summary()
        if local['incomplete_calls'] or local['unknown_usage_calls']:
            raise ModelFailure('Native accounting requires reconciliation')
        if not cached and (usage['call_count'] + reserve > CALL_CAP or usage['observed_tokens'] >= TOKEN_STOP):
            raise ModelFailure('Cumulative call/token envelope reached before launch')
        return usage

    def call(self, label: str, model: str, system: str, prompt: str,
             max_tokens: int = 2400, schema: dict | None = None) -> dict:
        request = inference_request(model, system, prompt, max_tokens, schema, self.provenance())
        cached = (self.directory / request_id(request) / 'record.json').exists()
        self.guard(cached=cached)
        # Native client checks schema, model, exact cached artifacts and orphan requests.
        return self.native.call(label=label, model=model, system=system, prompt=prompt,
                                max_tokens=max_tokens, schema=schema)


@contextmanager
def run_lock(path: Path) -> Iterator[None]:
    """Exclusive owned lock. A crash leaves evidence for explicit reconciliation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    token = f'{os.getpid()}:{os.urandom(16).hex()}'
    with path.open('x', encoding='utf-8') as handle:
        handle.write(token)
    try:
        yield
    finally:
        if path.read_text(encoding='utf-8') == token:
            path.unlink()


def dispatch(row: dict, runtime, root: Path) -> dict:
    """Check both selected original and raw extraction before native dispatch/cache."""
    checked_path(root, row['source_path'], row['source_sha256'])
    text = checked_path(root, row['text_path'], row['text_sha256'])
    if row['domain'] == 'kr_insurance':
        return runtime.run_document(text, row['doc_id'], PROFILE)
    return runtime.run_document(row)


def run_batch(rows: list[dict], runtimes: dict, client: EnvelopeClient, output: Path,
              batch_documents: int, root: Path = ROOT) -> dict:
    """Reconcile every row, dispatch a bounded next batch, checkpoint after each result."""
    if type(batch_documents) is not int or batch_documents < 0:
        raise ValueError('Batch document bound must be a nonnegative integer')
    protocol_hash = sha256((output / 'protocol.json').read_bytes())
    roster_hash = sha256(canonical(rows).encode())
    path = output / 'progress.json'
    prior = read(path) if path.exists() else None
    if prior and (prior['protocol_sha256'] != protocol_hash or prior['roster_sha256'] != roster_hash
                  or [r['doc_id'] for r in prior['documents']] != [r['doc_id'] for r in rows]):
        raise ValueError('Prior checkpoint protocol/roster differs')
    old = {r['doc_id']: r for r in prior['documents']} if prior else {}
    states, stop = [], 'batch_document_limit'

    def checkpoint(reason: str) -> dict:
        result = {'protocol_sha256': protocol_hash, 'roster_sha256': roster_hash,
            'main_cohort_documents': len(rows), 'documents': states,
            'status_counts': dict(Counter(r['status'] for r in states)), 'stop_reason': reason,
            'usage': client.usage_summary(), 'main_experiment_complete': False,
            'scope': 'One fixed original-task baseline; no grader selection, legal accuracy or full-study completion.'}
        pending = path.with_suffix('.pending.json')
        write_json(pending, result)
        os.replace(pending, path)
        return result

    for row in rows:
        runtime = runtimes[row['domain']]
        native = runtime.directory / 'documents' / row['doc_id'] / 'result.json'
        previous = old.get(row['doc_id'], {})
        if previous.get('native_result_sha256') and (not native.exists()
                or sha256(native.read_bytes()) != previous['native_result_sha256']):
            raise ValueError('Native result differs from prior checkpoint')
        state = {k: row[k] for k in ('doc_id', 'domain', 'allocation', 'component_id', 'preflight_status')}
        state['status'] = 'not_started' if row['preflight_status'] == 'runtime_candidate' else 'input_blocked'
        if native.exists():
            if state['status'] == 'input_blocked':
                raise ValueError('Unexpected execution of a blocked source')
            result = dispatch(row, runtime, root)
            state.update(status=result['status'], native_result_path=native.relative_to(root).as_posix(),
                         native_result_sha256=sha256(native.read_bytes()))
            if result['status'] != 'success':
                stop = 'native_result_requires_reconciliation'
        elif native.parent.exists() or previous.get('status') == 'interrupted_needs_reconciliation':
            state['status'] = 'interrupted_needs_reconciliation'
            stop = 'interrupted_document_requires_reconciliation'
        states.append(state)
    checkpoint(stop)
    if stop != 'batch_document_limit':
        return checkpoint(stop)
    launched = 0
    for row, state in zip(rows, states, strict=True):
        if state['status'] != 'not_started' or launched >= batch_documents:
            continue
        try:
            client.guard(row['maximum_calls'])
        except ModelFailure as exc:
            stop = str(exc)
            break
        print(json.dumps({'dispatch': row['doc_id'], 'allocation': row['allocation'],
                          'maximum_document_calls': row['maximum_calls']}, ensure_ascii=False), flush=True)
        runtime = runtimes[row['domain']]
        result = dispatch(row, runtime, root)
        native = runtime.directory / 'documents' / row['doc_id'] / 'result.json'
        state.update(status=result['status'], native_result_path=native.relative_to(root).as_posix(),
                     native_result_sha256=sha256(native.read_bytes()))
        launched += 1
        if result['status'] != 'success':
            stop = 'native_result_requires_reconciliation'
        checkpoint(stop)
        if stop != 'batch_document_limit':
            break
    return checkpoint(stop)


def prepare(output: Path, executable: Path, root: Path = ROOT) -> tuple[list[dict], dict, EnvelopeClient]:
    """Freeze all source identities, ordering, reference policy and code before inference."""
    values = {name: read(checked_path(root, name, expected)) for name, expected in PARENTS.items()}
    reconciliation = values[RECONCILIATION]
    for relative, expected in reconciliation['existing_stop_evidence'].items():
        checked_path(root, relative, expected)
    for relative, expected in reconciliation['stopped_pending_records'].items():
        checked_path(root, relative, expected)
    sources, extractions, allocation = (values[INPUTS[k]]['documents'] for k in ('sources', 'extractions', 'allocation'))
    check_roster(sources, extractions)
    check_roster(extractions, allocation)
    rows = ordered_roster(allocation, values['research/main_3000_preflight_v2/manifest.json']['documents'])
    for row in rows:
        checked_path(root, row['source_path'], row['source_sha256'])
        if row.get('text_path'):
            checked_path(root, row['text_path'], row['text_sha256'])
    pool = admit_loan_pool(values['research/loan_reference_1000_v1/candidate_pool.json']['chunks'], rows)
    history_path = output / 'prior_usage.json'
    if history_path.exists():
        history = read(history_path)
    else:
        if output.exists() and any(output.iterdir()):
            raise ValueError('Unfrozen main run requires reconciliation')
        history = usage_inventory(root)
        stopped = reconciliation['stopped_pending_records']
        if any(r['status'] == 'pending' and stopped.get(r['path']) != r['sha256']
               for r in history['records']):
            raise ValueError('Pending historical call requires reconciliation')
        write_once(history_path, history)
    native_client = CodexClient(output / 'calls', executable, max_calls=CALL_CAP,
                                token_stop_threshold=TOKEN_STOP, model=MINI_MODEL)
    client = EnvelopeClient(native_client, root, history)
    kr = NativeHarness(root / 'ECC_harness_v3_txt', output / 'kr', client)
    us = GroupScopedUSRuntime(output / 'us', client, pool, rows, root=root)
    implementations = ['scripts_evolve/main_execution.py', 'scripts_evolve/main_preflight.py',
                       'scripts_evolve/loan_reference.py', 'scripts_evolve/full_corpus_v2.py']
    code_hashes = {p: sha256((root / p).read_bytes()) for p in implementations}
    protocol = {'version': 1, 'parents': PARENTS, 'implementation_sha256': code_hashes,
        'roster_sha256': sha256(canonical(rows).encode()), 'target_total': 3000, 'target_per_domain': 1000,
        'ordering': 'development linked first, then reserved; domain round-robin; doc_id ascending within domain',
        'reference_policy': REFERENCE_POLICY, 'reference_pool_sha256': sha256(canonical(pool).encode()),
        'reference_sources': len({r['doc'] for r in pool}), 'reference_chunks': len(pool),
        'prior_usage_sha256': sha256(history_path.read_bytes()), 'cumulative_call_cap': CALL_CAP,
        'historical_pending_reconciliation': reconciliation,
        'known_token_prelaunch_stop': TOKEN_STOP, 'unknown_historical_calls': history['unknown_usage_calls'],
        'budget_scope': 'Stored pilot_v1/run_* and harness_v3/* calls; unknown usage is not zero. '
                        'Single calls can cross the observed-token prelaunch stop. No paid API/fallback/reset.',
        'kr_protocol': kr.protocol, 'us_protocol': us.protocol, 'automatic_refinement': False,
        'held_out_verified': False, 'legal_validity_verified': False,
        'scope': 'Fixed original-task baseline execution on all 3000 identities, not the full comparative study.'}
    write_once(output / 'protocol.json', protocol)
    write_once(output / 'roster.json', {'documents': rows})
    for relative, expected in code_hashes.items():
        destination = output / 'snapshot' / relative
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / relative, destination)
        if sha256(destination.read_bytes()) != expected:
            raise ValueError('Main runner snapshot differs')
    return rows, {'kr_insurance': kr, 'us_card': us, 'us_loan': us}, client


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex', type=Path, required=True)
    parser.add_argument('--batch-documents', type=int, default=0,
                        help='New documents this invocation; zero freezes/reconciles without model calls')
    args = parser.parse_args()
    if args.batch_documents < 0:
        parser.error('Batch document bound must be nonnegative')
    with run_lock(ROOT / 'research/harness_v3/main_execution.lock'):
        rows, runtimes, client = prepare(OUTPUT, args.codex)
        result = run_batch(rows, runtimes, client, OUTPUT, args.batch_documents)
        print(json.dumps({k: v for k, v in result.items() if k != 'documents'}, ensure_ascii=False), flush=True)
    return int(result['stop_reason'] != 'batch_document_limit')


if __name__ == '__main__':
    raise SystemExit(main())
