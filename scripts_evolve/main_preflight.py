"""Offline full-cohort runtime preflight; no inference and no success-only subset.

Measure the original KR parser and the current US full-source windows against
all 3,000 frozen inputs. Source-group labels are provenance evidence, not a
completed issuer/product-family audit or permission to call a split held-out.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import importlib.util
import json
from pathlib import Path
import re
import shutil
import unicodedata
from urllib.parse import urlparse

from scripts_evolve.full_corpus_v2 import DOMAINS, ROOT, sha256, write_once
from scripts_evolve.us_tasks import source_windows


def read(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def check_roster(sources: list[dict], extractions: list[dict], per_domain: int = 1000) -> None:
    if Counter(r['domain'] for r in sources) != Counter({d: per_domain for d in DOMAINS}):
        raise ValueError('Fixed source domain counts differ from required cohort')
    source_ids = [r['doc_id'] for r in sources]
    extraction_ids = [r['doc_id'] for r in extractions]
    if len(set(source_ids)) != len(sources) or Counter(source_ids) != Counter(extraction_ids):
        raise ValueError('Missing, repeated or substituted extraction roster entry')
    by_id = {r['doc_id']: r for r in sources}
    for row in extractions:
        if any(row.get(k) != value for k, value in by_id[row['doc_id']].items()):
            raise ValueError('Frozen source identity changed')


def group_evidence(row: dict, metadata: dict) -> dict:
    """Resolve collection labels without guessing insurer IDs from numeric names."""
    evidence = []
    source = Path(row['source_path'])
    if row['domain'] == 'kr_insurance':
        for record in metadata.get('kr', []):
            if record['sha256'] != row['source_sha256']:
                continue
            match = re.match(r'^L\d+\s+(\S+)\s+L\d+', record.get('product_name', ''))
            name = record.get('insurer') or (match[1] if match else None)
            if name:
                evidence.append({'label': 'kr_insurer:' + name, 'basis': 'collection_manifest_listing',
                                 'source_url': record.get('source_url')})
        if not evidence:
            match = re.match(r'^([^_]+(?:생명|손해보험|라이프|화재))_', source.name)
            if match:
                evidence.append({'label': 'kr_insurer:' + match[1], 'basis': 'unverified_original_filename',
                                 'source_path': row['source_path']})
    elif row['domain'] == 'us_loan':
        for record in metadata.get('loan', []):
            if record['out'] != source.name:
                continue
            if record.get('sha256') and record['sha256'] != row['source_sha256']:
                raise ValueError('Loan metadata hash disagrees with frozen source')
            cik = str(int(record['cik']))
            url = urlparse(record['url'])
            if url.scheme != 'https' or url.hostname != 'www.sec.gov' or not url.path.startswith(f'/Archives/edgar/data/{cik}/'):
                raise ValueError('SEC registrant CIK disagrees with collection URL')
            evidence.append({'label': 'sec_registrant:' + cik, 'basis': 'collection_manifest_cik',
                             'source_url': record['url'], 'accession': record['accession'],
                             'collection_source_hash_present': bool(record.get('sha256'))})
    elif row['domain'] == 'us_card':
        for record in metadata.get('card', []):
            if record['sha256'] == row['source_sha256']:
                evidence.append({'label': 'card_collection_issuer:' + record['issuer'],
                                 'basis': 'cfpb_supplement_manifest', 'source_url': record['url']})
        if not evidence and len(source.parts) == 4 and source.parts[:2] == ('data', '2025_Q2'):
            evidence.append({'label': 'card_collection_issuer:' + source.parent.name,
                             'basis': 'cfpb_archive_directory_label', 'source_path': row['source_path']})
    for item in evidence:
        item['label'] = re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', item['label'])).strip().casefold()
    return {'labels': sorted({e['label'] for e in evidence}), 'evidence': evidence,
            'identity_verified': False, 'evaluation_split': None,
            'limitation': 'Collection/filename labels only; document identity, aliases, affiliate and product families need audit.'}


def checked_path(root: Path, relative: str, expected: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Input path outside workspace')
    if sha256(path.read_bytes()) != expected:
        raise ValueError('Frozen input hash changed: ' + relative)
    return path


def audit_document(row: dict, root: Path, parser, metadata: dict) -> dict:
    checked_path(root, row['source_path'], row['source_sha256'])
    result = {k: row[k] for k in ('doc_id', 'domain', 'source_path', 'source_sha256', 'pilot_membership')}
    result.update(extraction_status=row['status'], mechanical_issues=row.get('mechanical_issues', []),
                  grouping=group_evidence(row, metadata), main_model_status='not_started',
                  status='preprocessing_review', minimum_calls_if_current_ready_pipeline_completes=0,
                  conditional_card_validation_calls=0, nonempty_exact_text_group=None)
    if not row.get('text_path'):
        if row['status'] == 'success':
            raise ValueError('Successful extraction lacks text')
        return result
    path = checked_path(root, row['text_path'], row['text_sha256'])
    text = path.read_bytes().decode('utf-8')
    if len(text) != row['characters']:
        raise ValueError('Extracted character count changed')
    result.update(text_path=row['text_path'], text_sha256=row['text_sha256'], source_characters=len(text))
    if any(c.isalnum() for c in text):
        result['nonempty_exact_text_group'] = row['domain'] + ':' + row['text_sha256']
    if row['domain'] == 'kr_insurance':
        raw_text = text
        # This is the original CLI's read_text() behavior, not an invented repair.
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        result.update(parser_input_characters=len(text), parser_input_newline_normalized=text != raw_text,
                      parser_span_coordinate_system='Unicode codepoints in universal-newline parser input')
        clauses = parser(text, source_name=path.stem)
        spans, cursor = [], 0
        for clause in clauses:
            start = text.find(clause['raw_text'], cursor)
            if start < 0 or not clause['raw_text']:
                raise ValueError('Original parser output cannot be aligned to nonoverlapping source spans')
            cursor = start + len(clause['raw_text'])
            spans.append({'clause_id': clause['clause_id'], 'start': start, 'end': cursor})
        covered = sum(s['end'] - s['start'] for s in spans)
        result.update(parsed_clauses=len(clauses), parser_literal_spans=spans,
                      parser_at_1600_character_clauses=sum(len(c['raw_text']) == 1600 for c in clauses),
                      source_covered_characters=covered, source_coverage_fraction=covered / max(len(text), 1),
                      coverage_scope='Monotone literal-span coverage after original filtering/truncation; NOT keyword or legal recall.')
        if row['status'] == 'success':
            result.update(status='runtime_candidate' if clauses else 'parser_unsupported',
                          minimum_calls_if_current_ready_pipeline_completes=3 if clauses else 0)
    elif row['status'] == 'success':
        windows = source_windows(text)
        result.update(status='runtime_candidate', windows=len(windows), source_covered_characters=windows[-1]['end'],
                      source_coverage_fraction=1.0, coverage_scope='Full raw-text window coverage; NOT semantic extraction quality.',
                      minimum_calls_if_current_ready_pipeline_completes=len(windows) + int(row['domain'] == 'us_card'),
                      conditional_card_validation_calls=int(row['domain'] == 'us_card'))
    return result


def attach_leakage_components(rows: list[dict]) -> None:
    """Join known labels/exact nonblank texts, retaining every source row."""
    parents = list(range(len(rows)))

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    seen = {}
    for i, row in enumerate(rows):
        labels = row['grouping']['labels'] + ([row['nonempty_exact_text_group']] if row['nonempty_exact_text_group'] else [])
        for label in labels:
            if label in seen:
                parents[find(i)] = find(seen[label])
            else:
                seen[label] = i
    groups = defaultdict(list)
    for i in range(len(rows)):
        groups[find(i)].append(i)
    for members in groups.values():
        identity = sha256('\n'.join(sorted(rows[i]['doc_id'] for i in members)).encode())[:20]
        exposed = any(rows[i]['pilot_membership'] for i in members)
        for i in members:
            rows[i].update(leakage_component_id=identity, leakage_component_size=len(members),
                           leakage_component_has_pilot_member=exposed, evaluation_split=None)


def usage_inventory(root: Path) -> dict:
    paths = list((root / 'research/pilot_v1').glob('run_*/calls/*/record.json'))
    paths += list((root / 'research/harness_v3').glob('*/calls/*/record.json'))
    records = []
    for path in sorted(paths):
        record = read(path)
        usage = record.get('usage')
        known = isinstance(usage, dict) and all(type(usage.get(k)) is int and usage[k] >= 0
                                               for k in ('input_tokens', 'output_tokens'))
        records.append({'path': path.relative_to(root).as_posix(), 'sha256': sha256(path.read_bytes()),
                        'status': record['status'], 'usage_known': known,
                        'observed_tokens': usage['input_tokens'] + usage['output_tokens'] if known else 0})
    unknown = sum(not r['usage_known'] for r in records)
    return {'call_count': len(records), 'observed_tokens': sum(r['observed_tokens'] for r in records),
            'unknown_usage_calls': unknown, 'total_tokens_known': unknown == 0, 'records': records,
            'scope': 'Stored call records in pilot_v1/run_* and harness_v3/*; missing records are not discoverable here.'}


def summarize(rows: list[dict], usage: dict) -> dict:
    calls = sum(r['minimum_calls_if_current_ready_pipeline_completes'] for r in rows)
    by_domain = {}
    for domain in DOMAINS:
        selected = [r for r in rows if r['domain'] == domain]
        by_domain[domain] = {'inputs': len(selected), 'statuses': dict(Counter(r['status'] for r in selected)),
                             'minimum_calls': sum(r['minimum_calls_if_current_ready_pipeline_completes'] for r in selected),
                             'source_characters': sum(r.get('source_characters', 0) for r in selected),
                             'provisional_group_labels': len({g for r in selected for g in r['grouping']['labels']}),
                             'without_group_label': sum(not r['grouping']['labels'] for r in selected),
                             'pilot_members': sum(bool(r['pilot_membership']) for r in selected),
                             'in_components_with_pilot_member': sum(r.get('leakage_component_has_pilot_member', False) for r in selected)}
    return {'main_cohort_inputs': len(rows), 'domains': by_domain, 'main_model_documents_completed': 0,
            'main_model_execution_complete': False, 'held_out_evaluation_ready': False,
            'minimum_calls_for_current_ready_inputs_one_configuration': calls,
            'additional_conditional_card_validation_calls': sum(r['conditional_card_validation_calls'] for r in rows),
            'historical_envelope_calls': 1100, 'historical_envelope_tokens': 30000000,
            'historical_calls': usage['call_count'], 'historical_observed_tokens': usage['observed_tokens'],
            'historical_unknown_usage_calls': usage['unknown_usage_calls'],
            'fits_remaining_historical_call_envelope': calls <= max(0, 1100 - usage['call_count']),
            'new_model_calls': 0, 'cost_usd': None,
            'limitations': 'Offline preflight, not main model results. Call floor assumes successful completion of current '
                           'mechanically ready inputs once; excludes preprocessing recovery, retries, baselines, ablations, '
                           'refinement and repeated seeds. It is neither a token estimate nor a spending authorization. '
                           'Unresolved inputs remain in the cohort. Group labels/components are provisional, not a held-out split.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'research/main_3000_preflight_v2')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'research'):
        parser.error('Output must be under research')
    source_path = ROOT / 'research/dataset_3000_v2/source_manifest.json'
    extraction_path = ROOT / 'research/dataset_3000_v2/extraction_manifest.json'
    sources, extractions = read(source_path)['documents'], read(extraction_path)['documents']
    check_roster(sources, extractions)
    metadata_paths = {'kr': ROOT / 'ECC_harness_v3_txt/data/raw/contracts/_collection_manifest.jsonl',
                      'loan': ROOT / 'data/loan_data/us_loan_corpus/_manifest.jsonl',
                      'card': ROOT / 'data/us_card_supplement_cfpb_current/_manifest.json'}
    metadata = {k: [json.loads(line) for line in p.read_text(encoding='utf-8').splitlines() if line.strip()]
                for k, p in metadata_paths.items() if k != 'card'}
    metadata['card'] = read(metadata_paths['card'])['records']
    originals = [Path(__file__), ROOT / 'scripts_evolve/us_tasks.py', ROOT / 'scripts_evolve/native_schemas.py',
                 ROOT / 'scripts_evolve/full_corpus_v2.py', ROOT / 'ECC_harness_v3_txt/scripts/parse_txt.py']
    protocol = {'source_manifest_sha256': sha256(source_path.read_bytes()),
                'extraction_manifest_sha256': sha256(extraction_path.read_bytes()),
                'metadata_sha256': {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()) for p in metadata_paths.values()},
                'implementation_sha256': {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()) for p in originals},
                'target_total': 3000, 'target_per_domain': 1000, 'inference_enabled': False,
                'scope': 'Original KR parser and current US full-source windows, not the outer refinement experiment.'}
    write_once(output / 'protocol.json', protocol)
    for path in originals:
        copy = output / 'snapshot' / path.relative_to(ROOT)
        copy.parent.mkdir(parents=True, exist_ok=True)
        if copy.exists() and copy.read_bytes() != path.read_bytes():
            raise ValueError('Preflight snapshot changed')
        if not copy.exists():
            shutil.copyfile(path, copy)
    parser_path = output / 'snapshot/ECC_harness_v3_txt/scripts/parse_txt.py'
    spec = importlib.util.spec_from_file_location('original_txt_preflight', parser_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = []
    for document in extractions:
        rows.append(audit_document(document, ROOT, module.chunk_summary_doc, metadata))
        if len(rows) % 250 == 0:
            print(json.dumps({'preflight_inputs': len(rows), 'total': 3000, 'model_calls': 0}), flush=True)
    attach_leakage_components(rows)
    usage = usage_inventory(ROOT)
    summary = summarize(rows, usage)
    write_once(output / 'usage_snapshot.json', usage)
    write_once(output / 'manifest.json', {'protocol': protocol, 'summary': summary, 'documents': rows})
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
