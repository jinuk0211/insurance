"""Offline E1 on every frozen source; lexical proxies are not legal accuracy.

Original rule filters are executed from selected AST declarations. Ranking is
an explicitly labelled algebraic float64 adaptation, not a byte-identical claim.
No LLM, paid API, summarization-model download or fallback is invoked.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import importlib.util
import math
from pathlib import Path
import re
import shutil
import sys

import numpy as np
import scipy
from scipy.sparse import csr_matrix

from scripts_evolve.full_corpus_v2 import DOMAINS, ROOT, sha256, write_once
from scripts_evolve.main_preflight import check_roster, checked_path, read

ORIGINALS = {'kr_insurance': 'eval_KR_ins/eval_kr_ins.py',
             'us_card': 'eval_US_card/e1_preprocessing_us.py',
             'us_loan': 'eval_US_loan/eval_loan.py'}
SYMBOLS = ('INS_TAXONOMY', 'LOAN_TAXONOMY', 'VULN_KEYWORDS_FLAT', 'VULN_KEYWORDS',
           'BOILERPLATE_EXACT', 'BOILERPLATE_PREFIX', 'BOILERPLATE_SUBSTR', 'NOISE_PATTERNS',
           'tokenize', 'cosine', 'tfidf_cosine', 'strategy_raw', 'strategy_ours', 'strategy_textrank')
RANK_CONFIG = {'kr_insurance': (r'(?<=[다요니까])\.\s+|(?<=[다요니까])\n+|\n{2,}', 10, 50),
               'us_card': (r'(?<=[.!?])\s+', 20, 3),
               'us_loan': (r'(?<=[.\?\!])\s+(?=[A-Z])|\n{2,}', 25, 80)}
METRICS = ('character_ratio', 'whitespace_unit_ratio', 'source_keyword_retention',
           'legacy_inventory_hit_rate', 'tfidf_pairwise_lexical_cosine')


def load_originals(root: Path) -> dict:
    tasks = {}
    for domain, relative in ORIGINALS.items():
        path = root / relative
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        selected = [node for node in tree.body
                    if (isinstance(node, ast.FunctionDef) and node.name in SYMBOLS)
                    or (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in SYMBOLS for t in node.targets))]
        namespace = {'re': re, 'math': math, 'defaultdict': defaultdict}
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
        if not all(k in namespace for k in ('tokenize', 'strategy_raw', 'strategy_ours', 'strategy_textrank')):
            raise ValueError('Missing original preprocessing declarations: ' + domain)
        namespace['keywords'] = namespace.get('VULN_KEYWORDS_FLAT', namespace.get('VULN_KEYWORDS'))
        if not namespace['keywords']:
            raise ValueError('Missing original keyword inventory')
        tasks[domain] = namespace
    return tasks


def count_matrix(sentences: list[str], tokenize) -> csr_matrix:
    vocabulary, rows, columns, values = {}, [], [], []
    for i, sentence in enumerate(sentences):
        for token, count in Counter(tokenize(sentence)).items():
            rows.append(i)
            columns.append(vocabulary.setdefault(token, len(vocabulary)))
            values.append(count)
    return csr_matrix((values, (rows, columns)), shape=(len(sentences), len(vocabulary)), dtype=np.float64)


def pagerank_scores(counts: csr_matrix) -> np.ndarray:
    """Compute the original complete cosine graph without allocating N x N.

    Diagonal removal and dangling-mass loss match the original 30 iterations.
    Associativity/tie differences in float64 are possible and disclosed.
    """
    n = counts.shape[0]
    norm = np.sqrt(np.asarray(counts.multiply(counts).sum(axis=1)).ravel())
    x = counts.multiply((1 / np.where(norm > 0, norm, 1))[:, None]).tocsr()
    diagonal = np.asarray(x.multiply(x).sum(axis=1)).ravel()
    row_sums = np.maximum(0, np.asarray(x @ (x.T @ np.ones(n))).ravel() - diagonal)
    row_sums = np.where(row_sums > 1e-12, row_sums, 1)
    scores = np.full(n, 1 / n)
    for _ in range(30):
        weighted = scores / row_sums
        scores = (1 - 0.85) / n + 0.85 * np.maximum(0, x @ (x.T @ weighted) - diagonal * weighted)
    return scores


def card_weights(counts: csr_matrix, start: int, end: int) -> np.ndarray:
    """Original pair-local IDF cosine, rounded to four decimals, in row blocks.

    Shared terms have IDF=1; unshared terms have IDF=log(3/2)+1. TF
    denominators cancel in cosine. This is the original degree heuristic,
    NOT PageRank and NOT a corpus-IDF standard TextRank implementation.
    """
    block = counts[start:end]
    squared = counts.multiply(counts)
    present = counts.copy()
    present.data[:] = 1
    shared_left = (squared[start:end] @ present.T).toarray()
    shared_right = (present[start:end] @ squared.T).toarray()
    total = np.asarray(squared.sum(axis=1)).ravel()
    a2 = (math.log(1.5) + 1) ** 2
    left = a2 * total[start:end, None] + (1 - a2) * shared_left
    right = a2 * total[None, :] + (1 - a2) * shared_right
    denominator = np.sqrt(np.maximum(0, left * right))
    weights = np.divide((block @ counts.T).toarray(), denominator,
                        out=np.zeros_like(denominator), where=denominator > 0)
    weights = np.round(weights, 4)
    weights[np.arange(end - start), np.arange(start, end)] = 0
    return weights


def fast_rank(text: str, domain: str, tokenize) -> tuple[str, dict]:
    pattern, minimum, limit = RANK_CONFIG[domain]
    sentences = [s.strip() for s in re.split(pattern, text.strip() if domain == 'us_card' else text)
                 if len(s.strip()) > minimum]
    n = len(sentences)
    details = {'implementation': 'algebraic_float64_adaptation_of_original', 'sentences': n,
               'algorithm': 'pair_local_tfidf_degree' if domain == 'us_card' else 'tf_cosine_pagerank_30_steps',
               'short_input_passthrough': n <= limit}
    if n <= limit:
        return text, details
    counts = count_matrix(sentences, tokenize)
    if domain == 'us_card':
        # cumsum follows the original left-to-right summation order.
        scores = np.concatenate([np.cumsum(card_weights(counts, i, min(i + 128, n)), axis=1)[:, -1]
                                 for i in range(0, n, 128)])
        limit = max(1, int(n * 0.6))
    else:
        scores = pagerank_scores(counts)
    selected = sorted(sorted(range(n), key=lambda i: -scores[i])[:limit])
    details['selected_sentences'] = selected
    return (' ' if domain == 'us_card' else '\n').join(sentences[i] for i in selected), details


def lexical_cosine(raw: str, output: str, korean: bool) -> float | None:
    pattern = r'[가-힣a-zA-Z0-9]{2,}' if korean else r'[a-zA-Z0-9]{2,}'
    first, second = (Counter(re.findall(pattern, t.lower())) for t in (raw, output))
    if not first or not second:
        return None
    common = first.keys() & second.keys()
    a2 = (math.log(1.5) + 1) ** 2
    numerator = sum(first[t] * second[t] for t in common)
    left = sum(c * c * (1 if t in common else a2) for t, c in first.items())
    right = sum(c * c * (1 if t in common else a2) for t, c in second.items())
    return min(1.0, numerator / math.sqrt(left * right))


def metrics(raw: str, output: str, keywords: list[str], korean: bool) -> dict:
    source, target = (raw, output) if korean else (raw.lower(), output.lower())
    inventory = keywords if korean else [k.lower() for k in keywords]
    unique = set(inventory)
    present = sorted(k for k in unique if k in source)
    lost = sorted(k for k in present if k not in target)
    input_units, output_units = len(raw.split()), len(output.split())
    return {'source_characters': len(raw), 'output_characters': len(output),
            'source_whitespace_units': input_units, 'output_whitespace_units': output_units,
            'character_ratio': len(output) / len(raw) if raw else None,
            'whitespace_unit_ratio': output_units / input_units if input_units else None,
            'inventory_size_with_duplicates': len(inventory), 'unique_inventory_size': len(unique),
            'source_present_keywords': present, 'lost_keywords': lost,
            'source_keyword_retention': (len(present) - len(lost)) / len(present) if present else None,
            'legacy_inventory_hit_rate': sum(k in target for k in inventory) / len(inventory),
            'tfidf_pairwise_lexical_cosine': lexical_cosine(raw, output, korean)}


def save_bytes(path: Path, data: bytes) -> str:
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('Existing artifact changed: ' + str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as handle:
            handle.write(data)
    return sha256(data)


def reference_checks(rows: list[dict], tasks: dict, root: Path) -> dict:
    """Compare unchanged original code on bounded, already-exposed real inputs.

    Sampling is deterministic by frozen roster order and sentence count only,
    not chosen by agreement. Disagreements are evidence, not silently repaired.
    """
    checks, counts = [], Counter()
    for row in rows:
        domain = row['domain']
        if counts[domain] >= 3 or row['allocation'] != 'development_exposed_or_linked':
            continue
        raw = checked_path(root, row['text_path'], row['text_sha256']).read_bytes().decode('utf-8')
        pattern, minimum, limit = RANK_CONFIG[domain]
        n = sum(len(s.strip()) > minimum for s in re.split(pattern, raw))
        if not limit < n <= 180 or row['status'] != 'success':
            continue
        original = tasks[domain]['strategy_textrank'](raw)
        adapted, details = fast_rank(raw, domain, tasks[domain]['tokenize'])
        checks.append({'doc_id': row['doc_id'], 'domain': domain, 'text_sha256': row['text_sha256'],
                       'sentence_count': n, 'original_output_sha256': sha256(original.encode('utf-8')),
                       'adapted_output_sha256': sha256(adapted.encode('utf-8')), 'exact_output_match': original == adapted,
                       'adapted_details': details})
        counts[domain] += 1
    return {'selection': 'First up to three mechanical-success development-linked documents per domain with non-passthrough sentence count <=180; no outcome selection.',
            'checks': checks, 'checked': len(checks), 'exact_matches': sum(c['exact_output_match'] for c in checks),
            'limitation': 'Small bounded implementation audit only, not full-cohort numerical equivalence or task accuracy.'}


def evaluate(row: dict, tasks: dict, parser, root: Path, output: Path) -> dict:
    checked_path(root, row['source_path'], row['source_sha256'])
    path = checked_path(root, row['text_path'], row['text_sha256'])
    raw = path.read_bytes().decode('utf-8')
    if len(raw) != row['characters']:
        raise ValueError('Frozen extraction character count changed')
    domain, korean = row['domain'], row['domain'] == 'kr_insurance'
    task = tasks[domain]
    result = {k: row[k] for k in ('doc_id', 'domain', 'source_path', 'source_sha256', 'text_path',
                                  'text_sha256', 'allocation', 'component_id', 'pilot_membership')}
    result.update(extraction_status=row['status'], mechanical_issues=row['mechanical_issues'],
                  language_verified=False, main_model_status='not_started', methods={})
    methods = ['raw', 'original_rule_filter', 'original_rank_float64'] + (['native_kr_parser_payload'] if korean else [])
    for method in methods:
        try:
            details, status = {}, 'completed'
            if method == 'raw':
                transformed = task['strategy_raw'](raw)
            elif method == 'original_rule_filter':
                transformed = task['strategy_ours'](raw)
            elif method == 'original_rank_float64':
                transformed, details = fast_rank(raw, domain, task['tokenize'])
            else:
                normalized = raw.replace('\r\n', '\n').replace('\r', '\n')
                clauses = parser(normalized, source_name=path.stem)
                transformed = '\n'.join(c['raw_text'] for c in clauses)
                details = {'clauses': len(clauses), 'at_1600_characters': sum(len(c['raw_text']) == 1600 for c in clauses),
                           'scope': 'Concatenated original raw_text fields only; excludes prompt, JSON metadata and repeated calls.',
                           'parser_newlines_normalized': normalized != raw}
                if not clauses:
                    status = 'no_parser_clauses'
            result['methods'][method] = {'status': status, 'details': details,
                                         'metrics': metrics(raw, transformed, task['keywords'], korean)}
        except Exception as exc:
            # Each failed method remains in the denominator, never replaced by raw.
            result['methods'][method] = {'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'}
            continue
        target = path if method == 'raw' else output / 'texts' / method / (row['doc_id'] + '.txt')
        digest = save_bytes(target, transformed.encode('utf-8'))
        result['methods'][method].update(output_path=target.relative_to(root).as_posix(), output_sha256=digest)
    return result


def summarize(rows: list[dict]) -> dict:
    domains = {}
    for domain in DOMAINS:
        domains[domain] = {}
        for stratum in ('all', 'mechanical_success', 'mechanical_review', 'development_exposed_or_linked', 'evaluation_reserved'):
            selected = [r for r in rows if r['domain'] == domain and
                        (stratum == 'all' or stratum == r['allocation']
                         or (stratum == 'mechanical_success' and r['extraction_status'] == 'success')
                         or (stratum == 'mechanical_review' and r['extraction_status'] != 'success'))]
            methods = sorted({m for r in selected for m in r['methods']})
            grouped = {}
            for method in methods:
                values = [r['methods'][method] for r in selected]
                aggregate = {'input_documents': len(selected), 'status_counts': dict(Counter(v['status'] for v in values)),
                             'extraction_status_counts': dict(Counter(r['extraction_status'] for r in selected))}
                for metric in METRICS:
                    defined = [v['metrics'][metric] for v in values if v.get('metrics', {}).get(metric) is not None]
                    aggregate[metric] = {'defined_documents': len(defined), 'undefined_or_failed_documents': len(values) - len(defined),
                                         'mean_defined': math.fsum(defined) / len(defined) if defined else None}
                grouped[method] = aggregate
            domains[domain][stratum] = grouped
    return {'input_documents': len(rows), 'domains': domains, 'new_model_calls': 0,
            'offline_preprocessing_measurement_complete': len(rows) == 3000,
            'main_model_experiment_complete': False, 'cost_usd': None}


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, default=ROOT / 'research/e1_3000_v1')
    args = cli.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'research'):
        cli.error('Output must be under research')
    paths = [ROOT / 'research/dataset_3000_v2/source_manifest.json',
             ROOT / 'research/dataset_3000_v2/extraction_manifest.json',
             ROOT / 'research/main_3000_groups_v1/allocation_manifest.json']
    sources, extractions, allocation = [read(p) for p in paths]
    check_roster(sources['documents'], extractions['documents'])
    check_roster(sources['documents'], allocation['documents'])
    by_id = {r['doc_id']: r for r in extractions['documents']}
    for row in allocation['documents']:
        if any(row[k] != v for k, v in by_id[row['doc_id']].items()):
            raise ValueError('Allocation extraction identity changed')
    implementations = [Path(__file__), ROOT / 'scripts_evolve/main_preflight.py', ROOT / 'scripts_evolve/full_corpus_v2.py',
                       ROOT / 'ECC_harness_v3_txt/scripts/parse_txt.py', *[ROOT / p for p in ORIGINALS.values()]]
    protocol = {'input_sha256': {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()) for p in paths},
                'implementation_sha256': {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()) for p in implementations},
                'runtime': {'python': sys.version, 'numpy': np.__version__, 'scipy': scipy.__version__},
                'per_domain': 1000, 'target_total': 3000, 'new_model_calls': 0,
                'rules': 'Original selected AST declarations, unchanged; frozen v2 extraction replaces old E1 PDF extraction.',
                'ranking': 'Algebraic float64 adaptation of original sentence split, TF cosine graph, d=.85, 30 steps, 50/80 selected sentences. '
                           'Card uses original pair-local IDF rounded-four-decimal degree score with ratio=.6, not PageRank. '
                           'Summation and rounding/ties can differ from original; no byte-equivalence claim. No source truncation.',
                'keyword_metrics': 'Literal substring inventory: KR case-sensitive, US lowercased. Legacy inventory hit-rate retains duplicates. '
                                   'Source retention deduplicates normalized inventory; denominator is keywords present in raw text; zero denominator is null. '
                                   'Not legal recall, semantic equivalence, occurrence retention or translated-language coverage.',
                'lexical_metric': 'Pair-local TF-IDF cosine; lowercase alphanumeric tokens length>=2, plus Hangul for KR. '
                                  'Empty token vectors yield null. This is lexical, not semantic, and differs from old corpus-IDF metrics.',
                'size_metrics': 'Unicode character and whitespace-unit output/input ratios, not billed model tokens. Empty denominator null.',
                'unavailable_methods': ['BART', 'KoBART', 'LLMLingua', 'ACE'],
                'limitations': 'All extraction failures/review flags and input IDs retained. OCR candidates not admitted. '
                               'Collection groups provisional; reserved not verified held-out. Card language not verified English-only. '
                               'Native KR parser payload measured separately from legacy rule filter. No downstream or legal-accuracy conclusion.'}
    write_once(output / 'protocol.json', protocol)
    for path in implementations:
        target = output / 'snapshot' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != path.read_bytes():
            raise ValueError('Snapshot changed')
        if not target.exists():
            shutil.copyfile(path, target)
    tasks = load_originals(output / 'snapshot')
    parser_path = output / 'snapshot/ECC_harness_v3_txt/scripts/parse_txt.py'
    spec = importlib.util.spec_from_file_location('original_e1_txt_parser', parser_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    write_once(output / 'keyword_inventories.json', {d: tasks[d]['keywords'] for d in DOMAINS})
    reference = reference_checks(allocation['documents'], tasks, ROOT)
    write_once(output / 'original_reference_checks.json', reference)
    print({'original_reference_checks': reference['checked'], 'exact_matches': reference['exact_matches']}, flush=True)
    results = []
    for row in allocation['documents']:
        value = evaluate(row, tasks, module.chunk_summary_doc, ROOT, output)
        write_once(output / 'documents' / (row['doc_id'] + '.json'), value)
        results.append(value)
        if len(results) % 100 == 0:
            print({'offline_e1_inputs': len(results), 'total': 3000, 'model_calls': 0}, flush=True)
    summary = summarize(results)
    write_once(output / 'summary.json', summary)
    write_once(output / 'manifest.json', {'protocol': protocol, 'summary': summary,
                'document_result_sha256': {r['doc_id']: sha256((output / 'documents' / (r['doc_id'] + '.json')).read_bytes()) for r in results}})
    print({'offline_e1_complete': len(results), 'main_model_experiment_complete': False}, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
