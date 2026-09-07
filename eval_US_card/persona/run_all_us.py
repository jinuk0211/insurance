"""
run_all_us.py  (Windows compatible)
3개 신용카드 약관 PDF x 3개 페르소나 전체 파이프라인 실행
"""

import sys, json, time, re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
WS         = SCRIPT_DIR / "workspace_us"
WS.mkdir(exist_ok=True)

# ── PDF 경로 설정 ─────────────────────────────────────────────
# 스크립트와 같은 폴더에 PDF가 있으면 자동 인식
# 아니면 아래에 절대경로 직접 입력:
#   예) Path(r"C:\Users\tgc04\Desktop\insurance\파일명.pdf")

PDF_FILES = {
    "MidFirst_Rewards_CreditCard":
        SCRIPT_DIR / "Rewards_Credit_Card_Cardholder_Agreement.pdf-256498.pdf",
    "APGFCU_Visa_Disclosure":
        SCRIPT_DIR / "APPLICATION AND SOLICITATION DISCLOSURE 3-21-22.pdf-256994.pdf",
    "APGFCU_Visa_Agreement":
        SCRIPT_DIR / "Visa-NewCreditCardAgreement_VD-VIS-DIS.pdf-256467.pdf",
}

# ── 디버그: 현재 스크립트 위치와 파일 탐색 결과 출력 ────────────
print(f"스크립트 위치: {SCRIPT_DIR}")
print(f"폴더 내 PDF 목록:")
for p in sorted(SCRIPT_DIR.glob("*.pdf")):
    print(f"  {p.name}")
print()

# ── PDF → TXT 추출 ───────────────────────────────────────────
def pdf_to_txt(pdf_path: Path, out_path: Path) -> str:
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pip install pdfplumber")
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    noise = [
        r"^\s*page\s+\d+\s*(of\s+\d+)?\s*$",
        r"^revision\s+\d{2}/\d{4}$",
        r"^member\s+fdic$",
        r"^equal\s+housing\s+lender$",
        r"^[=\-_]{4,}$",
    ]
    lines = [l.strip() for l in text.splitlines()
             if l.strip() and not any(re.match(p, l.strip(), re.IGNORECASE) for p in noise)]
    clean = "\n".join(lines)
    out_path.write_text(clean, encoding="utf-8")
    return clean

sys.path.insert(0, str(SCRIPT_DIR))
from us_vulnerability_spotter import run_spotter
from us_legal_validator       import run_validator
from us_severity_classifier   import run_classifier

PERSONAS = [
    {"id":"P01","age":45,"occupation":"salaried employee",
     "financial_status":"middle income","risk_flags":["carry_balance"]},
    {"id":"P02","age":28,"occupation":"gig worker",
     "financial_status":"low income",
     "risk_flags":["irregular_income","low_income","late_payment_history"]},
    {"id":"P03","age":67,"occupation":"retired",
     "financial_status":"fixed income",
     "risk_flags":["elderly","carry_balance","credit_risk"]},
]

# ── PDF 로드 ─────────────────────────────────────────────────
print("PDF → TXT 변환 중...")
TXT_FILES = {}
for name, pdf_path in PDF_FILES.items():
    if not pdf_path.exists():
        print(f"  [경고] 없음: {pdf_path}")
        continue
    print(f"  발견: {pdf_path.name}")
    txt_path = WS / f"{name}.txt"
    if not txt_path.exists():
        text = pdf_to_txt(pdf_path, txt_path)
        print(f"    → {len(text.split()):,} tokens 추출")
    else:
        print(f"    → 기존 TXT 사용")
    TXT_FILES[name] = txt_path

if not TXT_FILES:
    print("\n[오류] PDF를 찾지 못했습니다.")
    print(f"PDF_FILES 경로를 확인하세요: {SCRIPT_DIR}")
    sys.exit(1)

# ── 전체 파이프라인 ───────────────────────────────────────────
all_results = []

for product_name, txt_path in TXT_FILES.items():
    for persona in PERSONAS:
        session_id = f"US_{product_name}_{persona['id']}"
        prod_dir   = WS / product_name / persona["id"]
        prod_dir.mkdir(parents=True, exist_ok=True)

        drafts_path    = str(prod_dir / "vulnerability_drafts.json")
        validated_path = str(prod_dir / "validated_findings.json")
        report_path    = str(prod_dir / "final_report.json")

        print(f"\n{'='*65}")
        print(f"[{product_name}] x [{persona['id']}] "
              f"{persona['occupation']} {persona['age']}세")
        print(f"risk_flags: {persona['risk_flags']}")
        print(f"{'='*65}")

        print(f"\n[Stage 2] 취약점 탐지...")
        drafts = run_spotter(str(txt_path), persona, session_id)
        Path(drafts_path).write_text(
            json.dumps(drafts, ensure_ascii=False, indent=2), encoding="utf-8")
        unc = drafts.get("uncategorized_count", 0)
        print(f"  → 총 {drafts['total_vulnerabilities']}건 (UNCATEGORIZED: {unc}건)")
        time.sleep(1)

        print(f"\n[Stage 3] CourtListener 판례 검증...")
        validated = run_validator(drafts_path, validated_path)
        time.sleep(1)

        print(f"\n[Stage 4] 심각도 분류...")
        report = run_classifier(validated_path, report_path)

        vc = report.get("vulnerability_count", {})
        all_results.append({
            "product":       product_name,
            "persona_id":    persona["id"],
            "occupation":    persona["occupation"],
            "n_flags":       len(persona["risk_flags"]),
            "n_vulns":       drafts["total_vulnerabilities"],
            "uncategorized": unc,
            "confirmed":     validated["summary"]["confirmed"],
            "overall_risk":  report["overall_risk_level"],
            "critical":      vc.get("CRITICAL", 0),
            "high":          vc.get("HIGH", 0),
            "medium":        vc.get("MEDIUM", 0),
            "report_path":   report_path,
        })
        time.sleep(2)

# ── 전체 요약 ─────────────────────────────────────────────────
print(f"\n\n{'='*75}")
print("전체 실험 요약")
print(f"{'='*75}")
print(f"{'상품':<28} {'P':>3} {'탐지':>5} {'UNC':>5} {'확인':>5} "
      f"{'C':>3} {'H':>3} {'M':>3} {'위험도':>8}")
print("-"*75)
for r in all_results:
    print(f"{r['product'][:26]:<28} {r['persona_id']:>3} "
          f"{r['n_vulns']:>5} {r['uncategorized']:>5} {r['confirmed']:>5} "
          f"{r['critical']:>3} {r['high']:>3} {r['medium']:>3} "
          f"{r['overall_risk']:>8}")

summary_path = WS / "summary_all.json"
summary_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n[DONE] 전체 요약: {summary_path}")
print(f"[DONE] 결과 폴더: {WS}")
