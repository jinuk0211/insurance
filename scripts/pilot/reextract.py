"""Create a versioned, source-preserving manifest with verified KR re-extraction."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from . import prepare
from .runner import load_manifest

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = Path("research/pilot_v1/data_v2/manifest.json")
DEFAULT_OUTPUT = Path("research/pilot_v1/data_v3/manifest.json")


def _resolve_inside(root: Path, requested: Path | str) -> tuple[Path, str]:
    root = root.resolve()
    value = Path(requested)
    resolved = (value if value.is_absolute() else root / value).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("Path must stay inside workspace")
    return resolved, resolved.relative_to(root).as_posix()


def _safe_doc_id(doc_id: str) -> str:
    if not isinstance(doc_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", doc_id):
        raise ValueError(f"unsafe document ID for output path: {doc_id!r}")
    return doc_id


def _text_path(output_relative: str, doc_id: str) -> str:
    doc_id = _safe_doc_id(doc_id)
    return (Path(output_relative).parent / "text" / f"{doc_id}.txt").as_posix()


def _validate_text(doc_id: str, text: str) -> None:
    try:
        prepare.validate_source_text(text)
    except ValueError as error:
        raise ValueError(f"source quality failure for {doc_id}: {error}") from error
    if not 2_000 <= len(text) <= 50_000:
        raise ValueError(
            f"source length failure for {doc_id}: {len(text)} characters"
        )


def _new_kr_doc(parent: dict, root: Path, output_relative: str) -> tuple[dict, str]:
    parent_doc_id = _safe_doc_id(parent["doc_id"])
    original_relative = parent.get("original_pdf_path")
    original_sha = parent.get("original_pdf_sha256")
    if not isinstance(original_relative, str) or not isinstance(original_sha, str):
        raise ValueError(f"KR document lacks verified original PDF: {parent_doc_id}")
    original_path, _ = _resolve_inside(root, original_relative)
    source_bytes = original_path.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != original_sha:
        raise ValueError(f"Original PDF hash mismatch: {parent_doc_id}")
    candidate = prepare.Candidate(
        parent["domain"],
        parent["group_id"],
        original_path,
        parent.get("source_url"),
        parent.get("category"),
    )
    text = prepare.read_text(candidate)
    _validate_text(parent_doc_id, text)
    text_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    pieces = parent_doc_id.split("-", 2)
    if len(pieces) != 3 or pieces[0] != parent["domain"]:
        raise ValueError(f"Unexpected parent document ID: {parent_doc_id}")
    doc_id = f"{parent['domain']}-{pieces[1]}-{text_sha[:10]}"
    document = {
        **parent,
        "doc_id": doc_id,
        "parent_doc_id": parent_doc_id,
        "source_path": original_relative,
        "source_sha256": source_sha,
        "text_path": _text_path(output_relative, doc_id),
        "text_sha256": text_sha,
        "char_count": len(text),
        "extraction": "pypdf_full_document",
        "original_pdf_path": original_relative,
        "original_pdf_sha256": source_sha,
    }
    return document, text


def _copy_non_kr_doc(parent: dict, root: Path, output_relative: str) -> tuple[dict, str]:
    parent_doc_id = _safe_doc_id(parent["doc_id"])
    parent_text_relative = parent.get("text_path")
    if not isinstance(parent_text_relative, str):
        raise ValueError(f"Document lacks text path: {parent_doc_id}")
    parent_text_path, _ = _resolve_inside(root, parent_text_relative)
    text_bytes = parent_text_path.read_bytes()
    try:
        text = text_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"Text is not valid UTF-8: {parent_doc_id}") from error
    _validate_text(parent_doc_id, text)
    if text.encode("utf-8") != text_bytes:
        raise ValueError(f"Text bytes cannot be preserved: {parent_doc_id}")
    document = {
        **parent,
        "parent_doc_id": parent_doc_id,
        "text_path": _text_path(output_relative, parent_doc_id),
    }
    return document, text


def _check_domain_duplicates(rows: list[tuple[dict, str]]) -> None:
    previous: list[tuple[str, set[tuple[str, ...]]]] = []
    for document, text in rows:
        fingerprint = prepare.shingles(text)
        for previous_id, previous_fingerprint in previous:
            score = prepare.jaccard(fingerprint, previous_fingerprint)
            if score >= 0.8:
                raise ValueError(
                    f"near_duplicate in {document['domain']}: "
                    f"{previous_id} and {document['doc_id']} "
                    f"(jaccard={score:.3f})"
                )
        previous.append((document["doc_id"], fingerprint))


def reextract(
    root: Path,
    input_manifest: Path | str = DEFAULT_INPUT,
    output_manifest: Path | str = DEFAULT_OUTPUT,
) -> dict:
    """Re-extract KR originals and copy other text, writing only after all checks."""
    root = root.resolve()
    input_path, input_relative = _resolve_inside(root, input_manifest)
    output_path, output_relative = _resolve_inside(root, output_manifest)
    if input_path == output_path:
        raise ValueError("Input and output manifests must differ")
    parent_bytes = input_path.read_bytes()
    parent = load_manifest(root, input_path)
    documents: list[dict] = []
    texts: dict[str, str] = {}
    by_domain: dict[str, list[tuple[dict, str]]] = {domain: [] for domain in prepare.DOMAINS}
    for source_document in parent["documents"]:
        _safe_doc_id(source_document["doc_id"])
        if source_document["domain"] == "kr_insurance":
            document, text = _new_kr_doc(source_document, root, output_relative)
        else:
            document, text = _copy_non_kr_doc(source_document, root, output_relative)
        documents.append(document)
        texts[document["text_path"]] = text
        by_domain[document["domain"]].append((document, text))
    for domain, rows in by_domain.items():
        if len(rows) != 10:
            raise ValueError(f"Re-extraction changed {domain} document count")
        _check_domain_duplicates(rows)
    manifest = {
        "schema_version": 2,
        "documents": documents,
        "parent_manifest_path": input_relative,
        "parent_manifest_sha256": hashlib.sha256(parent_bytes).hexdigest(),
        "parent_selection_counts": parent.get("selection_counts"),
        "reextraction": {
            "method": (
                "KR source_path/original_pdf_path re-extracted with "
                "prepare.read_text and pypdf; US loan/card text bytes copied "
                "unchanged. No resampling, outcomes, OCR, or fallback."
            ),
            "pypdf_version": prepare.PYPDF_VERSION,
            "parent_manifest_path": input_relative,
            "parent_manifest_sha256": hashlib.sha256(parent_bytes).hexdigest(),
            "inherited_selection_counts": parent.get("selection_counts"),
        },
    }
    prepare.write_frozen(root, output_relative, manifest, texts)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-manifest", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-manifest", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = reextract(ROOT, args.input_manifest, args.output_manifest)
    print(json.dumps({
        "output": args.output_manifest.as_posix(),
        "documents": len(result["documents"]),
        "parent_manifest_path": result["parent_manifest_path"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
