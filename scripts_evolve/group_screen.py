"""Offline provenance/near-copy grouping for the fixed 3,000-source cohort.

No source is removed. A high lexical overlap conservatively joins evaluation
groups; it does not prove the PDFs, contracts, parties or legal effects identical.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from functools import lru_cache
import hashlib
import heapq
import json
from pathlib import Path
import re
import shutil
import unicodedata

from scripts_evolve.full_corpus_v2 import DOMAINS, ROOT, sha256, write_once
from scripts_evolve.main_preflight import checked_path, check_roster, read

SKETCH_SIZE = 128
CANDIDATE_THRESHOLD = .65
EXACT_THRESHOLD = .90


def token_shingles(text: str) -> set[int]:
    """Distinct five-token shingles; 64-bit hashes are not semantic labels."""
    tokens = re.findall(r'\w+', unicodedata.normalize('NFKC', text).casefold())
    return {int.from_bytes(hashlib.blake2b('\0'.join(tokens[i:i + 5]).encode(),
                digest_size=8, person=b'fin-5tok-v1').digest(), 'big')
            for i in range(len(tokens) - 4)}


def sketch_jaccard(left: set[int], right: set[int]) -> float:
    sample = set(heapq.nsmallest(SKETCH_SIZE, left | right))
    return len(left & right & sample) / len(sample) if sample else 0.0


def fingerprint(row: dict, root: Path) -> dict:
    checked_path(root, row['source_path'], row['source_sha256'])
    result = {k: row[k] for k in ('doc_id', 'domain', 'source_sha256')}
    result.update(extraction_status=row['status'], screenable=False, sketch=[], unique_shingles=0,
                  text_sha256=row.get('text_sha256'), normalized_tokens_policy='NFKC/casefold, Unicode word tokens, five-token shingles')
    if not row.get('text_path'):
        if row['status'] == 'success':
            raise ValueError('Successful source missing text')
        return result
    path = checked_path(root, row['text_path'], row['text_sha256'])
    text = path.read_bytes().decode('utf-8')
    values = token_shingles(text) if len(text.strip()) >= 1000 else set()
    result.update(unique_shingles=len(values), screenable=len(values) >= 30,
                  sketch=heapq.nsmallest(SKETCH_SIZE, values) if len(values) >= 30 else [])
    return result


def add_path_group(row: dict) -> dict:
    result = deepcopy(row)
    parts = Path(row['source_path']).parts
    if row['domain'] != 'kr_insurance' or row['grouping']['labels'] or parts[:4] != ('ECC_harness_v3_txt', 'data', 'raw', 'contracts'):
        return result
    for part in parts[4:]:
        match = re.match(r'^([^_]+(?:생명|손해보험|라이프|화재))_', part)
        if match:
            label = 'kr_insurer:' + unicodedata.normalize('NFKC', match[1]).casefold()
            result['grouping']['labels'].append(label)
            result['grouping']['evidence'].append({'label': label, 'basis': 'unverified_original_product_path_component',
                                                  'path_component': part, 'source_path': row['source_path']})
    result['grouping']['labels'] = sorted(set(result['grouping']['labels']))
    return result


def near_edges(rows: list[dict], fingerprints: list[dict], root: Path,
               candidate_threshold: float = CANDIDATE_THRESHOLD) -> tuple[list[dict], dict]:
    if Counter(r['doc_id'] for r in rows) != Counter(r['doc_id'] for r in fingerprints):
        raise ValueError('Fingerprint roster mismatch')
    by_id = {r['doc_id']: r for r in rows}
    prints = {r['doc_id']: r for r in fingerprints}
    for identity, row in by_id.items():
        if any(prints[identity][k] != row.get(k) for k in ('domain', 'source_sha256', 'text_sha256')):
            raise ValueError('Fingerprint identity mismatch')
    sketches = {k: set(p['sketch']) for k, p in prints.items()}

    @lru_cache(maxsize=16)
    def full(identity):
        row = by_id[identity]
        path = checked_path(root, row['text_path'], row['text_sha256'])
        return token_shingles(path.read_bytes().decode('utf-8'))

    edges = []
    counts = Counter()
    for domain in DOMAINS:
        selected = sorted(r['doc_id'] for r in rows if r['domain'] == domain and prints[r['doc_id']]['screenable'])
        for i, first in enumerate(selected):
            left = sketches[first]
            for second in selected[i + 1:]:
                if by_id[first]['leakage_component_id'] == by_id[second]['leakage_component_id']:
                    continue
                counts['cross_component_pairs_screened'] += 1
                right = sketches[second]
                # Upper bound on the bottom-k intersection estimate; avoids sorting unrelated pairs.
                if len(left & right) / min(SKETCH_SIZE, len(left | right)) < candidate_threshold:
                    continue
                approximate = sketch_jaccard(left, right)
                if approximate < candidate_threshold:
                    continue
                counts['candidate_pairs_verified'] += 1
                a, b = full(first), full(second)
                overlap, union = len(a & b), len(a | b)
                exact = overlap / union
                if exact >= EXACT_THRESHOLD:
                    edges.append({'documents': [first, second], 'domain': domain,
                                  'bottom_k_estimate': approximate, 'hashed_shingle_jaccard': exact,
                                  'intersection_shingles': overlap, 'union_shingles': union,
                                  'interpretation': 'conservative lexical leakage edge, NOT proof of identical contracts'})
            if (i + 1) % 200 == 0:
                print(json.dumps({'screen_domain': domain, 'left_documents': i + 1,
                                  'candidate_pairs_verified': counts['candidate_pairs_verified']}), flush=True)
    counts['accepted_cross_component_edges'] = len(edges)
    return edges, dict(counts)


def allocate(rows: list[dict], edges: list[dict]) -> list[dict]:
    result = deepcopy(rows)
    by_id = {r['doc_id']: i for i, r in enumerate(result)}
    if len(by_id) != len(rows):
        raise ValueError('Duplicate allocation document ID')
    parents = list(range(len(rows)))

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    seen = {}
    for i, row in enumerate(result):
        labels = row['grouping']['labels'] + ['preflight_component:' + row['leakage_component_id']]
        for label in labels:
            key = row['domain'], label
            if key in seen:
                parents[find(i)] = find(seen[key])
            else:
                seen[key] = i
    for edge in edges:
        ids = edge['documents']
        if len(ids) != 2 or ids[0] == ids[1] or any(identity not in by_id for identity in ids):
            raise ValueError('Invalid near-copy edge')
        a, b = (by_id[identity] for identity in ids)
        if result[a]['domain'] != result[b]['domain']:
            raise ValueError('Cross-domain near-copy edge')
        parents[find(a)] = find(b)
    components = defaultdict(list)
    for i in range(len(result)):
        components[find(i)].append(i)
    for members in components.values():
        identities = sorted(result[i]['doc_id'] for i in members)
        identity = sha256('\n'.join(identities).encode())[:20]
        exposed = any(result[i]['pilot_membership'] for i in members)
        labels = sorted({label for i in members for label in result[i]['grouping']['labels']})
        allocation = 'development_exposed_or_linked' if exposed else 'evaluation_reserved' if labels else 'group_review_required'
        for i in members:
            result[i].update(component_id=identity, component_size=len(members), component_labels=labels,
                             component_has_pilot_member=exposed, allocation=allocation, held_out_verified=False)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'research/main_3000_groups_v1')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'research'):
        parser.error('Output must be under research')
    paths = {'sources': ROOT / 'research/dataset_3000_v2/source_manifest.json',
             'extractions': ROOT / 'research/dataset_3000_v2/extraction_manifest.json',
             'preflight': ROOT / 'research/main_3000_preflight_v2/manifest.json'}
    values = {k: read(p) for k, p in paths.items()}
    check_roster(values['sources']['documents'], values['extractions']['documents'])
    expected = values['preflight']['protocol']
    if expected['source_manifest_sha256'] != sha256(paths['sources'].read_bytes()) or expected['extraction_manifest_sha256'] != sha256(paths['extractions'].read_bytes()):
        raise ValueError('Preflight parent identity changed')
    preflight = {r['doc_id']: r for r in values['preflight']['documents']}
    if len(preflight) != 3000 or set(preflight) != {r['doc_id'] for r in values['sources']['documents']}:
        raise ValueError('Preflight roster differs from fixed cohort')
    rows = []
    for row in values['extractions']['documents']:
        prior = preflight[row['doc_id']]
        if any(row[k] != prior[k] for k in ('domain', 'source_sha256', 'source_path', 'pilot_membership')):
            raise ValueError('Preflight source/exposure identity changed')
        rows.append(add_path_group({**row, **{k: prior[k] for k in ('grouping', 'leakage_component_id', 'nonempty_exact_text_group')}}))
    implementations = [Path(__file__), ROOT / 'scripts_evolve/main_preflight.py', ROOT / 'scripts_evolve/full_corpus_v2.py']
    protocol = {'input_sha256': {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()) for p in paths.values()},
                'implementation_sha256': {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()) for p in implementations},
                'target_total': 3000, 'per_domain': 1000, 'model_calls': 0,
                'candidate_screen': {'method': 'bottom-k union Jaccard estimate', 'k': SKETCH_SIZE, 'threshold': CANDIDATE_THRESHOLD},
                'edge_gate': {'method': 'full distinct five-token hashed-shingle Jaccard', 'threshold': EXACT_THRESHOLD},
                'limitations': 'Approximate candidate screening can miss pairs. Hash collisions are theoretically possible. '
                               'Raw extraction only; OCR candidates are not admitted. Lexical similarity is not semantic equivalence. '
                               'Groups use collection/filename labels, not verified party/affiliate identities. Reserved is not a verified held-out claim.'}
    write_once(output / 'protocol.json', protocol)
    for path in implementations:
        destination = output / 'snapshot' / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.read_bytes() != path.read_bytes():
            raise ValueError('Grouping snapshot changed')
        if not destination.exists():
            shutil.copyfile(path, destination)
    prints = []
    for row in rows:
        value = fingerprint(row, ROOT)
        write_once(output / 'fingerprints' / (row['doc_id'] + '.json'), value)
        prints.append(value)
        if len(prints) % 250 == 0:
            print(json.dumps({'fingerprinted': len(prints), 'total': 3000, 'model_calls': 0}), flush=True)
    edges, counts = near_edges(rows, prints, ROOT)
    allocation = allocate(rows, edges)
    summary = {'inputs': len(rows), 'domains': {domain: dict(Counter(r['allocation'] for r in allocation if r['domain'] == domain)) for domain in DOMAINS},
               'screenable': sum(p['screenable'] for p in prints), **counts, 'allocation_frozen': True,
               'held_out_verified': False, 'model_calls': 0, 'main_experiment_complete': False}
    write_once(output / 'near_copy_edges.json', {'protocol': protocol, 'counts': counts, 'edges': edges})
    write_once(output / 'allocation_manifest.json', {'protocol': protocol, 'summary': summary, 'documents': allocation,
                'fingerprint_sha256': {r['doc_id']: sha256((output / 'fingerprints' / (r['doc_id'] + '.json')).read_bytes()) for r in rows}})
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
