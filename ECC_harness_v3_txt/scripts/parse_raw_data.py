#!/usr/bin/env python3
"""
scripts/parse_raw_data.py

판결문 TXT + 분쟁사례 TXT → JSON 변환 (최초 1회 실행).
kfinlegal-harness 없이 ecc 폴더 안에서 바로 실행 가능.

사용법:
    python scripts/parse_raw_data.py
    python scripts/parse_raw_data.py --precedents-dir data/raw/precedents
    python scripts/parse_raw_data.py --disputes-dir data/raw/disputes
"""

import re
import json
import hashlib
import argparse
from pathlib import Path


# ── 판결문 파싱 ──────────────────────────────────────────

CASE_NUM_PATTERN = re.compile(
    r"(대법원|서울고등법원|서울고법|부산고등법원|대구고등법원|광주고등법원"
    r"|수원고등법원|서울중앙지방법원|서울중앙지법|지방법원)"
    r"\s*(\d{4})\s*(다|고|나|카|마|아|구|도|합|노)\s*(\d+)"
)

DATE_PATTERN = re.compile(
    r"(\d{4})\s*[년.]\s*(\d{1,2})\s*[월.]\s*(\d{1,2})\s*[일.]?\s*(?:선고|판결|결정)"
)

VULN_KEYWORDS = {
    "INS-01": ["보험금 지급", "보험금 거절", "지급 제한", "보험금 청구"],
    "INS-02": ["고지의무", "알릴 의무", "고지의무 위반", "계약 해지", "중요한 사항"],
    "INS-03": ["면책", "면책조항", "보상하지 않", "지급하지 않"],
    "INS-04": ["계약 전 알릴", "질문표", "청약서"],
    "INS-05": ["보험료", "보험료 인상", "갱신", "보험료 변경"],
    "LOAN-01": ["변동금리", "기준금리", "금리 변동"],
    "LOAN-02": ["가산금리", "금리 산정", "금리 조정"],
    "LOAN-03": ["중도상환", "조기상환", "중도상환수수료"],
    "LOAN-04": ["기한이익", "기한의 이익", "기한이익 상실"],
    "LOAN-05": ["담보권", "저당권", "근저당", "경매"],
    "LOAN-06": ["개인정보", "신용정보", "마케팅"],
}

LEGAL_KEYWORDS = [
    "약관", "보험계약", "상법", "보험업법", "약관규제법", "금융소비자보호법",
    "고지의무", "면책", "보험금", "담보", "금리", "이자", "무효", "취소", "해지",
]


def parse_precedent(txt_path: Path) -> dict | None:
    try:
        text = txt_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    # 사건번호
    m = CASE_NUM_PATTERN.search(text) or CASE_NUM_PATTERN.search(txt_path.stem.replace("_", " "))
    if m:
        case_number = m.group(0).strip()
        court = m.group(1)
    else:
        case_number = f"UNKNOWN_{txt_path.stem}"
        court = "미상"

    # 날짜
    dm = DATE_PATTERN.search(text)
    date = f"{dm.group(1)}-{dm.group(2).zfill(2)}-{dm.group(3).zfill(2)}" if dm else ""

    # 주문 추출
    ruling = ""
    ruling_m = re.search(r"주\s*문\s*\n(.*?)(?=이\s*유|$)", text, re.DOTALL)
    if ruling_m:
        ruling = re.sub(r"\s+", " ", ruling_m.group(1)).strip()[:200]

    # 이유 요약 (앞 300자)
    reasoning = ""
    reason_m = re.search(r"이\s*유\s*\n(.*?)$", text, re.DOTALL)
    if reason_m:
        reasoning = re.sub(r"\s+", " ", reason_m.group(1)).strip()[:300]

    # 취약점 태그
    vuln_tags = [tag for tag, kws in VULN_KEYWORDS.items() if any(kw in text for kw in kws)]
    keywords = [kw for kw in LEGAL_KEYWORDS if kw in text]

    uid = hashlib.md5(case_number.encode()).hexdigest()[:10]

    return {
        "id": uid,
        "case_number": case_number,
        "court": court,
        "date": date,
        "case_type": "보험" if any(k in text[:500] for k in ["보험금", "보험계약"]) else "대출",
        "ruling": ruling,
        "summary": reasoning,
        "full_text": text[:5000],
        "vuln_tags": vuln_tags,
        "keywords": keywords,
        "source_file": txt_path.name,
    }


# ── 분쟁사례 파싱 ────────────────────────────────────────

DISPUTE_CASE_PATTERN = re.compile(r"(\d{4}[-\s]*\d+)")
OUTCOME_KEYWORDS = ["소비자 승", "소비자 일부 승", "소비자 패", "조정", "기각"]


def parse_dispute(txt_path: Path) -> dict | None:
    try:
        text = txt_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    # case_id: 파일명 또는 본문에서 추출
    case_id = txt_path.stem

    # 기관
    institution = ""
    if "금융분쟁조정위원회" in text or "FIDO" in txt_path.stem:
        institution = "금융분쟁조정위원회"
    elif "금융감독원" in text or "FSS" in txt_path.stem:
        institution = "금융감독원"

    # 결과
    outcome = ""
    for kw in OUTCOME_KEYWORDS:
        if kw in text:
            outcome = kw
            break

    # 요약 (앞 400자)
    summary = re.sub(r"\s+", " ", text).strip()[:400]

    # 취약점 태그
    vuln_tags = [tag for tag, kws in VULN_KEYWORDS.items() if any(kw in text for kw in kws)]

    uid = hashlib.md5(case_id.encode()).hexdigest()[:10]

    return {
        "id": uid,
        "case_id": case_id,
        "institution": institution,
        "summary": summary,
        "outcome": outcome,
        "vuln_tags": vuln_tags,
        "source_file": txt_path.name,
    }


# ── 메인 ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="판결문/분쟁사례 TXT → JSON")
    parser.add_argument("--precedents-dir", default="data/raw/precedents")
    parser.add_argument("--disputes-dir", default="data/raw/disputes")
    args = parser.parse_args()

    # 판결문
    prec_dir = Path(args.precedents_dir)
    if prec_dir.exists():
        txt_files = list(prec_dir.glob("**/*.txt"))
        print(f"[판례] TXT {len(txt_files)}건 파싱 중...")
        parsed = [r for f in txt_files if (r := parse_precedent(f)) is not None]
        print(f"[판례] {len(parsed)}건 완료")
        Path("data/precedents.json").write_text(
            json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[판례] data/precedents.json 저장 완료")
    else:
        print(f"[판례] 디렉터리 없음: {prec_dir} — 건너뜀")

    # 분쟁사례
    disp_dir = Path(args.disputes_dir)
    if disp_dir.exists():
        txt_files = list(disp_dir.glob("**/*.txt"))
        print(f"[분쟁] TXT {len(txt_files)}건 파싱 중...")
        parsed = [r for f in txt_files if (r := parse_dispute(f)) is not None]
        print(f"[분쟁] {len(parsed)}건 완료")
        Path("data/dispute_cases.json").write_text(
            json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[분쟁] data/dispute_cases.json 저장 완료")
    else:
        print(f"[분쟁] 디렉터리 없음: {disp_dir} — 건너뜀")

    print("\n완료! 이제 claude 실행 후 /analyze 사용 가능.")


if __name__ == "__main__":
    main()
