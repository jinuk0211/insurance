"""Freeze a small issuer-disjoint pilot; never overwrite an existing dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader, __version__ as PYPDF_VERSION
from pypdf.errors import PdfReadError

ROOT = Path(__file__).resolve().parents[2]
DOMAINS = ("kr_insurance", "us_loan", "us_card")
BORDER_CHARS = frozenset("|+-=_│─┌┐└┘├┤┬┴┼━═║╔╗╚╝╠╣╦╩╬")
BORDER_SHARE_LIMIT = 0.50
ALNUM_SHARE_LIMIT = 0.35
SOURCE_QUALITY_POLICY = (
    "Reject NUL-containing text, blank/no-alphanumeric text, and text where "
    f"at least {BORDER_SHARE_LIMIT:.0%} of non-whitespace characters are "
    f"table-border characters while fewer than {ALNUM_SHARE_LIMIT:.0%} are "
    "alphanumeric. This is an extraction-corruption screen, not a semantic "
    "completeness guarantee."
)


@dataclass(frozen=True)
class Candidate:
    domain: str
    group_id: str
    source_path: Path
    source_url: str | None = None
    category: str | None = None
    original_pdf: Path | None = None


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def canonical_json(value: object) -> str:
    """Serialize JSON deterministically without Python bool/int coercion."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_group(name: str) -> str:
    return re.sub(r"[^\w]", "", unicodedata.normalize("NFKC", name).casefold())


def validate_source_text(text: str) -> None:
    """Reject obvious extraction corruption without judging document meaning.

    The thresholds intentionally target empty output and border-dominated table
    dumps such as a PDF whose extracted text is mostly +|- characters.
    Passing this screen does not establish that the source is complete.
    """
    if not isinstance(text, str):
        raise ValueError("source text must be a string")
    if "\x00" in text:
        raise ValueError("source text contains NUL control corruption")
    non_whitespace = [char for char in text if not char.isspace()]
    if not non_whitespace or not any(char.isalnum() for char in non_whitespace):
        raise ValueError("source text is empty or has no alphanumeric content")
    border_share = (
        sum(char in BORDER_CHARS for char in non_whitespace) / len(non_whitespace)
    )
    alnum_share = (
        sum(char.isalnum() for char in non_whitespace) / len(non_whitespace)
    )
    if border_share >= BORDER_SHARE_LIMIT and alnum_share < ALNUM_SHARE_LIMIT:
        raise ValueError(
            "source text is border-dominated low-content extraction "
            f"(border_share={border_share:.1%}, alnum_share={alnum_share:.1%})"
        )


def clean_extracted_text(text: str) -> str:
    """Drop the extractor's duplicate JSON appendix, not substantive clauses."""
    text = text.split("[ 전체 표 JSON 구조 ]", 1)[0]
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    return "\n".join(
        line.rstrip() for line in lines if not re.fullmatch(r"[=━]{10,}", line.strip())
    ).strip()


def read_text(candidate: Candidate) -> str:
    if candidate.source_path.suffix.lower() == ".pdf":
        reader = PdfReader(candidate.source_path)
        pages = [page.extract_text() or "" for page in reader.pages]
        if not pages or any(not page.strip() for page in pages):
            raise ValueError("PDF has an unextractable page; OCR was not performed")
        return clean_extracted_text("\n\n".join(pages))
    return clean_extracted_text(candidate.source_path.read_text(encoding="utf-8-sig"))


def shingles(text: str) -> set[tuple[str, ...]]:
    words = unicodedata.normalize("NFKC", text).casefold().split()
    return {tuple(words[index:index + 5]) for index in range(len(words) - 4)}


def jaccard(first: set[tuple[str, ...]], second: set[tuple[str, ...]]) -> float:
    union = len(first | second)
    return len(first & second) / union if union else 1.0


def discover(root: Path) -> dict[str, list[Candidate]]:
    candidates: dict[str, list[Candidate]] = {domain: [] for domain in DOMAINS}
    for category in ("암보험", "정기보험", "종신보험", "질병보험"):
        for path in sorted((root / "data" / category / "extracted").glob("*.txt")):
            insurer = path.name.partition("_")[0]
            original = path.parent.parent / f"{path.stem}.pdf"
            candidates["kr_insurance"].append(Candidate(
                "kr_insurance", "insurer:" + canonical_group(insurer), path,
                category=category, original_pdf=original if original.is_file() else None,
            ))
    loan_root = root / "data/loan_data/us_loan_corpus"
    for line in (loan_root / "_manifest.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        path = loan_root / row["out"]
        if not str(row.get("cik", "")).isdigit() or not path.is_file():
            raise ValueError(f"Loan manifest lacks CIK or existing source: {row['out']}")
        candidates["us_loan"].append(Candidate(
            "us_loan", f"cik:{int(row['cik']):010d}", path, row.get("url"),
        ))
    card_root = root / "data/2025_Q2"
    for path in sorted(card_root.rglob("*.pdf")):
        issuer = path.relative_to(card_root).parts[0]
        candidates["us_card"].append(Candidate(
            "us_card", "issuer:" + canonical_group(issuer), path,
        ))
    return candidates


def select_domain(
    root: Path, candidates: list[Candidate], data_dir: str, seed: int,
) -> tuple[list[dict], dict[str, str], dict]:
    """Seed-shuffle groups and paths, then admit the first 10 usable groups."""
    groups: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        groups[candidate.group_id].append(candidate)
    rng = random.Random(seed)
    group_order = sorted(groups)
    rng.shuffle(group_order)
    selected: list[dict] = []
    texts: dict[str, str] = {}
    selected_shingles: list[set[tuple[str, ...]]] = []
    source_hashes: set[str] = set()
    exclusions: Counter[str] = Counter()
    examined = 0
    for group_id in group_order:
        ordered = sorted(groups[group_id], key=lambda item: item.source_path.as_posix())
        rng.shuffle(ordered)
        for candidate in ordered:
            examined += 1
            source_hash = sha256(candidate.source_path.read_bytes())
            if source_hash in source_hashes:
                exclusions["exact_source_duplicate"] += 1
                continue
            try:
                text = read_text(candidate)
            except (PdfReadError, ValueError, UnicodeError, OSError) as error:
                exclusions[f"extraction_failure:{type(error).__name__}"] += 1
                continue
            try:
                validate_source_text(text)
            except ValueError as error:
                exclusions[f"source_quality:{error}"] += 1
                continue
            if not 2_000 <= len(text) <= 50_000:
                exclusions["outside_2000_50000_characters"] += 1
                continue
            fingerprint = shingles(text)
            if any(jaccard(fingerprint, previous) >= 0.8 for previous in selected_shingles):
                exclusions["near_duplicate_jaccard_ge_0.8"] += 1
                continue
            text_hash = sha256(text.encode("utf-8"))
            doc_id = f"{candidate.domain}-{len(selected) + 1:02d}-{text_hash[:10]}"
            text_path = (Path(data_dir) / "text" / f"{doc_id}.txt").as_posix()
            document = {
                "doc_id": doc_id, "domain": candidate.domain,
                "split": "dev" if len(selected) < 4 else "test",
                "group_id": group_id,
                "source_path": candidate.source_path.relative_to(root).as_posix(),
                "source_sha256": source_hash, "source_url": candidate.source_url,
                "text_path": text_path, "text_sha256": text_hash,
                "char_count": len(text), "category": candidate.category,
                "extraction": "pypdf_full_document" if candidate.source_path.suffix.lower() == ".pdf"
                else "existing_full_extraction_minus_duplicate_table_json",
            }
            if candidate.original_pdf:
                document["original_pdf_path"] = candidate.original_pdf.relative_to(root).as_posix()
                document["original_pdf_sha256"] = sha256(candidate.original_pdf.read_bytes())
            selected.append(document)
            texts[text_path] = text
            selected_shingles.append(fingerprint)
            source_hashes.add(source_hash)
            break
        if len(selected) == 10:
            break
    if len(selected) != 10:
        raise ValueError(f"Need 10 distinct usable groups; selected {len(selected)}: {dict(exclusions)}")
    return selected, texts, {
        "candidate_files": len(candidates), "candidate_groups": len(groups),
        "examined_candidates": examined, "selected": len(selected),
        "unexamined_candidates": len(candidates) - examined,
        "exclusions_among_examined": dict(sorted(exclusions.items())),
    }


def within_root(root: Path, relative: str) -> Path:
    path = root / relative
    if Path(relative).is_absolute() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Output paths must be relative and inside workspace")
    return path


def write_frozen(root: Path, output: str, manifest: dict, texts: dict[str, str]) -> None:
    """Preflight every artifact before creating anything; existing bytes are immutable."""
    destination = within_root(root, output)
    paths = {relative: within_root(root, relative) for relative in texts}
    exists = destination.exists()
    if exists and canonical_json(
        json.loads(destination.read_text(encoding="utf-8"))
    ) != canonical_json(manifest):
        raise RuntimeError("Frozen manifest differs; choose a new versioned output directory")
    for relative, path in paths.items():
        if path.exists() and path.read_bytes() != texts[relative].encode("utf-8"):
            raise RuntimeError(f"Frozen text differs: {relative}")
        if exists and not path.exists():
            raise RuntimeError(f"Frozen text is missing: {relative}")
    if exists:
        return
    for relative, path in paths.items():
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as handle:
                handle.write(texts[relative].encode("utf-8"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def prepare(root: Path, output: str, seed: int = 42) -> dict:
    within_root(root, output)
    data_dir = Path(output).parent.as_posix()
    candidates = discover(root)
    documents: list[dict] = []
    texts: dict[str, str] = {}
    counts = {}
    for domain in DOMAINS:
        selected, domain_texts, counts[domain] = select_domain(
            root, candidates[domain], data_dir, seed,
        )
        documents.extend(selected)
        texts.update(domain_texts)
    manifest = {
        "schema_version": 1, "seed": seed, "documents": documents,
        "selection_protocol": {
            "algorithm": "sorted groups and paths, Python Random(seed) shuffle; first usable per group",
            "documents_per_domain": 10, "dev_per_domain": 4, "test_per_domain": 6,
            "min_characters": 2_000, "max_characters": 50_000,
            "no_content_truncation": True, "no_outcome_based_selection": True,
            "near_duplicates": "Within each domain, all selected pairs must have NFKC casefold whitespace-token 5-word shingle Jaccard < 0.8; no full-corpus clustering is claimed.",
            "grouping": "KR insurer filename prefix; US card issuer folder; US loan SEC registrant CIK (not independently verified corporate-family or borrower identity). One selected document per group.",
            "scope": "Length-bounded pilot only, not a representative full-corpus benchmark. Existing KR extracted-text pool only. All pages of card PDFs require extractable text; OCR is not performed.",
            "cleaning": "Normalize newlines and trailing whitespace; remove decorative separator lines and duplicate whole-table JSON appendix; keep substantive text and earlier table text.",
            "source_quality": SOURCE_QUALITY_POLICY,
            "source_urls": "Document URLs only where stored in original loan manifest; unavailable URLs are null, never inferred.",
            "pdf_extractor": f"pypdf {PYPDF_VERSION}",
        },
        "selection_counts": counts,
    }
    write_frozen(root, output, manifest, texts)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="research/pilot_v1/data/manifest.json")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    manifest = prepare(ROOT, args.output, args.seed)
    print(json.dumps({"output": args.output, "counts": manifest["selection_counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
