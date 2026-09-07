"""Prepare all 3,000 main-experiment inputs, separate from the small pilot.

Never mutate originals. Keep per-document failures and complete page extraction
records. A canonical manifest is written only when all three targets are met.
Extraction checks are mechanical, not a certification of visual/semantic fidelity.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re

from pypdf import PdfReader
from pypdf.errors import PyPdfError

ROOT = Path(__file__).resolve().parents[1]
DOMAINS = ('kr_insurance', 'us_card', 'us_loan')


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)


def check_text(text: str) -> list[str]:
    issues = []
    if len(text.strip()) < 1000:
        issues.append('under_1000_characters')
    if '\x00' in text:
        issues.append('nul_character')
    if '\ufffd' in text:
        issues.append('replacement_character')
    private = sum('\ue000' <= c <= '\uf8ff' for c in text)
    if private / max(len(text), 1) > .001:
        issues.append('private_use_character_density')
    return issues


def source_group(record: dict, loan_manifest: dict) -> str:
    path = Path(record['path'])
    domain = record['domain']
    if domain == 'us_loan':
        cik = loan_manifest.get(path.name, {}).get('cik')
        if cik:
            return f'us_loan:cik:{str(cik).lstrip("0") or "0"}'
        issuer = re.split(r'_20\d{2}-', path.name)[0]
    elif domain == 'kr_insurance':
        issuer = path.name.split('_', 1)[0]
    elif 'us_card_supplement_cfpb_current' in path.parts:
        issuer = 'AMERICAN_EXPRESS_NATIONAL_BANK'
    else:
        parts = path.parts
        index = parts.index('2025_Q2') if '2025_Q2' in parts else -1
        issuer = parts[index + 1] if index >= 0 and index + 2 < len(parts) else path.name.split('_', 1)[0]
    return f'{domain}:{re.sub(r"[^a-z0-9가-힣]+", "_", issuer.lower()).strip("_")}'


def extract_record(record: dict, output: str, fingerprint: dict) -> dict:
    domain, expected = record['domain'], record['sha256']
    document_id = f'{domain}-{expected[:20]}'
    folder = Path(output) / 'documents' / domain
    metadata_path = folder / f'{expected}.json'
    text_path = folder / f'{expected}.txt'
    if metadata_path.exists():
        if sha256((ROOT / record['path']).read_bytes()) != expected:
            raise ValueError('source hash changed before cached extraction reuse')
        previous = json.loads(metadata_path.read_text(encoding='utf-8'))
        if previous['extractor'] != fingerprint or previous['source_sha256'] != expected:
            raise ValueError('extraction cache identity changed')
        if previous['status'] == 'success' and sha256(text_path.read_bytes()) != previous['text_sha256']:
            raise ValueError('cached extraction text changed')
        return previous
    result = {'doc_id': document_id, 'domain': domain, 'source_path': record['path'],
              'source_sha256': expected, 'source_group': record['source_group'],
              'extractor': fingerprint, 'status': 'failure'}
    try:
        source = (ROOT / record['path']).resolve()
        if not source.is_relative_to(ROOT) or source.suffix.lower() not in ('.txt', '.pdf'):
            raise ValueError('unsupported source path')
        if sha256(source.read_bytes()) != expected:
            raise ValueError('source hash changed since inventory')
        if source.suffix.lower() == '.pdf':
            reader = PdfReader(source)
            pages = [page.extract_text() or '' for page in reader.pages]
            result['page_characters'] = [len(page) for page in pages]
            result['pages'] = len(pages)
            # Preserve extracted text and explicit page boundaries; no slicing.
            text = '\n\f\n'.join(pages)
        else:
            text = source.read_text(encoding='utf-8')
            result['pages'] = None
        issues = check_text(text)
        result.update(characters=len(text), mechanical_issues=issues)
        if not issues:
            folder.mkdir(parents=True, exist_ok=True)
            encoded = text.encode('utf-8')
            with text_path.open('xb') as handle:
                handle.write(encoded)
            result.update(status='success', text_sha256=sha256(encoded),
                          text_path=str(text_path.relative_to(ROOT)).replace('\\', '/'))
    except (OSError, ValueError, TypeError, KeyError, NotImplementedError, PyPdfError) as exc:
        result.update(error_type=type(exc).__name__, error=str(exc))
    write_new(metadata_path, result)
    return result


def select_documents(candidates: list[dict], per_domain: int) -> dict[str, list[dict]]:
    result = {domain: [] for domain in DOMAINS}
    for domain in DOMAINS:
        source_hashes, text_hashes = set(), set()
        for row in sorted((r for r in candidates if r['domain'] == domain), key=lambda r: r['source_sha256']):
            if row['status'] != 'success':
                continue
            if row['source_sha256'] in source_hashes or row['text_sha256'] in text_hashes:
                continue
            source_hashes.add(row['source_sha256'])
            text_hashes.add(row['text_sha256'])
            if len(result[domain]) < per_domain:
                result[domain].append(row)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'research/dataset_3000_v1')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'research'):
        parser.error('output must stay under the research directory')
    if not 1 <= args.workers <= 8:
        parser.error('workers must be in 1..8')
    inventory = json.loads(args.inventory.read_text(encoding='utf-8'))
    loan_manifest = {r['out']: r for line in (ROOT / 'data/loan_data/us_loan_corpus/_manifest.jsonl').read_text(encoding='utf-8').splitlines()
                     if line.strip() for r in [json.loads(line)]}
    fingerprint = {'engine': 'pypdf', 'version': importlib.metadata.version('pypdf'),
                   'script_sha256': sha256(Path(__file__).read_bytes()),
                   'text_policy': 'all pages, no truncation, explicit form-feed page separators'}
    protocol = {'target_per_domain': 1000, 'target_total': 3000, 'extractor': fingerprint,
                'inventory_sha256': sha256(args.inventory.read_bytes()),
                'split_status': 'not assigned; must freeze group-aware splits before evaluation',
                'pilot_policy': 'pilot inputs and development exposure must be flagged, not relabeled as held-out'}
    protocol_path = output / 'protocol.json'
    if protocol_path.exists():
        if json.loads(protocol_path.read_text(encoding='utf-8')) != protocol:
            raise ValueError('preparation protocol changed; preserve existing extraction version')
    else:
        write_new(protocol_path, protocol)
    records = []
    for domain in inventory['domains']:
        for row in domain['records']:
            if row['duplicate_of'] or row['mechanical_issues']:
                continue
            record = {'domain': domain['domain'], **row}
            record['source_group'] = source_group(record, loan_manifest)
            records.append(record)
    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(extract_record, record, str(output), fingerprint): record for record in records}
        for future in as_completed(futures):
            results.append(future.result())
            if len(results) % 100 == 0 or len(results) == len(records):
                print(json.dumps({'processed': len(results), 'total': len(records),
                                  'statuses': dict(Counter(r['status'] for r in results))}), flush=True)
    selected = select_documents(results, 1000)
    counts = {domain: len(rows) for domain, rows in selected.items()}
    complete = all(n == 1000 for n in counts.values())
    summary = {'preparation_complete': complete, 'counts': counts,
               'statuses_by_domain': {domain: dict(Counter(r['status'] for r in results if r['domain'] == domain)) for domain in DOMAINS},
               'total_selected': sum(counts.values()),
               'limitations': 'Mechanical extraction checks and exact text deduplication only; visual/semantic review remains required.'}
    write_new(output / 'preparation_summary.json', summary)
    write_new(output / ('manifest.json' if complete else 'manifest.partial.json'),
              {'schema_version': 1, 'protocol': protocol, 'summary': summary,
               'documents': [row for domain in DOMAINS for row in selected[domain]]})
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0 if complete else 2


if __name__ == '__main__':
    raise SystemExit(main())
