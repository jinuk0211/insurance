"""Actual generated-query retrieval and model-selected evidence links.

Inference never receives silver labels. The deterministic gate checks offered
IDs and exact source spans, not legal entailment; silver scoring is separate.
"""
from __future__ import annotations

import json

from .legal import _catalog
from .metrics import rank_passages
from .schemas import STRING, object_schema, rows_schema
from .tasks import (FINDING_FIELDS, GENERATOR_MODEL, PROFILES, SCOPE,
                    _failure, _quote_valid, _rows, validate_config)

EVIDENCE_SCHEMA = rows_schema('validations', {
    'id': STRING,
    'status': {'type': 'string', 'enum': ['supported', 'uncertain', 'not_supported']},
    'reason': STRING,
    'citations': {'type': 'array', 'items': object_schema(
        {'authority_id': STRING, 'quote': STRING})},
})
EVIDENCE_SYSTEM = SCOPE + (
    ' Review each candidate against the full contract and ONLY its retrieved '
    'official-source excerpts. This is model inference, not legal advice or a '
    'human judgment. A burden can be lawful. Do not claim a legal violation. '
    'For every candidate, return one validation with the same id. supported '
    'means a cited excerpt materially supports the stated issue AND its '
    'applicability is established by supplied facts and scope. Explain this '
    'link and qualifications in reason (at most 60 words). Topic overlap is '
    'insufficient. Unknown jurisdiction, missing incorporated terms or '
    'unresolved applicability require uncertain. not_supported means the '
    'provided evidence does not substantively support this issue. Excerpts '
    'are incomplete laws: preserve their scope restrictions and version limits. '
    'Do not apply consumer-credit rules to commercial loans. For supported '
    'results cite at least one offered authority_id with a concise exact quote '
    'from its text, never an invented or outside ID. Otherwise return no '
    'citations. Return only JSON with validations; no omitted or repeated IDs.'
)


def validate_evidence(client, doc_id: str, domain: str, text: str,
                      findings: list[dict], catalog: dict, config: dict) -> dict:
    """Retrieve actual generated queries, then validate without reference labels."""
    config = validate_config(config)
    sources, fingerprint = _catalog(catalog, domain)
    candidates = [{key: row.get(key) for key in FINDING_FIELDS} for row in findings]
    _rows({'output': {'findings': candidates}}, 'findings', FINDING_FIELDS)
    passages = [{'id': row['id'], 'text': '\n'.join(
        [row['title'], row['jurisdiction'], row['text']])} for row in sources]
    by_id = {row['id']: row for row in sources}
    retrieval_config = {key: config[key] for key in ('retriever', 'k1', 'b')}
    retrieved = []
    for finding in candidates:
        ranked = rank_passages(finding['retrieval_query'], passages, retrieval_config)
        retrieved.append({'finding_id': finding['id'], 'query': finding['retrieval_query'],
                          'ranked_ids': ranked, 'authorities': [by_id[key] for key in ranked[:3]]})
    payload = {'doc_id': doc_id, 'domain': domain, 'profile': PROFILES[domain],
               'source': text, 'findings': candidates, 'retrieved': retrieved,
               'catalog_limitations': catalog['limitations']}
    call = client.call(label=f'validate_evidence:{doc_id}', model=getattr(client, 'generator_model', GENERATOR_MODEL),
                       system=EVIDENCE_SYSTEM, prompt=json.dumps(payload, ensure_ascii=False),
                       max_tokens=3200, schema=EVIDENCE_SCHEMA)
    output = call.get('output')
    if not isinstance(output, dict) or set(output) != {'validations'}:
        _failure('Evidence output must contain exactly validations', call)
    rows = output['validations']
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        _failure('Evidence validations must be records', call)
    expected = {row['id']: row for row in candidates}
    if len(rows) != len(expected) or {row.get('id') for row in rows} != set(expected):
        _failure('Evidence validation must cover every finding exactly once', call)
    offered = {row['finding_id']: set(row['ranked_ids'][:3]) for row in retrieved}
    validated = []
    for row in rows:
        if (set(row) != {'id', 'status', 'reason', 'citations'}
                or row['status'] not in ('supported', 'uncertain', 'not_supported')
                or not isinstance(row['reason'], str) or not row['reason'].strip()
                or not isinstance(row['citations'], list)):
            _failure('Malformed evidence validation record', call)
        citations = row['citations']
        if any(not isinstance(cite, dict) or set(cite) != {'authority_id', 'quote'}
               or not all(isinstance(value, str) and value.strip() for value in cite.values())
               for cite in citations):
            _failure('Malformed evidence citation', call)
        if len({cite['authority_id'] for cite in citations}) != len(citations):
            _failure('Repeated evidence citation ID', call)
        valid = all(cite['authority_id'] in offered[row['id']]
                    and _quote_valid(cite['quote'], by_id[cite['authority_id']]['text'])
                    for cite in citations)
        source_valid = _quote_valid(expected[row['id']]['quote'], text)
        withheld = not valid or not source_valid or (row['status'] == 'supported' and not citations)
        validated.append({**row, 'model_status': row['status'],
                          'status': 'uncertain' if withheld else row['status'],
                          'citations': [] if withheld or row['status'] != 'supported' else citations,
                          'proposed_citations': citations,
                          'citation_identity_and_quote_valid': valid,
                          'source_quote_valid': source_valid, 'withheld_by_gate': withheld})
    return {'validations': validated, 'retrieved': retrieved, 'call': call,
            'catalog_sha256': fingerprint, 'source_chars': len(text),
            'model_inference': True, 'human_supervision': False,
            'scope': 'Selected evidence links with ID/span gate; not guaranteed legal validity'}


def evaluate_validated_evidence(validation: dict, judgments: list[dict],
                                legal_reference: dict) -> dict:
    """Score actual selected links against independent, incomplete LLM silver."""
    grades = {row['issue_id']: row['relevance'] for row in legal_reference['queries']}
    eligible = {key for key, values in grades.items() if any(value > 0 for value in values.values())}
    assessed = {row['id']: row for row in judgments}
    rows = validation['validations']
    if len(rows) != len(assessed) or {row['id'] for row in rows} != set(assessed):
        raise ValueError('Final validation and source-assessment IDs differ')
    covered = set()
    links = supported_links = unmatched_findings = 0
    for row in rows:
        if row['status'] != 'supported':
            continue
        judgment = assessed[row['id']]
        matches = judgment['relevant_ref_ids'] if judgment['status'] == 'supported' else []
        if any(key not in grades for key in matches):
            raise ValueError('Source assessment references an unknown issue')
        unmatched_findings += not bool(matches)
        for citation in row['citations']:
            links += 1
            matched = {key for key in matches if grades[key].get(citation['authority_id'], 0) > 0}
            supported_links += bool(matched)
            covered.update(matched)
    return {'selected_authority_coverage': len(covered) / len(eligible) if eligible else None,
            'eligible_reference_count': len(eligible), 'covered_reference_ids': sorted(covered),
            'silver_authority_id_agreement': supported_links / links if links else None,
            'selected_link_count': links, 'silver_matched_link_count': supported_links,
            'unmatched_supported_findings': unmatched_findings,
            'no_eligible_authority': not eligible, 'abstained_all': links == 0,
            'scope': 'Selected authority-ID agreement plus source-supported issue match; not selected-quote entailment or legal precision'}
