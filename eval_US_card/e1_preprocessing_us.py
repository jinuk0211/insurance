"""
e1_preprocessing_us.py

E1 (US): CFPB 신용카드 약관 PDF 전처리 전략 비교
  Raw / TextRank / Ours (rule-based)

측정:
  - compression_rate  (output_tokens / input_tokens, ↓better)
  - keyword_recall    (취약점 키워드 보존율, ↑better)
  - semantic_sim      (TF-IDF cosine, ↑better)

사용법:
  python e1_preprocessing_us.py --pdf path/to/agreement.pdf
  python e1_preprocessing_us.py --pdf path/to/agreement.pdf --all-pdfs data/pdfs/
"""

import re, math, argparse, json
from pathlib import Path
from collections import defaultdict

# ── 취약점 키워드 (미국 신용카드/금융 도메인) ─────────────────
VULN_KEYWORDS = [
    # CC-01: 숨겨진 수수료
    "fee", "fees", "penalty", "charge", "surcharge", "annual fee",
    # CC-02: 금리 변동
    "variable rate", "apr", "interest rate", "prime rate", "margin",
    "rate increase", "penalty rate", "default rate",
    # CC-03: 청구 방식 불리
    "average daily balance", "two-cycle", "billing cycle",
    "minimum payment", "minimum due",
    # CC-04: 계약 해지/변경 불리
    "cancel", "terminate", "close account", "change in terms",
    "opt-out", "arbitration", "class action waiver",
    # CC-05: 분쟁해결 불리
    "arbitration", "dispute", "waiver", "binding arbitration",
    "class action",
    # UNCATEGORIZED
    "default", "delinquent", "collection", "credit limit",
]

def tokenize(text: str) -> list[str]:
    """소문자 단어 토큰화"""
    return re.findall(r"[a-z]+(?:'[a-z]+)?", text.lower())

def keyword_recall(text: str, keywords: list[str]) -> float:
    """키워드 보존율"""
    text_lower = text.lower()
    found = sum(1 for kw in keywords if kw in text_lower)
    return round(found / len(keywords), 4)

def tfidf_cosine(text1: str, text2: str) -> float:
    """TF-IDF 코사인 유사도"""
    docs = [tokenize(text1), tokenize(text2)]
    df = defaultdict(int)
    for doc in docs:
        for t in set(doc):
            df[t] += 1
    N = 2
    idf = {t: math.log((N + 1) / (df[t] + 1)) + 1 for t in df}

    def vec(tokens):
        tf = defaultdict(int)
        for t in tokens:
            tf[t] += 1
        total = len(tokens) or 1
        return {t: (c / total) * idf.get(t, 1.0) for t, c in tf.items()}

    v1, v2 = vec(docs[0]), vec(docs[1])
    keys = set(v1) & set(v2)
    if not keys:
        return 0.0
    dot = sum(v1[k] * v2[k] for k in keys)
    n1 = math.sqrt(sum(x * x for x in v1.values()))
    n2 = math.sqrt(sum(x * x for x in v2.values()))
    return round(dot / (n1 * n2), 4) if n1 * n2 > 0 else 0.0

# ── PDF 텍스트 추출 ───────────────────────────────────────────
def extract_pdf(pdf_path: Path) -> str:
    try:
        import pdfplumber
        texts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                # 표 영역 분리
                tables = page.extract_tables()
                table_rows = []
                for table in (tables or []):
                    for row in table:
                        cells = [c.strip() if c else "" for c in row]
                        table_rows.append(" | ".join(cells))

                body = page.extract_text() or ""
                if table_rows:
                    body += "\n" + "\n".join(table_rows)
                texts.append(body)
        return "\n".join(texts)
    except ImportError:
        raise ImportError("pdfplumber 설치 필요: pip install pdfplumber")

# ── 전처리 전략들 ─────────────────────────────────────────────
def strategy_raw(text: str) -> str:
    """전처리 없음 (baseline)"""
    return text

def strategy_textrank(text: str, ratio: float = 0.6) -> str:
    """TextRank 추출 요약 (문장 유사도 기반)"""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    if len(sentences) <= 3:
        return text

    # 문장 간 TF-IDF 코사인 유사도 행렬
    n = len(sentences)
    scores = [0.0] * n
    for i in range(n):
        for j in range(n):
            if i != j:
                scores[i] += tfidf_cosine(sentences[i], sentences[j])

    # 상위 ratio 문장 선택
    k = max(1, int(n * ratio))
    top_idx = sorted(range(n), key=lambda x: -scores[x])[:k]
    top_idx_sorted = sorted(top_idx)
    return " ".join(sentences[i] for i in top_idx_sorted)

# 제거할 보일러플레이트 패턴 (미국 신용카드 약관)
BOILERPLATE_EXACT = [
    "this page intentionally left blank",
    "please read this agreement carefully",
    "keep this agreement for your records",
    "continued on next page",
    "see reverse side",
    "member fdic",
    "equal housing lender",
]

BOILERPLATE_PREFIX = [
    "©", "copyright", "all rights reserved",
    "page ", "rev.", "form #",
]

BOILERPLATE_SUBSTR = [
    "equal opportunity lender",
    "fdic insured",
    "this is not a bill",
]

# 법적으로 무의미한 블록 패턴
NOISE_PATTERNS = [
    r"^\s*\d+\s*$",                    # 페이지 번호만
    r"^[_\-=\*]{5,}$",                 # 구분선만
    r"^\s*\[?\s*continued\s*\]?\s*$",  # "continued"만
]

def strategy_ours(text: str) -> str:
    """
    Rule-based 전처리:
    1. 보일러플레이트 제거
    2. 페이지 구분선/번호 제거
    3. 공백 정규화
    4. 법적 무의미 블록 제거
    """
    lines = text.splitlines()
    cleaned = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 정확 매치
        if stripped.lower() in BOILERPLATE_EXACT:
            continue

        # 접두어 매치
        if any(stripped.lower().startswith(p) for p in BOILERPLATE_PREFIX):
            continue

        # 포함 매치
        if any(p in stripped.lower() for p in BOILERPLATE_SUBSTR):
            continue

        # 노이즈 패턴
        if any(re.match(p, stripped) for p in NOISE_PATTERNS):
            continue

        # 너무 짧은 줄 (3단어 미만, 숫자/특수문자만)
        words = re.findall(r"[a-zA-Z]+", stripped)
        if len(words) < 2 and len(stripped) < 15:
            continue

        cleaned.append(stripped)

    # 공백 정규화
    result = "\n".join(cleaned)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()

# ── 토큰 수 추정 (단어 기반) ──────────────────────────────────
def count_tokens(text: str) -> int:
    """단어 기반 토큰 수 추정 (tiktoken 없이)"""
    return len(text.split())

# ── 실험 실행 ─────────────────────────────────────────────────
def run_experiment(pdf_path: Path) -> dict:
    print(f"\n{'='*65}")
    print(f"E1 실험 (US): {pdf_path.name}")
    print(f"{'='*65}")

    # 텍스트 추출
    raw_text = extract_pdf(pdf_path)
    print(f"원본 텍스트: {count_tokens(raw_text):,} tokens")

    strategies = {
        "Raw":      strategy_raw(raw_text),
        "TextRank": strategy_textrank(raw_text),
        "Ours":     strategy_ours(raw_text),
    }

    results = {}
    base_tokens = count_tokens(raw_text)

    print(f"\n{'전략':<12} {'Tokens':>8} {'Comp.Rate':>10} {'KW Recall':>10} {'Sem.Sim':>8}")
    print("-" * 55)

    for name, text in strategies.items():
        tokens = count_tokens(text)
        comp   = round(tokens / base_tokens, 4) if base_tokens > 0 else 1.0
        kw_rec = keyword_recall(text, VULN_KEYWORDS)
        sem    = tfidf_cosine(raw_text, text)

        results[name] = {
            "tokens":           tokens,
            "compression_rate": comp,
            "keyword_recall":   kw_rec,
            "semantic_sim":     sem,
        }

        marker = " ◀" if name == "Ours" else ""
        print(f"{name:<12} {tokens:>8,} {comp:>10.4f} {kw_rec:>10.4f} {sem:>8.4f}{marker}")

    return {
        "pdf":       pdf_path.name,
        "base_tokens": base_tokens,
        "results":   results,
    }

# ── 다중 PDF 평균 ─────────────────────────────────────────────
def run_batch(pdf_dir: Path) -> dict:
    pdfs = list(pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"[경고] {pdf_dir}에 PDF 없음")
        return {}

    print(f"\n{len(pdfs)}개 PDF 일괄 처리...")
    agg = defaultdict(lambda: defaultdict(list))

    for pdf_path in pdfs:
        try:
            res = run_experiment(pdf_path)
            for strat, metrics in res["results"].items():
                for k, v in metrics.items():
                    agg[strat][k].append(v)
        except Exception as e:
            print(f"  [오류] {pdf_path.name}: {e}")

    avg = {
        strat: {k: round(sum(v) / len(v), 4) for k, v in metrics.items()}
        for strat, metrics in agg.items()
    }

    print(f"\n{'='*65}")
    print(f"E1 평균 결과 ({len(pdfs)}개 PDF)")
    print(f"{'='*65}")
    print(f"{'전략':<12} {'Tokens':>8} {'Comp.Rate':>10} {'KW Recall':>10} {'Sem.Sim':>8}")
    print("-" * 55)
    for strat, m in avg.items():
        print(f"{strat:<12} {m['tokens']:>8,.0f} {m['compression_rate']:>10.4f} "
              f"{m['keyword_recall']:>10.4f} {m['semantic_sim']:>8.4f}")
    return avg

# ── 텍스트 직접 입력 모드 (PDF 없을 때) ──────────────────────
def run_from_text(text: str, label: str = "sample") -> dict:
    """PDF 없이 텍스트 직접 실험"""
    strategies = {
        "Raw":      strategy_raw(text),
        "TextRank": strategy_textrank(text),
        "Ours":     strategy_ours(text),
    }
    base_tokens = count_tokens(text)
    results = {}
    print(f"\n{'='*65}")
    print(f"E1 실험 (텍스트 직접): {label}")
    print(f"{'='*65}")
    print(f"{'전략':<12} {'Tokens':>8} {'Comp.Rate':>10} {'KW Recall':>10} {'Sem.Sim':>8}")
    print("-" * 55)
    for name, out_text in strategies.items():
        tokens = count_tokens(out_text)
        comp   = round(tokens / base_tokens, 4) if base_tokens > 0 else 1.0
        kw_rec = keyword_recall(out_text, VULN_KEYWORDS)
        sem    = tfidf_cosine(text, out_text)
        results[name] = {
            "tokens": tokens, "compression_rate": comp,
            "keyword_recall": kw_rec, "semantic_sim": sem,
        }
        print(f"{name:<12} {tokens:>8,} {comp:>10.4f} {kw_rec:>10.4f} {sem:>8.4f}")
    return {"label": label, "base_tokens": base_tokens, "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf",      type=str, help="단일 PDF 경로")
    parser.add_argument("--all-pdfs", type=str, help="PDF 디렉터리 (일괄 처리)")
    parser.add_argument("--out",      type=str, default="results/e1_us.json")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.all_pdfs:
        result = run_batch(Path(args.all_pdfs))
    elif args.pdf:
        result = run_experiment(Path(args.pdf))
    else:
        # 데모: 샘플 텍스트로 실행
        SAMPLE = """
        CREDIT CARD AGREEMENT
        Annual Percentage Rate (APR) for Purchases: 29.99% Variable APR.
        This APR will vary with the market based on the Prime Rate.
        Penalty APR and When it Applies: 29.99% This APR may be applied to your account
        if you make a late payment.
        Annual Fee: $95
        Foreign Transaction Fee: 3% of the U.S. dollar amount of each transaction.
        Minimum Interest Charge: If you are charged interest, the charge will be no less than $1.50.

        HOW TO AVOID PAYING INTEREST ON PURCHASES
        Your due date is at least 25 days after the close of each billing cycle.
        We will not charge you any interest on purchases if you pay your entire balance by the due date each month.

        Page 1 of 8
        Member FDIC
        Equal Housing Lender
        This page intentionally left blank

        ARBITRATION CLAUSE - IMPORTANT - PLEASE READ
        Either you or we may, without the other's consent, elect mandatory binding arbitration
        for any claim, dispute, or controversy between you and us.
        CLASS ACTION WAIVER: IF ARBITRATION IS CHOSEN BY ANY PARTY, NEITHER YOU NOR WE WILL
        HAVE THE RIGHT TO LITIGATE THAT CLAIM IN COURT OR TO HAVE A JURY TRIAL ON THAT CLAIM.

        DEFAULT AND COLLECTION
        You will be in default if you fail to make any minimum payment when due,
        exceed your credit limit, or if you become insolvent or bankrupt.
        Upon default, we may close your account, require immediate payment of your full balance,
        and report the delinquency to credit reporting agencies.

        CHANGE IN TERMS
        We may change the terms of this Agreement, including the APR, at any time.
        We will give you advance notice of any such change as required by applicable law.
        Continued use of your account means you accept the new terms.
        You may opt-out of the change by closing your account.

        © 2024 First National Bank. All rights reserved. Form #CC-2024-001
        Rev. January 2024
        """
        result = run_from_text(SAMPLE, "cfpb_sample")

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n✓ 저장: {out_path}")
