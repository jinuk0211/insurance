#!/usr/bin/env python3
"""
scripts/parse_pdf.py

약관 PDF → 조항 단위 JSON 변환 스크립트.
Claude Code의 contract-parser 에이전트가 Bash 도구로 이 스크립트를 호출한다.

사용법:
    python scripts/parse_pdf.py 약관.pdf
    python scripts/parse_pdf.py 약관.pdf --output workspace/findings_ledger.json
    python scripts/parse_pdf.py 약관.pdf --insurance-type 암보험
"""

import re
import json
import sys
import hashlib
import argparse
from pathlib import Path


def extract_text_from_pdf(pdf_path: str) -> str:
    """PDF에서 텍스트 추출. pymupdf 우선, 없으면 pdfminer 시도."""
    try:
        import fitz  # pymupdf
        doc = fitz.open(pdf_path)
        pages = []
        for page in doc:
            pages.append(page.get_text("text"))
        doc.close()
        return "\n".join(pages)
    except ImportError:
        pass

    try:
        from pdfminer.high_level import extract_text
        return extract_text(pdf_path)
    except ImportError:
        pass

    print("[오류] PDF 파싱 라이브러리 없음. 설치: pip install pymupdf", file=sys.stderr)
    sys.exit(1)


def chunk_by_article(text: str, source_name: str = "") -> list[dict]:
    """조항(제N조) 단위로 텍스트 분할."""

    # 조항 헤더 패턴
    ARTICLE_PATTERN = re.compile(
        r"(제\s*\d+\s*조(?:의\s*\d+)?\s*(?:[\(\（][^\)\）]{1,30}[\)\）])?)"
    )

    # 키워드 목록
    KEYWORDS = {
        "보험금": r"보험금",
        "면책": r"면책|지급하지\s*아니",
        "고지의무": r"고지의무|알릴\s*의무",
        "해지": r"해지|취소|무효",
        "보험료": r"보험료",
        "담보": r"담보|저당|근저당",
        "금리": r"금리|이자율|이율",
        "중도상환": r"중도상환|조기상환",
        "기한이익": r"기한의?\s*이익",
        "개인정보": r"개인정보|신용정보",
    }

    def extract_keywords(t: str) -> list[str]:
        return [kw for kw, pat in KEYWORDS.items() if re.search(pat, t)]

    def make_clause_id(article_num: str, idx: int) -> str:
        raw = f"{source_name}_{article_num}_{idx}"
        h = hashlib.md5(raw.encode()).hexdigest()[:6]
        safe = re.sub(r"[^a-zA-Z0-9]", "_", article_num)
        return f"ART_{safe}_{h}"

    # 조항 헤더 위치 찾기
    splits = []
    for m in ARTICLE_PATTERN.finditer(text):
        splits.append((m.start(), m.group(0).strip()))

    if not splits:
        # 조항 구분 못하면 전체를 하나로
        return [{
            "clause_id": make_clause_id("FULL", 0),
            "article_number": "FULL",
            "article_title": "",
            "raw_text": text[:3000],
            "normalized_text": re.sub(r"\s+", " ", text[:3000]).strip(),
            "keywords": extract_keywords(text),
            "vulnerability_flags": []
        }]

    clauses = []
    for i, (pos, header) in enumerate(splits):
        # 조항 번호/제목 파싱
        num_match = re.search(r"제\s*(\d+)\s*조(?:의\s*(\d+))?", header)
        if num_match:
            num = num_match.group(1)
            sub = num_match.group(2)
            article_number = f"{num}-{sub}" if sub else num
        else:
            article_number = f"UNKNOWN_{i}"

        title_match = re.search(r"[\(\（]([^\)\）]{1,30})[\)\）]", header)
        article_title = title_match.group(1).strip() if title_match else ""

        # 텍스트 범위
        start = pos
        end = splits[i + 1][0] if i + 1 < len(splits) else len(text)
        raw = text[start:end].strip()

        if not raw:
            continue

        # 너무 긴 조항은 잘라냄 (800토큰 ≈ 1600자)
        if len(raw) > 1600:
            raw = raw[:1600]

        clauses.append({
            "clause_id": make_clause_id(article_number, i),
            "article_number": article_number,
            "article_title": article_title,
            "raw_text": raw,
            "normalized_text": re.sub(r"\s+", " ", raw).strip(),
            "keywords": extract_keywords(raw),
            "vulnerability_flags": []
        })

    return clauses


def main():
    parser = argparse.ArgumentParser(description="약관 PDF → 조항 JSON 변환")
    parser.add_argument("pdf_path", help="약관 PDF 경로")
    parser.add_argument("--output", default="", help="출력 JSON 경로 (기본: stdout)")
    parser.add_argument("--session-id", default="", help="세션 ID")
    parser.add_argument("--insurance-type", default="", help="암보험, 종신보험 등")
    parser.add_argument("--product-type", default="insurance", help="insurance | loan")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"[오류] 파일 없음: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[parse_pdf] 파싱 시작: {pdf_path.name}", file=sys.stderr)

    # 텍스트 추출
    text = extract_text_from_pdf(str(pdf_path))
    print(f"[parse_pdf] 텍스트 추출 완료: {len(text)}자", file=sys.stderr)

    # 조항 분할
    clauses = chunk_by_article(text, source_name=pdf_path.stem)
    print(f"[parse_pdf] 조항 파싱 완료: {len(clauses)}개", file=sys.stderr)

    # 메타데이터
    import uuid
    session_id = args.session_id or str(uuid.uuid4())[:8]

    result = {
        "session_id": session_id,
        "product_type": args.product_type,
        "insurance_type": args.insurance_type or pdf_path.parent.name,
        "source_pdf": str(pdf_path),
        "total_clauses": len(clauses),
        "clauses": clauses
    }

    # 출력
    output_json = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_json, encoding="utf-8")
        print(f"[parse_pdf] 저장 완료: {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
