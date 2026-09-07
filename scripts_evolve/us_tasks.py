"""Original US task rules plus explicit, lossless GPT transport adaptations.

Only named declarations are loaded from the original task files. Their module
initializers, environment-file loaders and Anthropic clients are never executed.
"""
from __future__ import annotations

import ast
from collections import defaultdict
from copy import deepcopy
import html
import math
from pathlib import Path
import re

import jsonschema

from scripts_evolve.native_schemas import SCORE, TEXT, array, obj

ORIGINAL_FILES = {
    'card_spot': 'eval_US_card/persona/us_vulnerability_spotter.py',
    'card_legal': 'eval_US_card/persona/us_legal_validator.py',
    'card_severity': 'eval_US_card/persona/us_severity_classifier.py',
    'loan': 'eval_US_loan/eval_loan.py',
}
SYMBOLS = {
    'card_spot': ('TAXONOMY_DESC', 'FEW_SHOT', 'NOISE_PATTERNS', 'preprocess', 'parse_sections'),
    'card_legal': ('US_STATUTE_MAP', 'TAX_QUERY', 'tokenize', 'rerank_bm25'),
    'card_severity': ('calc_user_relevance', 'classify_severity', 'overall_risk'),
    'loan': ('LOAN_TAXONOMY', 'TAXONOMY_BLOCK', 'BORROWER_PROFILE', 'OURS_SYSTEM_BLOCK',
             'strategy_ours', 'tokenize', 'build_idf', 'tfidf_vec', 'cosine', 'bm25_scores', 'retrieve',
             'build_candidate_pool'),
}
CARD_SCOPE = 'original_fixed_statute_mapping_and_model_selected_search_snippets; NOT legal validity'


def card_query(finding: dict, templates: dict) -> str:
    """Use original category query templates; never send raw Lucene operators."""
    raw = templates.get(finding['taxonomy']) or finding['triggered_by']
    words = re.findall(r'[a-z]{2,}', raw.lower())
    if finding['taxonomy'] == 'UNCATEGORIZED':
        words = [w for w in words if len(w) > 3][:8] + ['credit', 'card', 'consumer', 'rights']
    words = list(dict.fromkeys(w for w in words if w not in ('and', 'or', 'not')))
    kept = []
    for word in words:
        if len(' '.join(kept + [word])) > 120:
            break
        kept.append(word)
    return ' '.join(kept) or 'credit card consumer protection'


def load_original_tasks(root: Path) -> dict:
    tasks = {}
    for task, relative in ORIGINAL_FILES.items():
        path = root / relative
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        selected = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in SYMBOLS[task]:
                selected.append(node)
            elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in SYMBOLS[task] for t in node.targets):
                selected.append(node)
        namespace = {'re': re, 'math': math, 'defaultdict': defaultdict}
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
        if any(name not in namespace for name in SYMBOLS[task]):
            raise ValueError(f'Original task declarations missing: {task}')
        tasks[task] = namespace
    return tasks


def source_windows(text: str, max_chars: int = 18000) -> list[dict]:
    """Cover every source character with 240-character units and overlapping windows."""
    if not text.strip() or max_chars < 1000:
        raise ValueError('Nonempty source and a window budget of at least 1000 required')
    units, offset = [], 0
    for line in text.splitlines(keepends=True):
        for start in range(0, len(line), 240):
            piece = line[start:start + 240]
            units.append({'index': len(units), 'start': offset, 'end': offset + len(piece), 'text': piece})
            offset += len(piece)
    windows, first = [], 0
    while first < len(units):
        last = first + 1
        while last < len(units) and units[last]['end'] - units[first]['start'] <= max_chars:
            last += 1
        window_units = units[first:last]
        windows.append({'index': len(windows), 'start': window_units[0]['start'],
                        'end': window_units[-1]['end'], 'units': window_units})
        if last == len(units):
            break
        first = max(first + 1, last - 2)
    return windows


def spot_schema(domain: str, window: dict) -> dict:
    if domain not in ('us_card', 'us_loan'):
        raise ValueError('Unsupported US domain')
    index = {'type': 'integer', 'minimum': window['units'][0]['index'], 'maximum': window['units'][-1]['index']}
    labels = [f'CC-{i:02}' for i in range(1, 6)] + ['UNCATEGORIZED'] if domain == 'us_card' else [f'LOAN-{i:02}' for i in range(1, 6)]
    fields = {'first_unit': index, 'last_unit': index, 'taxonomy': {'type': 'string', 'enum': labels},
              'retrieval_query': {**TEXT, 'maxLength': 80 if domain == 'us_loan' else 240}}
    if domain == 'us_loan':
        del fields['first_unit']
        del fields['last_unit']
        fields['source_unit'] = index
    if domain == 'us_card':
        fields.update(title={**TEXT, 'maxLength': 50}, confidence=SCORE, user_relevance=SCORE,
                      uncategorized_reason={'type': 'string'})
    return obj({'findings': array(obj(fields))})


def materialize_spot(domain: str, window: dict, output: dict) -> list[dict]:
    try:
        jsonschema.validate(output, spot_schema(domain, window))
    except jsonschema.ValidationError as exc:
        raise ValueError('Spotter schema or source range invalid') from exc
    units = {row['index']: row for row in window['units']}
    findings = []
    for proposal in output['findings']:
        first, last = (proposal['source_unit'], proposal['source_unit']) if domain == 'us_loan' else (proposal['first_unit'], proposal['last_unit'])
        if first > last:
            raise ValueError('Reversed source range')
        raw = ''.join(units[i]['text'] for i in range(first, last + 1))
        quote = raw.strip()
        if not quote or (domain == 'us_loan' and len(quote) > 300):
            raise ValueError('Empty quote or loan evidence over 300 characters; no truncation performed')
        if proposal.get('taxonomy') == 'UNCATEGORIZED' and not proposal['uncategorized_reason'].strip():
            raise ValueError('UNCATEGORIZED requires a reason')
        start = units[first]['start'] + len(raw) - len(raw.lstrip())
        row = {k: v for k, v in proposal.items() if k not in ('first_unit', 'last_unit', 'source_unit')}
        row.update(triggered_by=quote, source_start=start, source_end=start + len(quote),
                   source_units=[first, last], window_index=window['index'])
        findings.append(row)
    return findings


def opinion_candidates(response: dict) -> list[dict]:
    """CourtListener V4 uses clusters with nested opinion snippets, not docket IDs."""
    result, seen = [], set()
    for item in response['results']:
        cluster, url = item.get('cluster_id'), item.get('absolute_url', '')
        if type(cluster) is not int or cluster < 1 or not url.startswith(f'/opinion/{cluster}/'):
            raise ValueError('Invalid CourtListener candidate identity')
        if cluster in seen:
            continue
        seen.add(cluster)
        opinions = item.get('opinions', [])
        snippet = html.unescape(re.sub(r'<[^>]+>', '', '\n'.join(p.get('snippet') or '' for p in opinions)))
        result.append({'candidate_id': f'courtlistener:cluster:{cluster}', 'cluster_id': cluster,
                       'opinion_ids': [p['id'] for p in opinions if type(p.get('id')) is int],
                       'case_number': item.get('docketNumber'), 'case_name': item.get('caseName'),
                       'citations': item.get('citation', []), 'court': item.get('court'),
                       'date': item.get('dateFiled'), 'snippet': snippet,
                       '_full': (item.get('caseName') or '') + '\n' + snippet,
                       'url': 'https://www.courtlistener.com' + url,
                       'source': 'CourtListener V4 search; snippet only'})
    return result


def card_validation(drafts: list[dict], searches: list[list[dict]], decisions: dict,
                    statute_map: dict) -> list[dict]:
    if len(drafts) != len(searches):
        raise ValueError('Search/result count mismatch')
    expected = {str(i) for i, row in enumerate(drafts) if row['confidence'] >= .55 and searches[i]}
    if set(decisions) != expected:
        raise ValueError('Every nonempty candidate set requires exactly one decision')
    findings = []
    for index, draft in enumerate(drafts):
        low = draft['confidence'] < .55
        candidates = {c['candidate_id']: c for c in searches[index]}
        decision = decisions.get(str(index), {'case_ids': [], 'note': 'No case candidates to assess.'})
        selected = decision['case_ids']
        if len(set(selected)) != len(selected) or any(key not in candidates for key in selected):
            raise ValueError('Selected case outside finding candidate set or repeated')
        statutes = [] if low else [{'law_name': law, 'article': article, 'verified': False,
                                    'verification_scope': CARD_SCOPE}
                                   for law, article in statute_map.get(draft['taxonomy'], [])]
        precedents = [deepcopy(candidates[key]) for key in selected]
        status = 'LOW_CONFIDENCE' if low else 'CONFIRMED' if statutes or precedents else 'UNVERIFIED'
        findings.append({**draft, 'finding_id': draft['id'], 'status': status, 'legacy_status': status,
                         'user_relevance_score': draft['user_relevance'],
                         'legal_grounds': {'statutes': statutes, 'precedents': precedents},
                         'validator_note': decision['note'], 'validation_scope': CARD_SCOPE,
                         'legal_validity_verified': False})
    return findings
