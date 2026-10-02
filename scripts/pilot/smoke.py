"""Explicit one-development-document integration probe; never a paper result."""
import argparse
import json
from pathlib import Path

from .client import ModelClient, load_api_key, write_json
from .codex_client import CodexClient
from .evidence import evaluate_validated_evidence, validate_evidence
from .legal import create_legal_reference, evaluate_legal_retrieval
from .runner import load_manifest, source_fingerprint
from .tasks import assess, create_reference, fixed_config, generate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--doc-id', required=True)
    parser.add_argument('--budget-usd', type=float, default=.75)
    parser.add_argument('--provider', choices=('codex', 'anthropic'), default='codex')
    parser.add_argument('--codex-executable', type=Path)
    parser.add_argument('--max-calls', type=int, default=10)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    manifest = load_manifest(root, root / 'research/pilot_v1/data/manifest.json')
    doc = next((row for row in manifest['documents'] if row['doc_id'] == args.doc_id), None)
    if doc is None or doc['split'] != 'dev':
        parser.error('An explicitly selected development document is required')
    # Reuse the original diagnostic ledger; all failed annotation calls stay there.
    directory = root / ('research/pilot_v1/gpt_public_loan_smoke' if args.provider == 'codex'
                        else 'research/pilot_v1/public_loan_smoke')
    identity_path = directory / 'document.json'
    if identity_path.exists() and json.loads(identity_path.read_text(encoding='utf-8')) != doc:
        parser.error('The diagnostic directory belongs to another document')
    write_json(identity_path, doc)
    text = (root / doc['text_path']).read_text(encoding='utf-8')
    if args.provider == 'codex':
        if args.codex_executable is None:
            parser.error('--codex-executable is required for GPT subscription inference')
        client = CodexClient(directory / 'calls', args.codex_executable, max_calls=args.max_calls)
    else:
        client = ModelClient(directory / 'calls', load_api_key(root), args.budget_usd)
    reference = create_reference(client, doc['doc_id'], doc['domain'], text)
    write_json(directory / 'reference.json', reference)
    output = generate(client, doc['doc_id'], doc['domain'], text, fixed_config())
    write_json(directory / 'generation.json', output)
    grade = assess(client, doc['doc_id'], doc['domain'], text, output['findings'], reference)
    write_json(directory / 'assessment.json', grade)
    catalog = json.loads((root / 'research/pilot_v1/legal_sources.json').read_text(encoding='utf-8'))
    authorities = create_legal_reference(client, doc['doc_id'], doc['domain'], text, reference, catalog)
    write_json(directory / 'legal_reference.json', authorities)
    retrieval = evaluate_legal_retrieval(authorities, catalog, doc['domain'], fixed_config())
    validation = validate_evidence(client, doc['doc_id'], doc['domain'], text,
                                   output['findings'], catalog, fixed_config())
    write_json(directory / 'evidence_validation.json', validation)
    final_metrics = evaluate_validated_evidence(validation, grade['judgments'], authorities)
    record = {'doc_id': doc['doc_id'], 'status': 'success', 'purpose': 'development smoke, not final results',
              'source_sha256': source_fingerprint(root), 'source_chars': len(text),
              'annotation_retries': reference['annotation_retries'], 'metrics': grade['metrics'],
              'authority_retrieval': retrieval, 'validated_evidence_metrics': final_metrics,
              'billing': client.usage_summary() if args.provider == 'codex' else
                         {'spent_or_reserved_usd': client.spent_usd},
              'model_provenance': client.provenance() if args.provider == 'codex' else
                                  {'provider': 'anthropic'}}
    write_json(directory / 'smoke_result.json', record)
    print(json.dumps({key: record[key] for key in ('doc_id', 'status', 'annotation_retries',
                                                  'metrics', 'billing')}, indent=2))


if __name__ == '__main__':
    main()
