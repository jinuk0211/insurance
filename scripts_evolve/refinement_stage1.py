"""Executable, declarative Stage-1 mutations and fixed-denominator proxy gates.

The original filter is retained as a baseline. Model proposals are configuration
data, never Python, regular expressions, commands, paths or relaxed validators.
These gates do not establish preservation of every legally meaningful detail.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re

import jsonschema

from scripts_evolve.e1_cohort import lexical_cosine, metrics, save_bytes
from scripts_evolve.full_corpus_v2 import sha256, write_once
from scripts_evolve.native_schemas import obj
from scripts.pilot.codex_client import canonical

BASELINE = {'base': 'original', 'drop_exact_lines': [], 'drop_line_prefixes': [],
            'collapse_blank_lines': False, 'collapse_spaces': False, 'drop_separator_lines': False}
CONFIG_SCHEMA = obj({
    'base': {'type': 'string', 'enum': ['original', 'raw']},
    'drop_exact_lines': {'type': 'array', 'maxItems': 16,
                         'items': {'type': 'string', 'minLength': 1, 'maxLength': 160}},
    'drop_line_prefixes': {'type': 'array', 'maxItems': 8,
                           'items': {'type': 'string', 'minLength': 6, 'maxLength': 80}},
    'collapse_blank_lines': {'type': 'boolean'}, 'collapse_spaces': {'type': 'boolean'},
    'drop_separator_lines': {'type': 'boolean'},
})
FINANCIAL = re.compile(r'[$€£₩]\s*\d[\d,]*(?:\.\d+)?|\d[\d,.]*\s*%|\d[\d,]*(?:\.\d+)?\s*(?:억|만)?원')
GATES = {'minimum_baseline_whitespace_unit_fraction': 0.8, 'minimum_baseline_pairwise_lexical_cosine': 0.99,
         'preserve_baseline_inventory_keywords': True, 'preserve_financial_pattern_occurrence_counts': True,
         'limitations': 'Conservative lexical/numeric proxies only, not expert legal information-preservation labels.'}


def validate_config(config: dict) -> None:
    try:
        jsonschema.validate(config, CONFIG_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise ValueError('Invalid preprocessing candidate schema') from exc
    for key in ('drop_exact_lines', 'drop_line_prefixes'):
        if len({value.casefold() for value in config[key]}) != len(config[key]):
            raise ValueError('Duplicate case-insensitive line rules')
    for value in config['drop_exact_lines'] + config['drop_line_prefixes']:
        if not value.strip() or any(c in value for c in '\r\n\f') or value != value.strip():
            raise ValueError('Line rules must be nonblank single-line literals without outer whitespace')


def transform(raw: str, baseline: str, config: dict) -> str:
    validate_config(config)
    text = baseline if config['base'] == 'original' else raw
    if not any(config[k] for k in config if k != 'base'):
        return text
    exact = {s.casefold() for s in config['drop_exact_lines']}
    prefixes = tuple(s.casefold() for s in config['drop_line_prefixes'])
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.casefold() in exact or (prefixes and stripped.casefold().startswith(prefixes)):
            continue
        if config['drop_separator_lines'] and re.fullmatch(r'[_\-=*─━|+\s]{5,}', line):
            continue
        lines.append(re.sub(r'[ \t]{2,}', ' ', line) if config['collapse_spaces'] else line)
    result = '\n'.join(lines)
    if config['collapse_blank_lines']:
        result = re.sub(r'\n(?:[ \t]*\n){2,}', '\n\n', result)
    return result


def guard(baseline: str, output: str, keywords: list[str], korean: bool) -> list[str]:
    violations = []
    source, target = (baseline, output) if korean else (baseline.lower(), output.lower())
    inventory = keywords if korean else [k.lower() for k in keywords]
    if any(k in source and k not in target for k in set(inventory)):
        violations.append('lost_source_keyword')
    def values(text: str) -> Counter:
        return Counter(re.sub(r'\s+', '', match) for match in FINANCIAL.findall(text))

    if values(baseline) - values(output):
        violations.append('lost_financial_value')
    if baseline.strip() and not output.strip():
        violations.append('empty_output')
    if len(output.split()) < GATES['minimum_baseline_whitespace_unit_fraction'] * len(baseline.split()):
        violations.append('excessive_unit_loss')
    similarity = lexical_cosine(baseline, output, korean)
    if ((similarity is None and lexical_cosine(baseline, baseline, korean) is not None)
            or (similarity is not None and similarity < GATES['minimum_baseline_pairwise_lexical_cosine'])):
        violations.append('lexical_drift')
    return violations


def better(candidate: dict, incumbent: dict) -> bool:
    return bool(candidate['eligible'] and
                (candidate['output_whitespace_units'], candidate['output_characters']) <
                (incumbent['output_whitespace_units'], incumbent['output_characters']))


def line_evidence(cases: list[dict]) -> list[dict]:
    counts = Counter()
    for case in cases:
        counts.update({line.strip() for line in case['baseline'].splitlines() if 4 <= len(line.strip()) <= 140})
    return [{'line': line, 'document_count': count}
            for line, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])) if count >= 2][:60]


def evaluate(cases: list[dict], config: dict, keywords: list[str], directory: Path) -> dict:
    validate_config(config)
    write_once(directory / 'configuration.json', config)
    rows, failures, units, characters = [], 0, 0, 0
    for case in cases:
        output = transform(case['raw'], case['baseline'], config)
        violations = guard(case['baseline'], output, keywords, case['domain'] == 'kr_insurance')
        value = {k: case[k] for k in ('doc_id', 'domain', 'source_sha256', 'text_sha256', 'extraction_status', 'allocation')}
        value.update(gate_violations=violations, output_sha256=save_bytes(directory / 'texts' / (case['doc_id'] + '.txt'), output.encode('utf-8')),
                     metrics=metrics(case['raw'], output, keywords, case['domain'] == 'kr_insurance'))
        write_once(directory / 'documents' / (case['doc_id'] + '.json'), value)
        rows.append(value)
        failures += bool(violations)
        units += len(output.split())
        characters += len(output)
    retention = [r['metrics']['source_keyword_retention'] for r in rows if r['metrics']['source_keyword_retention'] is not None]
    summary = {'configuration_sha256': sha256(canonical(config).encode('utf-8')), 'input_documents': len(rows),
               'eligible': failures == 0 and bool(rows), 'gate_failed_documents': failures,
               'gate_violation_counts': dict(Counter(v for r in rows for v in r['gate_violations'])),
               'extraction_status_counts': dict(Counter(r['extraction_status'] for r in rows)),
               'output_whitespace_units': units, 'output_characters': characters,
               'source_keyword_retention_mean_defined': sum(retention) / len(retention) if retention else None,
               'source_keyword_retention_defined_documents': len(retention),
               'gate_failure_examples': [{'doc_id': r['doc_id'], 'violations': r['gate_violations']} for r in rows if r['gate_violations']][:8],
               'document_result_sha256': {r['doc_id']: sha256((directory / 'documents' / (r['doc_id'] + '.json')).read_bytes()) for r in rows}}
    write_once(directory / 'metrics.json', summary)
    return summary
