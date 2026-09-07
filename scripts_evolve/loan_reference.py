"""Freeze and audit original loan retrieval chunks on the fixed 1,000 sources.

Offline preparation only: no model, new relevance labels, runtime admission or
retrieval evaluation. Original full-paragraph tags and truncated text stay intact.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from pathlib import Path
import re
import shutil

from scripts_evolve.full_corpus_v2 import DOMAINS, ROOT, sha256, write_once
from scripts_evolve.main_preflight import check_roster, checked_path, read

ORIGINAL_PATH = 'eval_US_loan/eval_loan.py'
ORIGINAL_SHA256 = '2fed1d8a3249e19b1cbafdfb2ae87686c17692f509f02c3e844cfc89139c9b73'
INPUTS = {
    'sources': 'research/dataset_3000_v2/source_manifest.json',
    'extractions': 'research/dataset_3000_v2/extraction_manifest.json',
    'allocation': 'research/main_3000_groups_v1/allocation_manifest.json',
}
INPUT_SHA256 = {
    'sources': 'a69c745bdc26014decff7155cc59b8d71ccf2ebbc26ff3bf2b98b176a70bf956',
    'extractions': '902b32e3c29f2807277b3ce46d49c5fc90e99bf66f2b33da37be3949fb73475f',
    'allocation': 'f1942df8980c2d6d65dc5ec765aac3a1d85e2de1821f69d5dd218a80e2f66655',
}
IMPLEMENTATIONS = ['scripts_evolve/loan_reference.py', 'scripts_evolve/full_corpus_v2.py',
                   'scripts_evolve/main_preflight.py', ORIGINAL_PATH]
MIN_PARAGRAPH_CHARS, MAX_PARAGRAPHS, MAX_VISIBLE_CHARS = 200, 40, 1500


def load_original(root: Path) -> dict:
    """Execute only hash-pinned taxonomy/pool declarations, never API setup."""
    path = checked_path(root, ORIGINAL_PATH, ORIGINAL_SHA256)
    names = ('LOAN_TAXONOMY', 'build_candidate_pool')
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    nodes = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in names)
             or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets))]
    namespace = {'re': re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return {name: namespace[name] for name in names}


def load_inputs(root: Path) -> list[dict]:
    """Validate all three domains and inherited extraction fields before selection."""
    values = {key: read(checked_path(root, path, INPUT_SHA256[key])) for key, path in INPUTS.items()}
    check_roster(values['sources']['documents'], values['extractions']['documents'])
    check_roster(values['extractions']['documents'], values['allocation']['documents'])
    return sorted((r for r in values['allocation']['documents'] if r['domain'] == 'us_loan'),
                  key=lambda r: r['doc_id'])


def paragraph_spans(text: str) -> list[tuple[int, int]]:
    """Locate original stripped, length-eligible paragraphs without newline conversion."""
    spans, offset = [], 0
    for index, part in enumerate(re.split(r'(\n{2,})', text)):
        stripped = part.strip()
        if index % 2 == 0 and len(stripped) >= MIN_PARAGRAPH_CHARS:
            start = offset + len(part) - len(part.lstrip())
            spans.append((start, start + len(stripped)))
        offset += len(part)
    return spans


def keyword_tags(text: str, taxonomy: dict) -> list[str]:
    """Literal original inventory matches, not semantic relevance or legal findings."""
    low = text.lower()
    return [key for key, info in taxonomy.items() if any(kw.lower() in low for kw in info['keywords'])]


def audit_document(row: dict, root: Path, original: dict) -> tuple[dict, list[dict], list[dict]]:
    """Keep a report for every source and reconcile every original chunk to raw text."""
    if row['domain'] != 'us_loan':
        raise ValueError('Loan source required')
    checked_path(root, row['source_path'], row['source_sha256'])
    available = bool(row.get('text_path'))
    if not available and row['status'] == 'success':
        raise ValueError('Successful loan missing text')
    text = checked_path(root, row['text_path'], row['text_sha256']).read_bytes().decode('utf-8') if available else ''
    if available and len(text) != row['characters']:
        raise ValueError('Frozen character count differs from raw UTF-8 text')
    spans = paragraph_spans(text)
    pool = original['build_candidate_pool']({row['doc_id']: text}, set())
    expected, audits = [], []
    for index, (start, end) in enumerate(spans[:MAX_PARAGRAPHS]):
        tags = keyword_tags(text[start:end], original['LOAN_TAXONOMY'])
        if not tags:
            continue
        visible_end = min(end, start + MAX_VISIBLE_CHARS)
        visible = text[start:visible_end]
        identity = f"{row['doc_id']}#p{index}"
        expected.append({'doc': row['doc_id'], 'chunk_id': identity, 'text': visible, 'tags': tags})
        visible_tags = keyword_tags(visible, original['LOAN_TAXONOMY'])
        audits.append({'doc_id': row['doc_id'], 'chunk_id': identity, 'paragraph_index': index,
                       'paragraph_start': start, 'paragraph_end': end,
                       'source_start': start, 'source_end': visible_end, 'text_sha256': sha256(visible.encode()),
                       'original_tags': tags, 'visible_tags': visible_tags,
                       'tags_missing_from_visible_text': [t for t in tags if t not in visible_tags]})
    if pool != expected:
        raise ValueError('Original pool differs from independently reconstructed source spans/tags')
    report = {**row, 'text_available': available, 'reference_quality_eligible': row['status'] == 'success',
              'eligible_paragraphs': len(spans), 'considered_paragraphs': min(len(spans), MAX_PARAGRAPHS),
              'paragraphs_beyond_original_cap': max(0, len(spans) - MAX_PARAGRAPHS), 'chunks': len(pool),
              'chunks_with_missing_visible_tags': sum(bool(a['tags_missing_from_visible_text']) for a in audits)}
    return report, pool, audits


def summarize(documents: list[dict], audits: list[dict]) -> dict:
    """Report failure-inclusive document and chunk denominators separately."""
    if sum(d['chunks'] for d in documents) != len(audits):
        raise ValueError('Document/chunk audit counts differ')
    missing = [a for a in audits if a['tags_missing_from_visible_text']]
    return {
        'main_cohort_documents': len(DOMAINS) * 1000, 'loan_documents': len(documents),
        'extraction_statuses': dict(Counter(d['status'] for d in documents)),
        'documents_without_chunks': sum(d['chunks'] == 0 for d in documents),
        'documents_with_missing_visible_tags': len({a['doc_id'] for a in missing}),
        'chunks': len(audits), 'chunks_with_missing_visible_tags': len(missing),
        'chunks_with_no_visible_tag': sum(not a['visible_tags'] for a in audits),
        'missing_visible_tag_assignments': dict(Counter(t for a in missing for t in a['tags_missing_from_visible_text'])),
        'original_tag_assignments': dict(Counter(t for a in audits for t in a['original_tags'])),
        'visible_tag_assignments': dict(Counter(t for a in audits for t in a['visible_tags'])),
        'truncated_chunks': sum(a['source_end'] < a['paragraph_end'] for a in audits),
        'paragraphs_beyond_original_cap': sum(d['paragraphs_beyond_original_cap'] for d in documents),
        'development_documents': sum(d['allocation'] == 'development_exposed_or_linked' for d in documents),
        'evaluation_reserved_documents': sum(d['allocation'] == 'evaluation_reserved' for d in documents),
        'model_calls': 0, 'runtime_pool_admitted': False, 'relevance_gold_verified': False,
        'main_experiment_complete': False,
    }


def freeze(root: Path, output: Path) -> dict:
    """Write a new immutable preparation archive; leave runtime and prior runs untouched."""
    if output.resolve().parent != root.resolve() / 'research' or output.exists():
        raise ValueError('Use a new direct child of research')
    rows, original = load_inputs(root), load_original(root)
    protocol = {
        'version': 1, 'input_sha256': {p: INPUT_SHA256[k] for k, p in INPUTS.items()},
        'implementation_sha256': {p: sha256((root / p).read_bytes()) for p in IMPLEMENTATIONS},
        'main_cohort_documents': 3000, 'target_loan_documents': 1000, 'model_calls': 0,
        'algorithm': 'Exact original build_candidate_pool defaults, with empty sample exclusion only for archiving all potential chunks.',
        'raw_text_policy': 'UTF-8 bytes decoded without newline normalization; extraction flags retained; no OCR replacement.',
        'limits': {'minimum_stripped_paragraph_characters': 200, 'first_eligible_paragraphs': 40, 'visible_characters': 1500},
        'scope': 'Analogous commercial-loan clauses, NOT court precedents, verified adverse findings or human relevance labels.',
        'runtime_pool_admitted': False,
        'limitations': ['This all-source archive is not an evaluation pool. Query/self/group and quality exclusions require a frozen downstream protocol.',
                       'Original tags are computed before truncation; visible keyword diagnostics do not repair them or constitute legal relevance.',
                       'Development/exposure strata are preserved. No evaluation-reserved content is sent to a model or used to tune retrieval here.',
                       'No ranking, score, MRR, recall, main inference, budget expansion or paid API call is produced.'],
    }
    write_once(output / 'protocol.json', protocol)
    for relative in IMPLEMENTATIONS:
        destination = output / 'snapshot' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, destination)
    documents, pool, audits = [], [], []
    for row in rows:
        report, chunks, checks = audit_document(row, root, original)
        documents.append(report)
        pool.extend(chunks)
        audits.extend(checks)
        if len(documents) % 100 == 0:
            print({'loan_documents': len(documents), 'chunks': len(pool), 'model_calls': 0}, flush=True)
    write_once(output / 'candidate_pool.json', {'chunks': pool})
    write_once(output / 'chunk_audit.json', {'chunks': audits})
    result = {'protocol': protocol, 'documents': documents, 'summary': summarize(documents, audits),
              'artifact_sha256': {name: sha256((output / name).read_bytes())
                                 for name in ('protocol.json', 'candidate_pool.json', 'chunk_audit.json')}}
    write_once(output / 'manifest.json', result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'research/loan_reference_1000_v1')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != ROOT / 'research' or output.exists():
        parser.error('Use a new direct child of research; never overwrite existing evidence')
    print(freeze(ROOT, output)['summary'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
