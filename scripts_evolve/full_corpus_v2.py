"""Freeze the 3,000-source cohort and independently extract every full document.

V1 evidence is untouched. Failure, short-text and duplicate-text records remain
in this cohort; success-only subsets must never replace its denominator.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
DOMAINS = ('kr_insurance', 'us_card', 'us_loan')


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_once(path: Path, value: dict) -> None:
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8')) != value:
            raise ValueError(f'Existing evidence differs: {path}')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)


def build_cohort(inventory: dict, pilots: list[dict], domains: tuple = DOMAINS,
                 per_domain: int = 1000) -> list[dict]:
    memberships = defaultdict(list)
    for pilot in pilots:
        for row in pilot['documents']:
            hashes = {row.get(key) for key in ('source_sha256', 'original_pdf_sha256', 'text_sha256')}
            for digest in hashes - {None}:
                memberships[digest].append({'manifest': pilot['manifest'], 'doc_id': row['doc_id'],
                                            'historical_split': row.get('split')})
    cohort = []
    for domain in domains:
        matches = [r for r in inventory['domains'] if r['domain'] == domain]
        if len(matches) != 1:
            raise ValueError(f'Missing or repeated domain: {domain}')
        rows = [r for r in matches[0]['records'] if not r['duplicate_of'] and not r['mechanical_issues']]
        if len(rows) != per_domain:
            raise ValueError(f'{domain}: expected {per_domain} sources, found {len(rows)}')
        if len({r['sha256'] for r in rows}) != len(rows):
            raise ValueError(f'{domain}: duplicate source hash')
        for row in sorted(rows, key=lambda r: r['sha256']):
            members = memberships.get(row['sha256'], [])
            cohort.append({'doc_id': f"{domain}-{row['sha256'][:20]}", 'domain': domain,
                           'source_path': row['path'], 'source_sha256': row['sha256'],
                           'source_bytes': row['bytes'], 'pilot_membership': members,
                           # Membership alone does not prove a model saw the text.
                           # Conservatively withhold all old pilot members from a new test.
                           'held_out_eligible': False if members else None,
                           'evaluation_split': None, 'verified_source_group': None})
    return cohort


def quality_flags(text: str) -> list[str]:
    flags = []
    if len(text.strip()) < 1000:
        flags.append('under_1000_characters')
    if any(ord(c) < 32 and c not in '\t\r\n\f' for c in text) or '\x7f' in text:
        flags.append('unexpected_control_characters')
    if '\ufffd' in text:
        flags.append('replacement_character')
    if sum('\ue000' <= c <= '\uf8ff' for c in text) / max(len(text), 1) > .001:
        flags.append('private_use_character_density')
    return flags


def extract(row: dict, root_string: str, output_string: str, fingerprint: dict) -> dict:
    root, output = Path(root_string).resolve(), Path(output_string).resolve()
    source = (root / row['source_path']).resolve()
    if not source.is_relative_to(root) or source.suffix.lower() not in ('.pdf', '.txt'):
        raise ValueError('Unsupported source path')
    if sha256(source.read_bytes()) != row['source_sha256']:
        raise ValueError('source hash changed')
    folder = output / 'documents' / row['domain']
    metadata = folder / f"{row['source_sha256']}.json"
    text_path = metadata.with_suffix('.txt')
    if metadata.exists():
        old = json.loads(metadata.read_text(encoding='utf-8'))
        if old['extractor'] != fingerprint or any(old[k] != row[k] for k in row):
            raise ValueError('Cached identity changed')
        if old.get('text_sha256') and sha256(text_path.read_bytes()) != old['text_sha256']:
            raise ValueError('Cached text hash changed')
        return old
    result = {**row, 'extractor': fingerprint, 'status': 'failure'}
    try:
        if source.suffix.lower() == '.pdf':
            with pymupdf.open(source) as document:
                pages = [page.get_text() for page in document]
            text = '\n\f\n'.join(pages)
            result.update(pages=len(pages), page_characters=[len(p) for p in pages])
        else:
            text = source.read_text(encoding='utf-8')
            result['pages'] = None
        flags = quality_flags(text)
        # Keep even flagged text verbatim for diagnosis. No character stripping,
        # guessed glyph replacement, OCR, summarization or length truncation.
        encoded = text.encode('utf-8')
        folder.mkdir(parents=True, exist_ok=True)
        if text_path.exists():
            if text_path.read_bytes() != encoded:
                raise ValueError('Existing extracted text differs')
        else:
            with text_path.open('xb') as handle:
                handle.write(encoded)
        result.update(status='needs_review' if flags else 'success', mechanical_issues=flags,
                      characters=len(text), text_sha256=sha256(encoded),
                      text_path=text_path.relative_to(root).as_posix())
    except (OSError, ValueError, RuntimeError, pymupdf.FileDataError) as exc:
        result.update(error_type=type(exc).__name__, error=str(exc))
    write_once(metadata, result)
    return result


def summarize(cohort: list[dict], results: list[dict]) -> dict:
    if {r['doc_id'] for r in cohort} != {r['doc_id'] for r in results} or len(cohort) != len(results):
        raise ValueError('Missing or repeated extraction records')
    text_groups = defaultdict(list)
    for row in results:
        if row.get('text_sha256') and row.get('characters', 1) > 0:
            text_groups[(row['domain'], row['text_sha256'])].append(row['doc_id'])
    duplicates = sorted(sorted(ids) for ids in text_groups.values() if len(ids) > 1)
    return {'total_inputs': len(cohort),
            'domain_counts': dict(Counter(r['domain'] for r in cohort)),
            'status_counts': {d: dict(Counter(r['status'] for r in results if r['domain'] == d))
                              for d in sorted({r['domain'] for r in cohort})},
            'exact_text_duplicate_groups': duplicates,
            'all_inputs_mechanically_ready': all(r['status'] == 'success' for r in results) and not duplicates,
            'main_model_execution_complete': False,
            'limitations': 'Mechanical checks only, not semantic/visual validation or 3,000 independent contracts. '
                           'All selected inputs remain in the denominator; no evaluation split is frozen yet.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'research/dataset_3000_v2')
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'research') or not 1 <= args.workers <= 8:
        parser.error('Output must be under research, with 1..8 workers')
    raw_inventory = args.inventory.read_bytes()
    pilots, evidence = [], []
    for name in ('data', 'data_v2', 'data_v3'):
        path = ROOT / 'research/pilot_v1' / name / 'manifest.json'
        raw = path.read_bytes()
        pilots.append({'manifest': path.relative_to(ROOT).as_posix(), **json.loads(raw)})
        evidence.append({'path': path.relative_to(ROOT).as_posix(), 'sha256': sha256(raw)})
    cohort = build_cohort(json.loads(raw_inventory), pilots)
    fingerprint = {'engine': 'pymupdf', 'version': pymupdf.VersionBind,
                   'script_sha256': sha256(Path(__file__).read_bytes()),
                   'text_policy': 'all pages, raw text, form-feed boundaries, no OCR or truncation'}
    protocol = {'target_total': 3000, 'target_per_domain': 1000, 'extractor': fingerprint,
                'inventory_sha256': sha256(raw_inventory), 'pilot_manifest_evidence': evidence,
                'pilot_policy': 'Conservatively exclude every historical pilot member from a new held-out test; '
                                'unmatched source hashes are not proof of no development exposure.',
                'denominator_policy': 'Keep every selected source, including extraction failures and duplicates.',
                'source_group_policy': 'Unverified; resolve issuer/product-family groups before splitting.'}
    write_once(output / 'source_manifest.json', {'schema_version': 2, 'protocol': protocol, 'documents': cohort})
    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(extract, row, str(ROOT), str(output), fingerprint) for row in cohort]
        for future in as_completed(futures):
            results.append(future.result())
            if len(results) % 100 == 0:
                print(json.dumps({'processed': len(results), 'total': len(cohort),
                                  'statuses': dict(Counter(r['status'] for r in results))}), flush=True)
    results.sort(key=lambda r: r['doc_id'])
    summary = summarize(cohort, results)
    write_once(output / 'extraction_manifest.json', {'schema_version': 2, 'protocol': protocol,
                                                   'summary': summary, 'documents': results})
    write_once(output / 'preparation_summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0 if summary['all_inputs_mechanically_ready'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
