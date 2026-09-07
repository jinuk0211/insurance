#!/usr/bin/env python3
"""
scripts/search_precedents.py

판례/분쟁사례 키워드 검색 스크립트.
legal-validator 에이전트가 Bash 도구로 호출한다.

사용법:
    python scripts/search_precedents.py "고지의무 위반 보험금"
    python scripts/search_precedents.py "면책조항" --vuln-id INS-03 --top-k 3
"""

import json
import sys
import argparse
from pathlib import Path


def search(query: str, vuln_id: str = "", top_k: int = 5) -> list[dict]:
    """판례 + 분쟁사례 키워드 검색."""

    results = []

    # 판례 검색
    precedents_path = Path("data/precedents.json")
    if precedents_path.exists():
        precedents = json.loads(precedents_path.read_text(encoding="utf-8"))
        query_tokens = set(query.split())

        for p in precedents:
            text = f"{p.get('case_number','')} {p.get('summary','')} {' '.join(p.get('keywords',[]))}"

            # vuln_id 필터
            if vuln_id and vuln_id not in p.get("vuln_tags", []):
                continue

            # 키워드 매칭 점수
            text_tokens = set(text.split())
            overlap = len(query_tokens & text_tokens)
            if overlap == 0:
                # 부분 문자열 검색 fallback
                score = sum(1 for token in query_tokens if token in text) / max(len(query_tokens), 1)
            else:
                score = overlap / max(len(query_tokens), 1)

            if score > 0:
                results.append({
                    "type": "precedent",
                    "case_number": p.get("case_number", ""),
                    "court": p.get("court", ""),
                    "date": p.get("date", ""),
                    "summary": p.get("summary", ""),
                    "vuln_tags": p.get("vuln_tags", []),
                    "relevance_score": round(min(score, 1.0), 3),
                    "source": "data/precedents.json"
                })

    # 분쟁사례 검색
    disputes_path = Path("data/dispute_cases.json")
    if disputes_path.exists():
        disputes = json.loads(disputes_path.read_text(encoding="utf-8"))
        query_tokens = set(query.split())

        for d in disputes:
            text = f"{d.get('case_id','')} {d.get('summary','')} {d.get('outcome','')}"

            if vuln_id and vuln_id not in d.get("vuln_tags", []):
                continue

            score = sum(1 for token in query_tokens if token in text) / max(len(query_tokens), 1)

            if score > 0:
                results.append({
                    "type": "dispute",
                    "case_id": d.get("case_id", ""),
                    "institution": d.get("institution", ""),
                    "summary": d.get("summary", ""),
                    "outcome": d.get("outcome", ""),
                    "vuln_tags": d.get("vuln_tags", []),
                    "relevance_score": round(min(score, 1.0), 3),
                    "source": "data/dispute_cases.json"
                })

    # 점수 순 정렬
    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    return results[:top_k]


def main():
    parser = argparse.ArgumentParser(description="판례/분쟁사례 검색")
    parser.add_argument("query", help="검색 쿼리")
    parser.add_argument("--vuln-id", default="", help="취약점 ID 필터 (예: INS-02)")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    results = search(args.query, args.vuln_id, args.top_k)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
