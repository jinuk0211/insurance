"""Offline structural reference refinement with development-only selection.

Compare original truncation, complete keyword-bearing windows, and a compact
tag-cover subset. Literal tag consistency is NOT legal or retrieval accuracy.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import shutil

from scripts_evolve.full_corpus_v2 import ROOT, sha256, write_once
from scripts_evolve.loan_reference import (
    INPUTS, INPUT_SHA256, ORIGINAL_PATH, ORIGINAL_SHA256, keyword_tags, load_inputs, load_original,
)
from scripts_evolve.main_preflight import checked_path, read

METHODS = ('original', 'full_windows', 'compact_cover')
WIDTH = 1500
DEVELOPMENT = 'development_exposed_or_linked'
PARENTS = {
    'research/loan_reference_1000_v1/candidate_pool.json':
        '4c27ceac3ecea1023b8ac8f296ab1cc9909198723a30b7d7ecd3dfe3ad074b61',
    'research/loan_reference_1000_v1/chunk_audit.json':
        'f7d46e13d69b4e9ef9b2c5caf854ece8f52c0efd17e769a952dce9746d807bb8',
}


def refine_parent(parent: dict, source: str, taxonomy: dict) -> dict[str, list[dict]]:
    """Retain original parent tags through bounded exact-source reference windows."""
    keywords = [kw for info in taxonomy.values() for kw in info['keywords']]
    if not keywords or any(not kw or len(kw) > WIDTH for kw in keywords):
        raise ValueError('Nonempty bounded taxonomy keywords required')
    start, end = parent['paragraph_start'], parent['paragraph_end']
    if any(type(n) is not int for n in (start, end)) or not 0 <= start < end <= len(source):
        raise ValueError('Invalid parent source range')
    paragraph = source[start:end]
    expected = keyword_tags(paragraph, taxonomy)
    if expected != parent['original_tags'] or not expected:
        raise ValueError('Original parent tags differ from source')

    def chunk(first: int, last: int, identifier: str, tags: list[str]) -> dict:
        return {'doc': parent['doc_id'], 'chunk_id': identifier,
                'parent_chunk_id': parent['chunk_id'], 'text': source[first:last], 'tags': tags,
                'source_start': first, 'source_end': last}

    original = chunk(start, min(start + WIDTH, end), parent['chunk_id'], expected)
    overlap = max(len(kw) for kw in keywords) - 1
    windows, first, index = [], start, 0
    while first < end:
        last = min(first + WIDTH, end)
        tags = keyword_tags(source[first:last], taxonomy)
        if tags:
            windows.append(chunk(first, last, f"{parent['chunk_id']}:w{index}", tags))
        if last == end:
            break
        first = last - overlap
        index += 1
    uncovered, compact = set(expected), []
    while uncovered:
        best = min(windows, key=lambda row: (-len(uncovered.intersection(row['tags'])), row['source_start']))
        if not uncovered.intersection(best['tags']):
            raise ValueError('Windowing lost an original parent tag')
        compact.append(best)
        uncovered.difference_update(best['tags'])
    compact.sort(key=lambda row: row['source_start'])
    return {'original': [original], 'full_windows': windows, 'compact_cover': compact}


def measure(pool: list[dict], expected: dict[str, set[str]], taxonomy: dict) -> dict:
    """Use fixed parent/category denominators; duplicated windows cannot inflate recall."""
    if len({r['chunk_id'] for r in pool}) != len(pool) or any(r['parent_chunk_id'] not in expected for r in pool):
        raise ValueError('Unknown parent or duplicate candidate chunk')
    retained = defaultdict(set)
    assignments = unsupported = 0
    for row in pool:
        visible = set(keyword_tags(row['text'], taxonomy))
        retained[row['parent_chunk_id']].update(set(row['tags']).intersection(visible))
        assignments += len(row['tags'])
        unsupported += len(set(row['tags']) - visible)
    total = sum(len(tags) for tags in expected.values())
    present = sum(len(tags.intersection(retained[parent])) for parent, tags in expected.items())
    intervals = defaultdict(list)
    for row in pool:
        intervals[row['doc']].append((row['source_start'], row['source_end']))
    covered = 0
    for spans in intervals.values():
        cursor = 0
        for start, end in sorted(spans):
            covered += max(0, end - max(start, cursor))
            cursor = max(cursor, end)
    return {'chunks': len(pool), 'indexed_characters': sum(len(r['text']) for r in pool),
            'union_source_characters': covered,
            'original_parent_count': len(expected), 'original_parent_tag_pairs': total,
            'visible_parent_tag_pairs': present, 'emitted_tag_assignments': assignments,
            'unsupported_emitted_tag_assignments': unsupported,
            'parent_tag_retention': present / total if total else None,
            'visible_tag_consistency': (assignments - unsupported) / assignments if assignments else None,
            'bounded_source_spans': all(0 <= r['source_start'] < r['source_end']
                and r['source_end'] - r['source_start'] == len(r['text']) <= WIDTH for r in pool),
            'scope': 'Literal keyword visibility and index size, not relevance, legal accuracy or measured latency.'}


def select_candidate(scores: dict[str, dict]) -> str:
    """Select smallest structurally valid development index, never by reserved results."""
    eligible = [name for name in METHODS if scores[name]['parent_tag_retention'] == 1
                and scores[name]['visible_tag_consistency'] == 1 and scores[name]['bounded_source_spans']]
    if not eligible:
        raise ValueError('No candidate passes the structural gate')
    priority = {'compact_cover': 0, 'full_windows': 1, 'original': 2}
    return min(eligible, key=lambda name: (scores[name]['indexed_characters'], priority[name]))


def compare_document(row: dict, parents: list[dict], baseline: list[dict],
                     taxonomy: dict, root: Path) -> dict:
    """Check frozen bytes and baseline reproduction before evaluating either candidate."""
    checked_path(root, row['source_path'], row['source_sha256'])
    source = checked_path(root, row['text_path'], row['text_sha256']).read_bytes().decode('utf-8')
    pools = {name: [] for name in METHODS}
    for parent in parents:
        if parent['doc_id'] != row['doc_id']:
            raise ValueError('Parent belongs to another source')
        variants = refine_parent(parent, source, taxonomy)
        for name in METHODS:
            for candidate in variants[name]:
                if source[candidate['source_start']:candidate['source_end']] != candidate['text']:
                    raise ValueError('Candidate source span differs')
            pools[name].extend(variants[name])
    original = [{k: r[k] for k in ('doc', 'chunk_id', 'text', 'tags')} for r in pools['original']]
    if original != baseline:
        raise ValueError('Original archived reference pool not reproduced')
    expected = {r['chunk_id']: set(r['original_tags']) for r in parents}
    return {'document': row, 'pools': pools, 'expected': expected,
            'scores': {name: measure(pools[name], expected, taxonomy) for name in METHODS}}


def aggregate(results: list[dict], taxonomy: dict) -> dict:
    """Preserve every supplied document, including zero-chunk and quality-flag rows."""
    expected = {key: tags for r in results for key, tags in r['expected'].items()}
    return {'documents': len(results), 'zero_original_chunk_documents': sum(not r['expected'] for r in results),
            'quality_flagged_documents': sum(r['document']['status'] != 'success' for r in results),
            'methods': {name: measure([c for r in results for c in r['pools'][name]], expected, taxonomy)
                        for name in METHODS}}


def run(root: Path, output: Path) -> dict:
    """Freeze, select on 22 development sources, then apply unchanged to all 1,000 loans."""
    if output.resolve().parent != root.resolve() / 'research' or output.exists():
        raise ValueError('Use a new direct child of research; preserve earlier evidence')
    documents = load_inputs(root)
    values = {name: read(checked_path(root, name, expected)) for name, expected in PARENTS.items()}
    checked_path(root, ORIGINAL_PATH, ORIGINAL_SHA256)
    original = load_original(root)
    taxonomy = original['LOAN_TAXONOMY']
    baseline, parents = defaultdict(list), defaultdict(list)
    for r in values['research/loan_reference_1000_v1/candidate_pool.json']['chunks']:
        baseline[r['doc']].append(r)
    for r in values['research/loan_reference_1000_v1/chunk_audit.json']['chunks']:
        parents[r['doc_id']].append(r)
    development = [r for r in documents if r['allocation'] == DEVELOPMENT]
    if len(documents) != 1000 or len(development) != 22 or any(r['status'] != 'success' for r in development):
        raise ValueError('Frozen loan/development roster differs')
    implementations = ['scripts_evolve/loan_reference_refinement.py', 'scripts_evolve/loan_reference.py',
                       'scripts_evolve/main_preflight.py', 'scripts_evolve/full_corpus_v2.py', ORIGINAL_PATH]
    protocol = {'version': 1, 'parents_sha256': {**PARENTS, **{INPUTS[k]: v for k, v in INPUT_SHA256.items()}},
        'implementation_sha256': {p: sha256((root / p).read_bytes()) for p in implementations},
        'plan_sha256': sha256((root / 'research/loan_reference_refinement_plan.md').read_bytes()),
        'main_cohort_documents': 3000, 'loan_documents': 1000, 'development_documents': 22,
        'methods': list(METHODS), 'maximum_chunk_characters': WIDTH,
        'overlap_characters': max(len(kw) for info in taxonomy.values() for kw in info['keywords']) - 1,
        'selection_rule': 'Complete parent/tag retention and visible-tag consistency; bounded exact source spans; '
                          'minimum development indexed characters, tie compact_cover/full_windows/original.',
        'exposure': 'Motivating truncation defect was observed in prior all-source diagnostics; NOT untouched held-out.',
        'model_calls': 0, 'runtime_default_changed': False, 'relevance_gold_verified': False,
        'scope': 'Two manually engineered structural revisions, not LLM-generated outer-loop evolution or retrieval accuracy.'}
    write_once(output / 'protocol.json', protocol)
    for path in implementations:
        destination = output / 'snapshot' / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / path, destination)
    results = [compare_document(r, parents[r['doc_id']], baseline[r['doc_id']], taxonomy, root) for r in development]
    dev_scores = aggregate(results, taxonomy)
    write_once(output / 'development.json', {'document_ids': [r['document']['doc_id'] for r in results], **dev_scores})
    selected = select_candidate(dev_scores['methods'])
    write_once(output / 'selection.json', {'method': selected, 'development_sha256': sha256((output / 'development.json').read_bytes()),
                                         'runtime_admitted': False, 'reason': protocol['selection_rule']})
    for row in documents:
        if row['allocation'] != DEVELOPMENT:
            results.append(compare_document(row, parents[row['doc_id']], baseline[row['doc_id']], taxonomy, root))
    results.sort(key=lambda r: r['document']['doc_id'])
    all_scores = aggregate(results, taxonomy)
    reserved = aggregate([r for r in results if r['document']['allocation'] != DEVELOPMENT], taxonomy)
    for name in METHODS:
        write_once(output / f'{name}_pool.json', {'chunks': [c for r in results for c in r['pools'][name]]})
    manifest = {'protocol': protocol, 'selected_structural_candidate': selected,
        'development': dev_scores, 'all_loans': all_scores, 'evaluation_reserved_not_held_out': reserved,
        'documents': [{**r['document'], 'method_scores': r['scores']} for r in results],
        'main_experiment_complete': False, 'retrieval_quality_verified': False, 'runtime_default_changed': False}
    write_once(output / 'manifest.json', manifest)
    print(json.dumps({'selected_structural_candidate': selected, 'development': dev_scores,
                      'all_loans': all_scores, 'model_calls': 0}, ensure_ascii=False), flush=True)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'research/loan_reference_refinement_01')
    args = parser.parse_args()
    run(ROOT, args.output.resolve())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
