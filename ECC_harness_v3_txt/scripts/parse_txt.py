#!/usr/bin/env python3
"""
scripts/parse_txt.py

보험 상품요약서 TXT → 조항 단위 JSON 변환.
제N조 패턴이 없는 상품요약서 형식 전용.

지원 헤더 패턴:
  ◆ 보험금 지급사유 및 지급제한사항
  1. 상품의 특이사항
  3-1. 상품의 구성
   (1) 계약 전 알릴 의무

사용법:
    python scripts/parse_txt.py 약관.txt
    python scripts/parse_txt.py 약관.txt --output workspace/findings_ledger.json
"""

import re
import json
import hashlib
import argparse
import uuid
from pathlib import Path

# ── 키워드 / 취약점 관련 섹션 ─────────────────────────

KEYWORDS = {
    "보험금":   r"보험금",
    "면책":     r"면책|지급하지\s*아니|지급하지\s*않",
    "고지의무": r"고지의무|알릴\s*의무",
    "해지":     r"해지|취소|무효",
    "보험료":   r"보험료",
    "개시일":   r"보장개시일|암보장개시일",
    "제한":     r"제한|부지급|지급제한",
}

VULN_SECTION_KEYWORDS = [
    "지급제한", "알릴 의무", "고지의무", "면책", "무효", "사기",
    "부지급", "해지", "해약", "갱신", "보험료 납입", "보장개시",
    "계약 전", "보험금 지급사유",
]

# 헤더 패턴 (우선순위 순)
HEADER_PATTERNS = [
    (re.compile(r"^◆\s+(.+)$", re.MULTILINE),                        "section"),
    (re.compile(r"^ \((\d+)\)\s+(.{2,50})$", re.MULTILINE),          "subsection"),  # iM라이프
    (re.compile(r"^\((\d+)\)\s+(.{2,50})$", re.MULTILINE),           "subsection"),
    (re.compile(r"^(\d+-\d+)\.\s+(.{2,50})$", re.MULTILINE),         "subsection"),  # 3-1.
    (re.compile(r"^(\d+)\.\s+([가-힣A-Za-z].{2,40})$", re.MULTILINE),"section"),
]


def is_vuln_section(title: str) -> bool:
    return any(kw in title for kw in VULN_SECTION_KEYWORDS)


def extract_keywords(text: str) -> list[str]:
    return [kw for kw, pat in KEYWORDS.items() if re.search(pat, text)]


def make_clause_id(title: str, idx: int, source: str = "") -> str:
    raw = f"{source}_{title}_{idx}"
    h = hashlib.md5(raw.encode()).hexdigest()[:6]
    safe = re.sub(r"[^a-zA-Z0-9]", "_", title[:20])
    return f"SUM_{safe}_{h}"


def chunk_summary_doc(text: str, source_name: str = "") -> list[dict]:
    """상품요약서 텍스트 → 조항 단위 리스트."""
    # 모든 헤더 위치 수집
    splits = []
    for pat, stype in HEADER_PATTERNS:
        for m in pat.finditer(text):
            groups = [g for g in m.groups() if g]
            title = groups[-1].strip() if groups else ""
            if not title:
                continue
            if stype == "section":
                splits.append((m.start(), title, stype))
            elif is_vuln_section(title):
                splits.append((m.start(), title, stype))

    if not splits:
        return []

    # 위치 순 정렬 + 중복 제거
    splits.sort(key=lambda x: x[0])
    seen_pos: set[int] = set()
    deduped = []
    for s in splits:
        if s[0] not in seen_pos:
            seen_pos.add(s[0])
            deduped.append(s)

    clauses = []
    for i, (pos, title, stype) in enumerate(deduped):
        end = deduped[i + 1][0] if i + 1 < len(deduped) else len(text)
        raw = text[pos:end].strip()

        if len(raw) < 30:
            continue
        if len(raw) > 1600:
            raw = raw[:1600]

        kws = extract_keywords(raw)

        # 섹션이면서 키워드도 없고 취약점 관련도 아니면 제외
        if stype == "section" and not kws and not is_vuln_section(title):
            continue

        clauses.append({
            "clause_id": make_clause_id(title, i, source_name),
            "article_number": str(i + 1),
            "article_title": title,
            "raw_text": raw,
            "normalized_text": re.sub(r"\s+", " ", raw).strip(),
            "keywords": kws,
            "vulnerability_flags": [],
            "doc_type": "summary",
        })

    return clauses


def main():
    parser = argparse.ArgumentParser(description="보험 상품요약서 TXT → 조항 JSON")
    parser.add_argument("txt_path", help="TXT 파일 경로")
    parser.add_argument("--output", default="", help="출력 JSON 경로 (기본: stdout)")
    parser.add_argument("--session-id", default="", help="세션 ID")
    parser.add_argument("--product-type", default="insurance", help="insurance | loan")
    parser.add_argument("--insurance-type", default="", help="암보험, 종신보험 등")
    args = parser.parse_args()

    txt_path = Path(args.txt_path)
    if not txt_path.exists():
        print(f"[오류] 파일 없음: {txt_path}", flush=True)
        raise SystemExit(1)

    text = txt_path.read_text(encoding="utf-8", errors="replace")
    print(f"[parse_txt] 텍스트 읽기 완료: {len(text)}자", flush=True)

    clauses = chunk_summary_doc(text, source_name=txt_path.stem)
    print(f"[parse_txt] 조항 파싱 완료: {len(clauses)}개", flush=True)

    session_id = args.session_id or str(uuid.uuid4())[:8]

    result = {
        "session_id": session_id,
        "product_type": args.product_type,
        "insurance_type": args.insurance_type or txt_path.parent.name,
        "source_txt": str(txt_path),
        "doc_format": "product_summary",
        "total_clauses": len(clauses),
        "clauses": clauses,
    }

    output_json = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_json, encoding="utf-8")
        print(f"[parse_txt] 저장 완료: {args.output}", flush=True)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
