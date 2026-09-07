"""
e4_persona_us.py

E4 (US): CFPB 신용카드 약관 × 10 페르소나 취약점 탐지

측정:
  1. 상품별 taxonomy 분포
  2. n_flags vs mean_user_relevance Pearson r

사용법:
  python e4_persona_us.py --txt path/to/agreement.txt
  python e4_persona_us.py --demo   (샘플 텍스트로 실행)
  python e4_persona_us.py --txt-dir data/txts/  (다중 파일)
"""

import json, re, math, random, time, os, argparse
from pathlib import Path
from collections import defaultdict

try:
    import anthropic
    _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
except Exception:
    _client = None
    print("[경고] anthropic 미설치 또는 API 키 없음 → mock 모드")

parser = argparse.ArgumentParser()
parser.add_argument("--txt",     type=str, help="단일 TXT 파일 경로")
parser.add_argument("--txt-dir", type=str, help="TXT 디렉터리")
parser.add_argument("--demo",    action="store_true", help="샘플 텍스트로 실행")
parser.add_argument("--n-personas", type=int, default=10)
parser.add_argument("--out-dir", type=str, default="results")
args = parser.parse_args()

OUT_DIR = Path(args.out_dir)
OUT_DIR.mkdir(parents=True, exist_ok=True)
random.seed(42)

# ── 샘플 약관 텍스트 ──────────────────────────────────────────
SAMPLE_AGREEMENTS = {
    "CFPB_Visa_Platinum": """
VISA PLATINUM CREDIT CARD AGREEMENT

INTEREST RATES:
- Purchase APR: 24.99% Variable (based on Prime Rate + 18.74%)
- Penalty APR: 29.99% - Applied when you miss 2+ consecutive payments
- Cash Advance APR: 29.99% Variable

FEES:
- Annual Fee: $95 (non-refundable, charged on first statement)
- Foreign Transaction Fee: 3% of each transaction in USD
- Late Payment Fee: $40 (if balance over $250)
- Cash Advance Fee: Greater of $15 or 5% of advance amount
- Balance Transfer Fee: 5% (minimum $10)

BILLING:
We use the Average Daily Balance method (including new purchases).
Minimum payment: 2% of balance or $35, whichever is greater.
Payment not received by 5pm ET on due date is considered late.

ARBITRATION:
ALL DISPUTES MUST BE RESOLVED THROUGH BINDING ARBITRATION.
YOU WAIVE YOUR RIGHT TO A JURY TRIAL AND CLASS ACTION.
Arbitration conducted by AAA under consumer rules.
You may opt out within 60 days of account opening only.

CHANGE IN TERMS:
We may change rates, fees, and terms at any time for any reason.
Notice will be provided as required by applicable law.
Continued use of your card constitutes acceptance.
    """,

    "CFPB_Mastercard_Cash": """
MASTERCARD CASH REWARDS AGREEMENT

APR: 19.99% to 29.99% Variable based on creditworthiness.
Default Rate: 29.99% if payment is 60+ days late.

REWARDS:
Cash back may be revoked if account is in default or closed.
Rewards have no cash value if account is closed for any reason.
We reserve the right to modify or cancel the rewards program.

MINIMUM PAYMENT TRAP:
Minimum payment = 1% of balance + finance charges + fees.
Example: $5,000 balance at 29.99% APR → 22+ years to pay off at minimum payment.

ACCOUNT CLOSURE:
We may close your account at any time without prior notice.
Upon closure, entire balance is immediately due.
We may charge-off your account and sell debt to collectors.

CLASS ACTION WAIVER:
By opening this account you agree that any legal action
must be brought individually and not as part of any class.
This waiver is a material term of this Agreement.

CREDIT LIMIT:
We may reduce your credit limit at any time without notice.
Transactions that would exceed your limit may be declined or approved
with an over-limit fee at our discretion.
    """,
}

# ── 전처리 ────────────────────────────────────────────────────
def preprocess(txt: str) -> str:
    lines = []
    for line in txt.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.fullmatch(r"[|\+\-=\s]+", s):
            continue
        if re.fullmatch(r"\d+", s):
            continue
        lines.append(s)
    return "\n".join(lines)

# ── 페르소나 생성 ─────────────────────────────────────────────
OCCUPATIONS = [
    "full-time employee", "self-employed", "retired",
    "part-time worker", "freelancer", "government employee",
    "student", "gig worker", "healthcare worker", "teacher",
]

CONDITIONS = [
    "diabetes", "heart condition", "recent bankruptcy",
    "high blood pressure", "disability",
]

RISK_OCCS   = {"self-employed", "gig worker", "freelancer", "part-time worker"}
LOW_INCOME  = {"part-time worker", "gig worker", "student"}

def gen_profiles(n: int) -> list[dict]:
    profiles = []
    rng = random.Random(42)
    for i in range(min(n, len(OCCUPATIONS))):
        age  = rng.randint(22, 70)
        occ  = OCCUPATIONS[i]
        conds = rng.sample(CONDITIONS, k=rng.randint(0, 2))
        carry = rng.choice([True, True, False])   # 잔액 이월 여부
        late  = rng.choice([True, False, False])   # 연체 경험

        flags = []
        if age >= 65:                            flags.append("elderly")
        if conds:                                flags.append("pre_existing")
        if occ in RISK_OCCS:                     flags.append("irregular_income")
        if occ in LOW_INCOME or age < 25:        flags.append("low_income")
        if carry:                                flags.append("carry_balance")
        if late:                                 flags.append("late_payment_history")
        if "recent bankruptcy" in conds:         flags.append("credit_risk")

        profiles.append({
            "profile_id":    f"P{i+1:02d}",
            "age":           age,
            "occupation":    occ,
            "conditions":    conds,
            "carry_balance": carry,
            "late_payment":  late,
            "risk_flags":    flags,
            "n_flags":       len(flags),
        })
    return profiles

# ── 취약점 탐지 ───────────────────────────────────────────────
TAXONOMY_DESC = """\
Vulnerability Types (US Credit Card):
- CC-01: Hidden or unclear fees
- CC-02: Unfavorable APR / penalty rate terms
- CC-03: Minimum payment trap / unfavorable billing
- CC-04: Unilateral change in terms / account cancellation
- CC-05: Mandatory arbitration / class action waiver
- UNCATEGORIZED: Other consumer disadvantages"""

def run_spotter(product_name: str, txt: str, profile: dict) -> list[dict]:
    if _client is None:
        # Mock: 항상 샘플 취약점 반환
        return [
            {"taxonomy": "CC-02", "title": "Penalty APR",
             "triggered_by": "Penalty APR applies",
             "confidence": 0.8,
             "user_relevance": 0.6 + 0.05 * profile["n_flags"]},
            {"taxonomy": "CC-05", "title": "Arbitration clause",
             "triggered_by": "binding arbitration",
             "confidence": 0.9,
             "user_relevance": 0.5 + 0.03 * profile["n_flags"]},
        ]

    profile_str = (
        f"Age {profile['age']}, {profile['occupation']}, "
        f"conditions: {', '.join(profile['conditions']) or 'none'}, "
        f"carries balance: {profile['carry_balance']}, "
        f"late payment history: {profile['late_payment']}, "
        f"risk flags: {', '.join(profile['risk_flags']) or 'none'}"
    )

    prompt = f"""You are a US consumer financial contract vulnerability detection expert.

[User Profile]
{profile_str}

[Credit Card Agreement: {product_name}]
{txt[:5000]}

From this user's perspective, detect ALL unfavorable vulnerability clauses.
Rate user_relevance (0.0~1.0) based on how much this clause affects THIS specific user.

{TAXONOMY_DESC}

Reply ONLY with a JSON array (no explanation):
[{{"taxonomy": "CC-XX", "title": "short title", "triggered_by": "verbatim clause (50 chars max)", "confidence": 0.0, "user_relevance": 0.0}}]"""

    try:
        resp = _client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        m = re.search(r'\[.*\]', text, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception as e:
        print(f"    [오류] {e}")
    return []

# ── Pearson r ─────────────────────────────────────────────────
def pearson_r(xs: list, ys: list) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(
        sum((x - mx) ** 2 for x in xs) *
        sum((y - my) ** 2 for y in ys)
    )
    return round(num / den, 4) if den > 0 else 0.0

# ── 약관 로드 ─────────────────────────────────────────────────
agreements = {}

if args.demo:
    agreements = {k: preprocess(v) for k, v in SAMPLE_AGREEMENTS.items()}
elif args.txt:
    p = Path(args.txt)
    agreements[p.stem] = preprocess(p.read_text(encoding="utf-8"))
elif args.txt_dir:
    for p in Path(args.txt_dir).glob("*.txt"):
        agreements[p.stem] = preprocess(p.read_text(encoding="utf-8"))
else:
    print("[정보] --demo, --txt, 또는 --txt-dir 필요 → demo 모드로 실행")
    agreements = {k: preprocess(v) for k, v in SAMPLE_AGREEMENTS.items()}

profiles = gen_profiles(args.n_personas)

print("=" * 65)
print(f"E4 실험 (US): {len(agreements)}개 상품 × {len(profiles)}개 페르소나")
print("=" * 65)
for p in profiles:
    print(f"  {p['profile_id']} | {p['age']}세 {p['occupation']:<20} "
          f"n_flags={p['n_flags']} {p['risk_flags']}")

# ── 실험 실행 ─────────────────────────────────────────────────
all_results = []
product_taxonomy = {}

for product_name, txt in agreements.items():
    product_taxonomy[product_name] = defaultdict(int)
    print(f"\n── {product_name} ({len(txt):,}자) ──")

    for p in profiles:
        print(f"  [{p['profile_id']}] {p['occupation']} {p['age']}세 "
              f"(n_flags={p['n_flags']})", end=" ... ")

        vulns = run_spotter(product_name, txt, p)
        if _client is not None:
            time.sleep(0.8)

        mean_rel  = (sum(v.get("user_relevance", 0.6) for v in vulns) / len(vulns)
                     if vulns else 0.0)
        mean_conf = (sum(v.get("confidence", 0.6) for v in vulns) / len(vulns)
                     if vulns else 0.0)

        for v in vulns:
            product_taxonomy[product_name][v.get("taxonomy", "UNCATEGORIZED")] += 1

        all_results.append({
            "profile_id":      p["profile_id"],
            "n_flags":         p["n_flags"],
            "risk_flags":      p["risk_flags"],
            "age":             p["age"],
            "occupation":      p["occupation"],
            "product":         product_name,
            "n_vulns":         len(vulns),
            "mean_relevance":  round(mean_rel, 4),
            "mean_confidence": round(mean_conf, 4),
            "vulnerabilities": vulns,
        })
        print(f"{len(vulns)}개 탐지, rel={mean_rel:.3f}")

# ── 분석 1: taxonomy 분포 ─────────────────────────────────────
print("\n" + "=" * 65)
print("분석 1: 상품별 taxonomy 분포")
print("=" * 65)
all_tax = ["CC-01", "CC-02", "CC-03", "CC-04", "CC-05", "UNCATEGORIZED"]
header = f"{'상품':<25}" + "".join(f"{t:>12}" for t in all_tax) + f"{'합계':>7}"
print(header)
print("-" * 80)
for prod, dist in product_taxonomy.items():
    total = sum(dist.values())
    row = f"{prod:<25}" + "".join(f"{dist.get(t,0):>12}" for t in all_tax) + f"{total:>7}"
    print(row)

# ── 분석 2: Pearson r ─────────────────────────────────────────
print("\n" + "=" * 65)
print(f"분석 2: n_flags vs mean_user_relevance (N={len(all_results)})")
print("=" * 65)
xs    = [r["n_flags"]        for r in all_results]
ys    = [r["mean_relevance"] for r in all_results]
r_all = pearson_r(xs, ys)
print(f"  전체 Pearson r = {r_all:+.4f}")

for prod in agreements:
    sub = [r for r in all_results if r["product"] == prod]
    r_p = pearson_r([r["n_flags"] for r in sub],
                    [r["mean_relevance"] for r in sub])
    print(f"  {prod:<30}  r = {r_p:+.4f}  (N={len(sub)})")

# risk_flag별 평균 relevance
print("\n  Risk Flag별 mean relevance:")
flag_types = ["carry_balance", "late_payment_history", "irregular_income",
              "low_income", "elderly", "credit_risk"]
for flag in flag_types:
    with_flag    = [r["mean_relevance"] for r in all_results if flag in r["risk_flags"]]
    without_flag = [r["mean_relevance"] for r in all_results if flag not in r["risk_flags"]]
    if with_flag and without_flag:
        delta = sum(with_flag)/len(with_flag) - sum(without_flag)/len(without_flag)
        print(f"    {flag:<28}  Δ={delta:+.3f}  "
              f"(n_with={len(with_flag)}, n_without={len(without_flag)})")

# ── 저장 ─────────────────────────────────────────────────────
output = {
    "experiment":   "e4_persona_US",
    "n_profiles":   len(profiles),
    "n_products":   len(agreements),
    "total_calls":  len(all_results),
    "pearson_r_all": r_all,
    "pearson_r_by_product": {
        prod: pearson_r(
            [r["n_flags"]        for r in all_results if r["product"] == prod],
            [r["mean_relevance"] for r in all_results if r["product"] == prod]
        )
        for prod in agreements
    },
    "taxonomy_dist": {
        prod: dict(dist) for prod, dist in product_taxonomy.items()
    },
    "all_results": all_results,
}
out_path = OUT_DIR / "e4_persona_us.json"
out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
print(f"\n✓ 저장: {out_path}")
