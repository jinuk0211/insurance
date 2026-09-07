import hashlib
import json
from pathlib import Path

import pytest

from scripts.pilot import reextract


def _text(label: str) -> str:
    return " ".join(f"{label}_term_{index}" for index in range(600))


def make_parent_fixture(tmp_path: Path) -> Path:
    documents = []
    for domain_index, domain in enumerate(("kr_insurance", "us_loan", "us_card")):
        for offset in range(10):
            number = domain_index * 10 + offset
            doc_id = f"{domain}-{offset + 1:02d}-parent{number:02d}"
            text = _text(f"{domain}_{number}")
            text_relative = f"research/pilot_v1/data_v2/text/{doc_id}.txt"
            text_path = tmp_path / text_relative
            text_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.write_text(text, encoding="utf-8")
            row = {
                "doc_id": doc_id,
                "domain": domain,
                "split": "dev" if offset < 4 else "test",
                "group_id": f"group:{domain}:{offset}",
                "source_path": f"data/{domain}/{doc_id}.source",
                "source_sha256": "",
                "source_url": None,
                "text_path": text_relative,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "char_count": len(text),
                "extraction": "existing",
            }
            source_path = tmp_path / row["source_path"]
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_bytes = f"source bytes {doc_id}".encode("utf-8")
            source_path.write_bytes(source_bytes)
            row["source_sha256"] = hashlib.sha256(source_bytes).hexdigest()
            if domain == "kr_insurance":
                original_relative = f"data/{domain}/{doc_id}.pdf"
                original_path = tmp_path / original_relative
                original_bytes = f"original pdf bytes {doc_id}".encode("utf-8")
                original_path.write_bytes(original_bytes)
                row["original_pdf_path"] = original_relative
                row["original_pdf_sha256"] = hashlib.sha256(original_bytes).hexdigest()
                row["category"] = "fixture"
            documents.append(row)
    manifest = {
        "schema_version": 1,
        "seed": 42,
        "documents": documents,
        "selection_counts": {"kr_insurance": {"selected": 10}, "us_loan": {"selected": 10},
                             "us_card": {"selected": 10}},
        "selection_protocol": {"scope": "fixture parent"},
    }
    parent = tmp_path / "research/pilot_v1/data_v2/manifest.json"
    parent.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return parent


def test_reextract_preserves_lineage_and_non_kr_bytes(tmp_path, monkeypatch):
    parent = make_parent_fixture(tmp_path)
    parent_bytes = parent.read_bytes()

    def fake_read_text(candidate):
        return _text(f"reextracted_{candidate.source_path.stem}")

    monkeypatch.setattr(reextract.prepare, "read_text", fake_read_text)
    result = reextract.reextract(tmp_path)
    output = tmp_path / "research/pilot_v1/data_v3/manifest.json"
    saved = json.loads(output.read_text(encoding="utf-8"))

    assert result == saved
    assert parent.read_bytes() == parent_bytes
    assert saved["parent_manifest_path"] == "research/pilot_v1/data_v2/manifest.json"
    assert saved["parent_manifest_sha256"] == hashlib.sha256(parent_bytes).hexdigest()
    assert saved["reextraction"]["pypdf_version"] == reextract.prepare.PYPDF_VERSION
    assert saved["parent_selection_counts"]["kr_insurance"]["selected"] == 10
    assert len(saved["documents"]) == 30

    old = {row["doc_id"]: row for row in json.loads(parent.read_text())["documents"]}
    assert [row["parent_doc_id"] for row in saved["documents"]] == list(old)
    for row in saved["documents"]:
        assert row["parent_doc_id"] in old
        parent_row = old[row["parent_doc_id"]]
        assert row["group_id"] == parent_row["group_id"]
        assert row["split"] == parent_row["split"]
        if row["domain"] == "kr_insurance":
            assert row["source_path"] == parent_row["original_pdf_path"]
            assert row["source_sha256"] == parent_row["original_pdf_sha256"]
            assert row["extraction"] == "pypdf_full_document"
            assert row["doc_id"] != row["parent_doc_id"]
        else:
            assert row["doc_id"] == row["parent_doc_id"]
            assert row["source_path"] == parent_row["source_path"]
            assert row["source_sha256"] == parent_row["source_sha256"]
            assert (tmp_path / row["text_path"]).read_bytes() == (
                tmp_path / parent_row["text_path"]
            ).read_bytes()


def test_reextract_is_idempotent_and_does_not_overwrite_v3(tmp_path, monkeypatch):
    make_parent_fixture(tmp_path)
    monkeypatch.setattr(
        reextract.prepare,
        "read_text",
        lambda candidate: _text(f"reextracted_{candidate.source_path.stem}"),
    )
    first = reextract.reextract(tmp_path)
    output = tmp_path / "research/pilot_v1/data_v3/manifest.json"
    before = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in output.parent.rglob("*")
        if path.is_file()
    }
    second = reextract.reextract(tmp_path)
    after = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in output.parent.rglob("*")
        if path.is_file()
    }
    assert first == second
    assert before == after


def test_reextract_rejects_parent_tamper_before_output(tmp_path):
    parent = make_parent_fixture(tmp_path)
    row = json.loads(parent.read_text(encoding="utf-8"))["documents"][0]
    (tmp_path / row["text_path"]).write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        reextract.reextract(tmp_path)
    assert not (tmp_path / "research/pilot_v1/data_v3/manifest.json").exists()


def test_reextract_rejects_near_duplicate_before_any_write(tmp_path, monkeypatch):
    make_parent_fixture(tmp_path)
    monkeypatch.setattr(reextract.prepare, "read_text", lambda candidate: _text("same"))
    with pytest.raises(ValueError, match="near_duplicate"):
        reextract.reextract(tmp_path)
    assert not (tmp_path / "research/pilot_v1/data_v3/manifest.json").exists()


def test_reextract_rejects_extraction_quality_failure_before_any_write(tmp_path, monkeypatch):
    make_parent_fixture(tmp_path)
    monkeypatch.setattr(
        reextract.prepare,
        "read_text",
        lambda candidate: "+-|-+" * 1000,
    )
    with pytest.raises(ValueError, match="quality"):
        reextract.reextract(tmp_path)
    assert not (tmp_path / "research/pilot_v1/data_v3/manifest.json").exists()


@pytest.mark.parametrize("input_path,output_path", [
    ("../manifest.json", "research/pilot_v1/data_v3/manifest.json"),
    ("research/pilot_v1/data_v2/manifest.json", "../data_v3/manifest.json"),
])
def test_reextract_rejects_paths_outside_workspace(tmp_path, input_path, output_path):
    with pytest.raises(ValueError, match="inside workspace"):
        reextract.reextract(tmp_path, input_path, output_path)


@pytest.mark.parametrize("bad_id", ["../escape", r"..\escape", ".."])
def test_reextract_rejects_unsafe_parent_ids_without_mutating_output(tmp_path, bad_id):
    parent = make_parent_fixture(tmp_path)
    payload = json.loads(parent.read_text(encoding="utf-8"))
    payload["documents"][0]["doc_id"] = bad_id
    parent.write_text(json.dumps(payload), encoding="utf-8")
    sentinel = tmp_path / "research/pilot_v1/data_v3/manifest.json"
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text("sentinel", encoding="utf-8")

    with pytest.raises(ValueError, match="unsafe document ID"):
        reextract.reextract(tmp_path)

    assert sentinel.read_text(encoding="utf-8") == "sentinel"
