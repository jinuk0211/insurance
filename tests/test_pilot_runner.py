"""Freeze and document-level experiment invariants."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts.pilot.runner import (
    Pilot,
    digest,
    load_manifest,
    mean_defined,
    resolve_manifest_path,
    source_fingerprint,
)
from scripts.pilot.client import ModelFailure, write_json
from scripts.pilot.tasks import fixed_config


def test_mean_does_not_treat_missing_as_perfect_or_zero():
    assert mean_defined([None, .2, .4]) == pytest.approx(.3)
    assert mean_defined([None]) is None


def test_source_fingerprint_changes_when_evaluator_changes(tmp_path):
    directory = tmp_path / 'scripts/pilot'
    directory.mkdir(parents=True)
    (directory / 'tasks.py').write_text('original', encoding='utf-8')
    before = source_fingerprint(tmp_path)
    (directory / 'tasks.py').write_text('changed', encoding='utf-8')
    assert source_fingerprint(tmp_path) != before


def test_manifest_missing_domain_or_tampered_source_fails(tmp_path):
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps({'documents': []}), encoding='utf-8')
    with pytest.raises(ValueError, match='30'):
        load_manifest(tmp_path, path)


def test_runner_rejects_corrupted_frozen_text_before_client_provenance(tmp_path):
    documents = []
    for index, domain in enumerate(("kr_insurance", "us_loan", "us_card")):
        for offset in range(10):
            number = index * 10 + offset
            relative = f"data/text/doc-{number}.txt"
            text = ("Ordinary contract terms for document " + str(number)
                    if number else "Ordinary clause\x00 with NUL corruption")
            text_path = tmp_path / relative
            text_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.write_text(text, encoding="utf-8")
            documents.append({
                "doc_id": f"{domain}-{number}",
                "domain": domain,
                "split": "dev" if offset < 4 else "test",
                "group_id": f"group:{number}",
                "text_path": relative,
                "text_sha256": hashlib.sha256(
                    text.encode("utf-8")).hexdigest(),
            })
    path = tmp_path / "research/pilot_v1/data/manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"documents": documents}), encoding="utf-8")

    class Client:
        def provenance(self):
            raise AssertionError("model/client provenance must not be touched")

    with pytest.raises(ValueError, match="NUL"):
        Pilot(tmp_path, tmp_path / "run", Client())


def write_valid_manifest(tmp_path, relative="research/pilot_v1/data/manifest_v2.json"):
    documents = []
    for index, domain in enumerate(("kr_insurance", "us_loan", "us_card")):
        for offset in range(10):
            number = index * 10 + offset
            text = f"Ordinary contract terms for valid document {number}."
            text_relative = f"data/text/doc-{number}.txt"
            text_path = tmp_path / text_relative
            text_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.write_text(text, encoding="utf-8")
            documents.append({
                "doc_id": f"{domain}-{number}",
                "domain": domain,
                "split": "dev" if offset < 4 else "test",
                "group_id": f"group:{number}",
                "text_path": text_relative,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            })
    manifest_path = tmp_path / relative
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({"documents": documents}), encoding="utf-8")
    (tmp_path / "research/pilot_v1/legal_sources.json").write_text(
        json.dumps({"sources": []}), encoding="utf-8"
    )
    return manifest_path


def test_pilot_uses_explicit_versioned_manifest_and_records_relative_path(tmp_path):
    write_valid_manifest(tmp_path)
    pilot = Pilot(
        tmp_path,
        tmp_path / "run",
        object(),
        manifest_path="research/pilot_v1/data/manifest_v2.json",
    )
    assert pilot.manifest_path == "research/pilot_v1/data/manifest_v2.json"
    assert pilot.protocol["manifest_path"] == pilot.manifest_path
    assert len(pilot.manifest["documents"]) == 30


@pytest.mark.parametrize("requested", ["../manifest.json", Path("C:/outside/manifest.json")])
def test_manifest_path_cannot_escape_workspace(tmp_path, requested):
    with pytest.raises(ValueError, match="inside workspace"):
        resolve_manifest_path(tmp_path, requested)


def minimal_pilot(tmp_path):
    pilot = Pilot.__new__(Pilot)
    pilot.root = tmp_path
    pilot.run_dir = tmp_path / 'run'
    pilot.protocol = {'test': 'protocol'}
    pilot.catalog = {'sources': []}
    pilot.docs = [{'doc_id': 'd1', 'domain': 'us_card', 'split': 'dev', 'text_sha256': 'hash'},
                  {'doc_id': 't1', 'domain': 'us_card', 'split': 'test', 'text_sha256': 'testhash'}]
    return pilot


def test_test_access_requires_matching_freeze(tmp_path):
    pilot = minimal_pilot(tmp_path)
    with pytest.raises(ValueError, match='freeze'):
        pilot.documents('test')
    write_json(pilot.run_dir / 'test_freeze.json', {'protocol_sha256': 'wrong'})
    with pytest.raises(ValueError, match='freeze'):
        pilot.documents('test')
    write_json(pilot.run_dir / 'test_freeze.json', {'protocol_sha256': digest(pilot.protocol)})
    assert pilot.documents('test')[0]['doc_id'] == 't1'


def test_cannot_resume_development_after_freeze(tmp_path):
    pilot = minimal_pilot(tmp_path)
    write_json(pilot.run_dir / 'test_freeze.json', {})
    with pytest.raises(ValueError, match='locked'):
        pilot.develop()


def test_cached_failure_cannot_become_completed_on_resume(tmp_path):
    pilot = minimal_pilot(tmp_path)
    config = fixed_config()
    row = {**pilot.docs[0], 'config': config, 'protocol_sha256': digest(pilot.protocol),
           'status': 'failure', 'quality': None}
    write_json(pilot.run_dir / 'evaluations' / digest(config) / 'd1.json', row)
    with pytest.raises(ModelFailure, match='failed evaluation'):
        pilot.evaluate(config, 'dev')


@pytest.mark.parametrize("limit", [0, -1, True, 2])
def test_development_probe_limit_must_select_existing_documents(tmp_path, limit):
    pilot = minimal_pilot(tmp_path)
    with pytest.raises(ValueError, match="Development document limit"):
        pilot.evaluate(fixed_config(), "dev", limit)


def test_wrong_cached_identity_is_rejected(tmp_path):
    pilot = minimal_pilot(tmp_path)
    config = fixed_config()
    row = {**pilot.docs[0], 'config': config, 'protocol_sha256': digest(pilot.protocol),
           'status': 'success', 'quality': 1, 'text_sha256': 'tampered'}
    write_json(pilot.run_dir / 'evaluations' / digest(config) / 'd1.json', row)
    with pytest.raises(ValueError, match='identity'):
        pilot.evaluate(config, 'dev')


def test_unfrozen_method_cannot_access_test_even_after_finalization(tmp_path):
    pilot = minimal_pilot(tmp_path)
    write_json(pilot.run_dir / 'test_freeze.json',
               {'protocol_sha256': digest(pilot.protocol), 'methods': {'fixed': fixed_config()}})
    changed = {**fixed_config(), 'instruction': 'new after test'}
    with pytest.raises(ValueError, match='frozen methods'):
        pilot.evaluate(changed, 'test')


def test_stale_reference_identity_is_rejected(tmp_path):
    pilot = minimal_pilot(tmp_path)
    write_json(pilot.run_dir / 'references/d1.json',
               {'doc_id': 'd1', 'text_sha256': 'hash', 'protocol_sha256': 'stale'})
    with pytest.raises(ValueError, match='Cached reference'):
        pilot.reference(pilot.docs[0])


def test_quote_typography_normalization_never_changes_numbers_or_negation():
    from scripts.pilot.tasks import _quote_valid

    assert _quote_valid("Agent's legal counsel", "Agent\u2019s legal counsel")
    assert _quote_valid('"Rate" means', '\u201cRate\u201d means')
    assert not _quote_valid('10.0 percent', '100 percent')
    assert not _quote_valid('shall pay the fee', 'shall not pay the fee')
