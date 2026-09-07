"""
e2_input_format_us.py

E2 (US): CFPB 신용카드 약관 PDF를 어떤 형식으로 LLM에 넘기느냐에 따른
         취약점 탐지 정확도 비교

비교 형식:
  pdf_multimodal     : PDF base64 직접 멀티모달 입력
  pdf_text_raw       : pdfplumber 추출 raw TXT
  pdf_text_fewshot   : raw TXT + few-shot 예시
  ours_no_preprocess : 우리 프롬프트+persona, 전처리 없음
  ours               : 전처리 TXT + 우리 프롬프트 + persona (전체)
  ours_no_profile    : ours에서 persona 제거 (ablation)

취약점 taxonomy (미국 신용카드):
  CC-01: 숨겨진 / 불명확한 수수료
  CC-02: 금리 변동 불리 조건 (APR escalation)
  CC-03: 청구 방식 소비자 불리 (minimum payment trap 등)
  CC-04: 계약 변경·해지 소비자 불리
  CC-05: 강제 중재 / 집단소송 금지
  UNCATEGORIZED: 그 외 소비자 불이익

사용법:
  python e2_input_format_us.py --pdf path/to/agreement.pdf
  python e2_input_format_us.py --pdf path/to/agreement.pdf --gt CC-01,CC-02,CC-04,CC-05
"""

import json, re, time, base64, argparse, sys
from pathlib import Path
import urllib.request

sys.path.insert(0, str(Path(__file__).parent))
from e1_preprocessing_us import extract_pdf, strategy_ours, strategy_raw, VULN_KEYWORDS

# ── CLI ───────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--pdf",  type=str, required=False, help="PDF 파일 경로")
parser.add_argument("--gt",   type=str, default="CC-01,CC-02,CC-04,CC-05",
                    help="정답 taxonomy (쉼표 구분)")
parser.add_argument("--out",  type=str, default="results/e2_us.json")
args = parser.parse_args()

OUT = Path(args.out)
OUT.parent.mkdir(parents=True, exist_ok=True)

GT = set(args.gt.split(","))

# ── 텍스트 준비 ───────────────────────────────────────────────
SAMPLE_TEXT = """
CREDIT CARD AGREEMENT AND DISCLOSURE STATEMENT
Effective Date: January 1, 2024

INTEREST RATES AND INTEREST CHARGES
Annual Percentage Rate (APR) for Purchases: 24.99% - 29.99% Variable
APR for Cash Advances: 29.99% Variable
Penalty APR: 29.99% - This APR applies if you make a late payment or your payment is returned.
  How Long Will the Penalty APR Apply: If your APRs are increased for this reason, the Penalty APR
  will apply until you make six consecutive minimum payments when due.

FEES
Annual Fee: $95
Foreign Transaction: 3% of each transaction in U.S. dollars
Balance Transfer: Either $5 or 3% of the amount of each transfer, whichever is greater.
Cash Advance: Either $10 or 5% of the amount of each cash advance, whichever is greater.
Late Payment: Up to $40
Over-the-Credit-Limit: None
Return Payment: Up to $40

HOW WE WILL CALCULATE YOUR BALANCE:
We use a method called "average daily balance" (including new purchases).

MINIMUM PAYMENT:
We will calculate your minimum payment as 2% of your outstanding balance or $25, whichever is greater.
If you make only the minimum payment each period, you will pay more in interest.

CHANGE IN TERMS:
We may change the APR, fees, and other terms of this Agreement at any time.
We will give you at least 45 days advance notice of significant changes.
If you do not opt out within the stated period, you accept the changes.
Opting out means you must close your account and pay the remaining balance.

ARBITRATION AGREEMENT:
Any dispute, claim, or controversy arising out of or relating to this Agreement shall be settled
by binding arbitration. YOU GIVE UP YOUR RIGHT TO PARTICIPATE IN A CLASS ACTION.
This arbitration agreement applies to all disputes including those about fees and interest charges.

ACCOUNT CANCELLATION:
We may cancel your account at any time, for any reason, with or without notice.
Upon cancellation, your entire outstanding balance becomes immediately due and payable.

DEFAULT:
You will be in default if you fail to make a minimum payment, exceed your credit limit,
or if we believe you are unable or unwilling to pay your debts.
"""

if args.pdf:
    pdf_path = Path(args.pdf)
    raw_txt = extract_pdf(pdf_path)
    pdf_b64 = base64.standard_b64encode(pdf_path.read_bytes()).decode("utf-8")
    has_pdf = True
else:
    raw_txt = SAMPLE_TEXT
    pdf_b64 = None
    has_pdf = False
    print("[정보] PDF 없음 → 샘플 텍스트로 실행")

preprocessed_txt = strategy_ours(raw_txt)
MAX_TXT = 12000

print(f"정답 taxonomy: {sorted(GT)}")
print(f"raw: {len(raw_txt.split()):,}tok | preprocessed: {len(preprocessed_txt.split()):,}tok")

# ── 사용자 프로필 ─────────────────────────────────────────────
USER_PROFILE = {
    "age": 45,
    "occupation": "salaried employee",
    "financial_status": "middle income",
    "risk_flags": ["carry_balance", "occasional_late_payment"],
}

TAXONOMY_DESC = """\
Vulnerability Types (US Credit Card):
- CC-01: Hidden or unclear fees (annual fee, foreign transaction, etc.)
- CC-02: Unfavorable APR escalation (penalty rate, variable rate risk)
- CC-03: Unfavorable billing methods (average daily balance, minimum payment trap)
- CC-04: Unfair contract change / account cancellation terms
- CC-05: Mandatory arbitration / class action waiver
- UNCATEGORIZED: Other consumer disadvantages"""

FEW_SHOT = """\
[Example 1]
Clause: "Penalty APR of 29.99% will apply if you make a late payment and will remain until you make 6 consecutive on-time payments."
→ [{"taxonomy": "CC-02", "triggered_by": "Penalty APR of 29.99% will apply if you make a late payment"}]

[Example 2]
Clause: "Any dispute shall be settled by binding arbitration. YOU GIVE UP YOUR RIGHT TO PARTICIPATE IN A CLASS ACTION."
→ [{"taxonomy": "CC-05", "triggered_by": "binding arbitration... YOU GIVE UP YOUR RIGHT TO PARTICIPATE IN A CLASS ACTION"}]

[Example 3]
Clause: "We may change the APR, fees, and other terms of this Agreement at any time."
→ [{"taxonomy": "CC-04", "triggered_by": "We may change the APR, fees, and other terms of this Agreement at any time"}]"""

BASE_INSTRUCTION = f"""\
{TAXONOMY_DESC}

Detect ALL consumer-unfavorable vulnerabilities.
Reply ONLY with a JSON array:
[{{"taxonomy": "CC-XX or UNCATEGORIZED", "triggered_by": "verbatim clause text"}}]
If no vulnerability: []"""

# ── Claude API 호출 ───────────────────────────────────────────
def call_claude(messages: list) -> list[dict]:
    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("    [오류] ANTHROPIC_API_KEY 환경변수 미설정")
        return []
    payload = json.dumps({
        "model":      "claude-haiku-4-5-20251001",
        "max_tokens": 2000,
        "messages":   messages,
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type":      "application/json",
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
            text = data["content"][0]["text"]
            m = re.search(r'\[.*?\]', text, re.DOTALL)
            if m:
                return json.loads(m.group())
    except Exception as e:
        print(f"    API 오류: {e}")
    return []

# ── 형식별 메시지 빌더 ────────────────────────────────────────
def build_messages(fmt: str) -> list:
    if fmt == "pdf_multimodal":
        if not has_pdf:
            return []  # PDF 없으면 스킵
        return [{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_b64,
                    }
                },
                {
                    "type": "text",
                    "text": f"Detect all consumer vulnerabilities in this credit card agreement PDF.\n{BASE_INSTRUCTION}"
                }
            ]
        }]

    elif fmt == "pdf_text_raw":
        return [{
            "role": "user",
            "content": (
                f"[Credit Card Agreement (PDF extracted text)]\n"
                f"{raw_txt[:MAX_TXT]}\n\n"
                f"{BASE_INSTRUCTION}"
            )
        }]

    elif fmt == "pdf_text_fewshot":
        return [{
            "role": "user",
            "content": (
                f"{FEW_SHOT}\n\n"
                f"[Credit Card Agreement]\n"
                f"{raw_txt[:MAX_TXT]}\n\n"
                f"{BASE_INSTRUCTION}"
            )
        }]

    elif fmt == "ours_no_preprocess":
        profile_str = (
            f"Age {USER_PROFILE['age']}, {USER_PROFILE['occupation']}, "
            f"{USER_PROFILE['financial_status']}, "
            f"risk flags: {', '.join(USER_PROFILE['risk_flags'])}"
        )
        return [{
            "role": "user",
            "content": (
                f"You are a US consumer financial contract vulnerability detection expert.\n"
                f"{FEW_SHOT}\n\n"
                f"[User Profile]\n{profile_str}\n\n"
                f"[Credit Card Agreement (raw, no preprocessing)]\n"
                f"{raw_txt[:MAX_TXT]}\n\n"
                f"Detect all consumer vulnerabilities.\n{BASE_INSTRUCTION}"
            )
        }]

    elif fmt == "ours":
        profile_str = (
            f"Age {USER_PROFILE['age']}, {USER_PROFILE['occupation']}, "
            f"{USER_PROFILE['financial_status']}, "
            f"risk flags: {', '.join(USER_PROFILE['risk_flags'])}"
        )
        return [{
            "role": "user",
            "content": (
                f"You are a US consumer financial contract vulnerability detection expert.\n"
                f"{FEW_SHOT}\n\n"
                f"[User Profile]\n{profile_str}\n\n"
                f"[Credit Card Agreement (preprocessed)]\n"
                f"{preprocessed_txt[:MAX_TXT]}\n\n"
                f"Detect all consumer vulnerabilities.\n{BASE_INSTRUCTION}"
            )
        }]

    elif fmt == "ours_no_profile":
        return [{
            "role": "user",
            "content": (
                f"You are a US consumer financial contract vulnerability detection expert.\n"
                f"{FEW_SHOT}\n\n"
                f"[Credit Card Agreement (preprocessed)]\n"
                f"{preprocessed_txt[:MAX_TXT]}\n\n"
                f"Detect all consumer vulnerabilities.\n{BASE_INSTRUCTION}"
            )
        }]

    return []

# ── 지표 계산 ─────────────────────────────────────────────────
def calc_metrics(detected: list[dict], gt: set[str]) -> dict:
    pred = {d.get("taxonomy", "") for d in detected if d.get("taxonomy")}
    tp   = len(pred & gt)
    fp   = len(pred - gt)
    fn   = len(gt - pred)
    p    = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1   = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return {
        "precision":       round(p, 4),
        "recall":          round(r, 4),
        "f1":              round(f1, 4),
        "n_detected":      len(detected),
        "pred_taxonomies": sorted(pred),
        "tp": tp, "fp": fp, "fn": fn,
    }

# ── 실험 실행 ─────────────────────────────────────────────────
FORMATS = [
    "pdf_multimodal",
    "pdf_text_raw",
    "pdf_text_fewshot",
    "ours_no_preprocess",
    "ours",
    "ours_no_profile",
]

# PDF 없으면 multimodal 스킵
if not has_pdf:
    FORMATS = [f for f in FORMATS if f != "pdf_multimodal"]

print(f"\nE2 실험 (US): {len(FORMATS)}개 형식")
summary = {}

for fmt in FORMATS:
    print(f"\n  [{fmt}]")
    messages = build_messages(fmt)
    if not messages:
        print(f"    → 스킵 (PDF 없음)")
        continue

    detected = call_claude(messages)
    metrics  = calc_metrics(detected, GT)
    summary[fmt] = {**metrics, "detected": detected}

    print(f"    탐지 {metrics['n_detected']}건 → "
          f"P={metrics['precision']:.4f} R={metrics['recall']:.4f} F1={metrics['f1']:.4f}")
    print(f"    pred: {metrics['pred_taxonomies']}")
    time.sleep(2)

output = {
    "experiment":    "E2_input_format_US",
    "source":        args.pdf or "sample_text",
    "gt_taxonomies": sorted(GT),
    "user_profile":  USER_PROFILE,
    "summary":       summary,
}
OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

print("\n" + "=" * 65)
print("E2 결과 요약 (US)")
print("=" * 65)
print(f"{'형식':<22} {'Prec':>7} {'Recall':>7} {'F1':>7} {'탐지':>5}")
print("-" * 50)
for fmt, v in summary.items():
    print(f"{fmt:<22} {v['precision']:>7.4f} {v['recall']:>7.4f} "
          f"{v['f1']:>7.4f} {v['n_detected']:>5}")
print(f"\n[완료] 저장: {OUT}")
