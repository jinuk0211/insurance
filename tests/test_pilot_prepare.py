"""Behavioral tests for the frozen, group-disjoint pilot corpus."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.pilot import prepare


def make_candidate(root: Path, number: int, group: str | None = None):
    path = root / f"source-{number}.txt"
    text = " ".join(f"term{number}_{index}" for index in range(300))
    path.write_text(text, encoding="utf-8")
    return prepare.Candidate("us_loan", group or f"cik:{number}", path)


def test_seeded_selection_has_ten_unique_groups_and_four_six_split(tmp_path):
    candidates = [make_candidate(tmp_path, n) for n in range(15)]
    selected, texts, counts = prepare.select_domain(
        tmp_path, candidates, "research/data", seed=42
    )
    repeated, repeated_texts, repeated_counts = prepare.select_domain(
        tmp_path, list(reversed(candidates)), "research/data", seed=42
    )
    assert selected == repeated
    assert texts == repeated_texts
    assert counts == repeated_counts
    assert len(selected) == len({doc["group_id"] for doc in selected}) == 10
    assert [doc["split"] for doc in selected].count("dev") == 4
    assert [doc["split"] for doc in selected].count("test") == 6
    assert all(doc["char_count"] == len(texts[doc["text_path"]]) for doc in selected)
    assert all(len(doc["source_sha256"]) == 64 for doc in selected)


def test_near_duplicate_normalizes_whitespace_and_case():
    first = " ".join(f"word{n}" for n in range(100))
    duplicate = first.upper().replace(" ", " \n\t ") + " extra"
    assert prepare.jaccard(prepare.shingles(first), prepare.shingles(duplicate)) > 0.8


def test_duplicate_groups_and_identical_content_cannot_supply_ten(tmp_path):
    candidates = [make_candidate(tmp_path, n, "same-group") for n in range(11)]
    with pytest.raises(ValueError, match="10 distinct"):
        prepare.select_domain(tmp_path, candidates, "research/data", seed=42)


@pytest.mark.parametrize("size", [1999, 50001])
def test_length_exclusion_never_truncates(tmp_path, size):
    candidates = [make_candidate(tmp_path, n) for n in range(10)]
    candidates[0].source_path.write_text("a" * size, encoding="utf-8")
    with pytest.raises(ValueError, match="10 distinct"):
        prepare.select_domain(tmp_path, candidates, "research/data", seed=42)
    assert len(candidates[0].source_path.read_text(encoding="utf-8")) == size


def test_duplicate_table_json_tail_is_not_second_copy_of_document():
    assert prepare.clean_extracted_text("Clause.\n[ 전체 표 JSON 구조 ]\n[]") == "Clause."
    assert prepare.clean_extracted_text("A\r\nB") == "A\nB"


def test_source_quality_accepts_prose_and_modest_table():
    prepare.validate_source_text(
        "The borrower shall make each payment on the date stated in this agreement. "
        "Failure to pay may trigger the notice and cure provisions."
    )
    prepare.validate_source_text(
        "Field | Value\nAPR | 12.4 percent\nGrace period | 25 days\n"
        "The table is followed by ordinary explanatory text."
    )


@pytest.mark.parametrize("text", ["", " \n\t", "----------------\n||||||||"])
def test_source_quality_rejects_empty_or_degenerate_text(text):
    with pytest.raises(ValueError, match="source text"):
        prepare.validate_source_text(text)


def test_source_quality_rejects_nul_control_corruption():
    with pytest.raises(ValueError, match="NUL"):
        prepare.validate_source_text("A valid-looking clause\x00 with corruption.")


def test_source_quality_rejects_border_dominated_low_content_extraction():
    extracted = ("+-+-|-+-+|-+-+|-+-+|-+-+\n" * 200
                 + "Contract terms appear only once.")
    with pytest.raises(ValueError, match="border-dominated"):
        prepare.validate_source_text(extracted)


def test_selection_rejects_quality_failure_instead_of_admitting_it(tmp_path):
    candidates = [make_candidate(tmp_path, n) for n in range(9)]
    bad = tmp_path / "source-bad.txt"
    bad.write_text(("+-+-|-+-+|-+-+\n" * 300), encoding="utf-8")
    candidates.append(prepare.Candidate("us_loan", "cik:bad", bad))
    with pytest.raises(ValueError, match="10 distinct"):
        prepare.select_domain(tmp_path, candidates, "research/data", seed=42)


def test_frozen_write_is_idempotent_and_rejects_mutation_before_writes(tmp_path):
    manifest = {"schema_version": 1, "documents": []}
    text_path = "research/data/text/doc.txt"
    output = "research/data/manifest.json"
    prepare.write_frozen(tmp_path, output, manifest, {text_path: "original"})
    before = (tmp_path / output).stat().st_mtime_ns
    prepare.write_frozen(tmp_path, output, manifest, {text_path: "original"})
    assert (tmp_path / output).stat().st_mtime_ns == before
    with pytest.raises(RuntimeError, match="manifest differs"):
        prepare.write_frozen(tmp_path, output, {"changed": True}, {text_path: "new"})
    assert (tmp_path / text_path).read_text() == "original"
    assert json.loads((tmp_path / output).read_text()) == manifest


def test_frozen_manifest_comparison_is_type_sensitive(tmp_path):
    output = "out/manifest.json"
    prepare.write_frozen(tmp_path, output, {"metadata": {"enabled": True}}, {})
    with pytest.raises(RuntimeError, match="manifest differs"):
        prepare.write_frozen(tmp_path, output, {"metadata": {"enabled": 1}}, {})


def test_changed_text_is_rejected_even_when_manifest_matches(tmp_path):
    prepare.write_frozen(tmp_path, "out/manifest.json", {}, {"out/doc.txt": "first"})
    with pytest.raises(RuntimeError, match="text differs"):
        prepare.write_frozen(tmp_path, "out/manifest.json", {}, {"out/doc.txt": "second"})
    assert (tmp_path / "out/doc.txt").read_text() == "first"


def test_output_cannot_escape_workspace(tmp_path):
    with pytest.raises(ValueError, match="inside workspace"):
        prepare.write_frozen(tmp_path, "../escape.json", {}, {})


def test_cross_group_content_duplicates_are_rejected(tmp_path):
    candidates = [make_candidate(tmp_path, n) for n in range(10)]
    candidates[1].source_path.write_bytes(candidates[0].source_path.read_bytes())
    with pytest.raises(ValueError, match="exact_source_duplicate"):
        prepare.select_domain(tmp_path, candidates, "research/data", seed=42)


def test_cross_group_near_duplicates_are_rejected(tmp_path):
    candidates = [make_candidate(tmp_path, n) for n in range(10)]
    original = candidates[0].source_path.read_text(encoding="utf-8")
    candidates[1].source_path.write_text(original.upper() + " extra", encoding="utf-8")
    with pytest.raises(ValueError, match="near_duplicate"):
        prepare.select_domain(tmp_path, candidates, "research/data", seed=42)


def test_pdf_extraction_keeps_all_pages_and_rejects_empty_page(tmp_path, monkeypatch):
    candidate = prepare.Candidate("us_card", "issuer:one", tmp_path / "test.pdf")
    pages = [SimpleNamespace(extract_text=lambda: "first page"),
             SimpleNamespace(extract_text=lambda: "last page")]
    monkeypatch.setattr(prepare, "PdfReader", lambda path: SimpleNamespace(pages=pages))
    assert prepare.read_text(candidate) == "first page\n\nlast page"
    pages.append(SimpleNamespace(extract_text=lambda: ""))
    with pytest.raises(ValueError, match="unextractable page"):
        prepare.read_text(candidate)


def test_prepare_emits_thirty_documents_and_preserves_source_urls(tmp_path, monkeypatch):
    candidates = {}
    for index, domain in enumerate(prepare.DOMAINS):
        candidates[domain] = []
        for number in range(10):
            item = make_candidate(tmp_path, index * 10 + number)
            candidates[domain].append(prepare.Candidate(
                domain, item.group_id, item.source_path, "https://example.test/source"
            ))
    monkeypatch.setattr(prepare, "discover", lambda root: candidates)
    manifest = prepare.prepare(tmp_path, "research/data/manifest.json")
    assert len(manifest["documents"]) == 30
    assert all(doc["source_url"] == "https://example.test/source"
               for doc in manifest["documents"])
    assert len(list((tmp_path / "research/data/text").glob("*.txt"))) == 30
    assert prepare.prepare(tmp_path, "research/data/manifest.json") == manifest


def test_discover_uses_actual_data_prefix_and_normalizes_issuer_groups(tmp_path):
    kr = tmp_path / "data/암보험/extracted/한화생명_product.txt"
    loan = tmp_path / "data/loan_data/us_loan_corpus/loan.txt"
    card = tmp_path / "data/2025_Q2/Bank, Inc/card.pdf"
    for path in (kr, loan, card):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"placeholder")
    original = kr.parent.parent / "한화생명_product.pdf"
    original.write_bytes(b"pdf")
    manifest = loan.parent / "_manifest.jsonl"
    manifest.write_text(json.dumps({"out": "loan.txt", "cik": "123",
                                    "url": "https://example.test/loan"}), encoding="utf-8")
    found = prepare.discover(tmp_path)
    assert found["kr_insurance"][0].original_pdf == original
    assert found["us_loan"][0].group_id == "cik:0000000123"
    assert found["us_loan"][0].source_url == "https://example.test/loan"
    assert found["us_card"][0].group_id == "issuer:bankinc"
    manifest.write_text(json.dumps({"out": "missing.txt", "cik": "123"}))
    with pytest.raises(ValueError, match="existing source"):
        prepare.discover(tmp_path)


def test_existing_manifest_with_missing_text_is_not_silently_repaired(tmp_path):
    output = tmp_path / "manifest.json"
    output.write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="text is missing"):
        prepare.write_frozen(tmp_path, "manifest.json", {}, {"missing.txt": "text"})
    assert not (tmp_path / "missing.txt").exists()
