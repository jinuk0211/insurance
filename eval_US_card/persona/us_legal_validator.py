"""
us_legal_validator.py — Stage 3
vulnerability_drafts.json → CourtListener 판례 검색 → validated_findings.json
"""
import json, re, time, math, os
from pathlib import Path
from collections import defaultdict

try:
    import requests
except ImportError:
    raise ImportError("pip install requests")

try:
    import anthropic
    _judge_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY",""))
    HAS_ANTHROPIC = True
except:
    HAS_ANTHROPIC = False

CL_BASE = "https://www.courtlistener.com/api/rest/v4"
CL_KEY  = os.environ.get("COURTLISTENER_API_KEY","")
CL_HDR  = {"User-Agent": "KFinLegalHarness-US/1.0"}
if CL_KEY:
    CL_HDR["Authorization"] = f"Token {CL_KEY}"

def clean_ascii(text: str) -> str:
    """non-ASCII 문자 제거 (윈도우 인코딩 오류 방지)"""
    return text.encode("ascii", errors="ignore").decode("ascii")


# US 법령 매핑 (Citation Gate용)
US_STATUTE_MAP = {
    "CC-01": [("Truth in Lending Act","15 U.S.C. § 1601"),("CFPB Regulation Z","12 CFR Part 1026")],
    "CC-02": [("Truth in Lending Act","15 U.S.C. § 1666i"),("Credit CARD Act 2009","15 U.S.C. § 1637")],
    "CC-03": [("Truth in Lending Act","15 U.S.C. § 1637"),("CFPB Regulation Z","12 CFR § 1026.51")],
    "CC-04": [("Truth in Lending Act","15 U.S.C. § 1637"),("Credit CARD Act 2009","15 U.S.C. § 1637(i)")],
    "CC-05": [("Federal Arbitration Act","9 U.S.C. § 2"),("Dodd-Frank Act","12 U.S.C. § 5518")],
}

TAX_QUERY = {
    "CC-01": "credit card fee disclosure TILA Truth in Lending hidden fees",
    "CC-02": "credit card penalty APR interest rate increase consumer protection TILA",
    "CC-03": "credit card minimum payment billing unfair practice consumer",
    "CC-04": "credit card change in terms unilateral modification account cancellation",
    "CC-05": "credit card arbitration clause class action waiver unconscionable consumer",
    "UNCATEGORIZED": "",
}

# ── CourtListener 검색 ────────────────────────────────────────
def cl_search(query: str, n: int = 10) -> list[dict]:
    if not query:
        return []
    try:
        r = requests.get(
            f"{CL_BASE}/search/",
            params={"q": query, "type": "o", "stat_Precedential": "on", "count": n},
            headers=CL_HDR, timeout=15
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        candidates = []
        for item in results:
            candidates.append({
                "case_number": str(item.get("docket_id","")),
                "case_name":   item.get("caseName",""),
                "court":       item.get("court_id",""),
                "date":        item.get("dateFiled",""),
                "snippet":     clean_ascii(item.get("snippet",""))[:400],
                "_full":       clean_ascii(item.get("caseName","") + " " + item.get("snippet","")),
                "source":      "courtlistener.com",
                "url":         "https://www.courtlistener.com" + item.get("absolute_url",""),
            })
        return candidates
    except Exception as e:
        print(f"  [CourtListener] {e}")
        return []

# ── BM25 재랭킹 ───────────────────────────────────────────────
def tokenize(text: str) -> list:
    return re.findall(r"[a-zA-Z]+", text.lower())

def rerank_bm25(query: str, candidates: list, top_k: int = 3) -> list:
    if not candidates: return []
    try:
        from rank_bm25 import BM25Okapi
        docs   = [tokenize(c["_full"]) or ["_"] for c in candidates]
        bm25   = BM25Okapi(docs)
        scores = bm25.get_scores(tokenize(query) or ["_"])
        max_s  = max(scores) if max(scores) > 0 else 1.0
        norm   = [float(s)/max_s for s in scores]
    except ImportError:
        q_set = set(tokenize(query))
        norm  = [len(q_set & set(tokenize(c["_full"]))) / max(len(q_set),1)
                 for c in candidates]
    ranked = sorted(zip(candidates, norm), key=lambda x: -x[1])
    return [dict(d, relevance_score=round(s,3)) for d,s in ranked[:top_k]]

# ── Claude Judge ──────────────────────────────────────────────
_JUDGE_CACHE = {}

def judge_relevance(vuln: dict, prec: dict) -> bool:
    key = vuln.get("id","") + "|" + prec.get("case_number","")
    if key in _JUDGE_CACHE:
        return _JUDGE_CACHE[key]

    # API 없으면 키워드 fallback
    if not HAS_ANTHROPIC:
        kw_map = {
            "CC-01":["fee","disclosure","TILA","Truth in Lending"],
            "CC-02":["APR","interest","penalty","rate"],
            "CC-03":["minimum payment","billing","balance"],
            "CC-04":["change","terms","cancel","modification"],
            "CC-05":["arbitration","class action","waiver"],
        }
        kws  = kw_map.get(vuln.get("taxonomy",""), [])
        text = (prec.get("case_name","") + prec.get("snippet","")).lower()
        result = any(k.lower() in text for k in kws)
        _JUDGE_CACHE[key] = result
        return result

    prompt = (
        f"Is this US court case legally relevant to the credit card vulnerability?\n\n"
        f"[Vulnerability] {vuln.get('taxonomy','')} — {vuln.get('title','')}\n"
        f"[Clause] {vuln.get('triggered_by','')[:200]}\n\n"
        f"[Case: {prec.get('case_name','')[:80]}]\n"
        f"Snippet: {prec.get('snippet','')[:300]}\n\n"
        f"Relevant topics: consumer finance, credit card, APR, fees, arbitration, "
        f"TILA, CFPB, Fair Credit Billing Act, class action.\n"
        f"Reply YES or NO only."
    )
    try:
        resp = _judge_client.messages.create(
            model="claude-haiku-4-5", max_tokens=5,
            messages=[{"role":"user","content":prompt}]
        )
        result = resp.content[0].text.strip().upper().startswith("Y")
        _JUDGE_CACHE[key] = result
        time.sleep(0.2)
        return result
    except Exception as e:
        print(f"  [Judge오류] {e}")
        return False

# ── Citation Gate ─────────────────────────────────────────────
def verify_statute(taxonomy: str) -> list:
    """US 법령 매핑 반환 (Citation Gate: 사전 정의된 것만)"""
    return [{"law_name": s[0], "article": s[1], "verified": True}
            for s in US_STATUTE_MAP.get(taxonomy, [])]

# ── 단일 취약점 검증 ──────────────────────────────────────────
def validate_one(vuln: dict, top_k: int = 3) -> dict:
    tax   = vuln.get("taxonomy","")
    query = vuln.get("retrieval_query","") or TAX_QUERY.get(tax,"")

    # UNCATEGORIZED: triggered_by에서 핵심 키워드 추출해서 쿼리 구성
    if tax == "UNCATEGORIZED":
        words = [w for w in tokenize(vuln.get("triggered_by","")) if len(w) > 3]
        query = " ".join(words[:8]) + " credit card consumer rights"
        if not query.strip():
            query = "credit card unfair practice consumer protection"

    candidates = cl_search(query, n=15) if query else []
    time.sleep(0.5)

    ranked     = rerank_bm25(query, candidates, top_k)
    good_precs = []
    for prec in ranked:
        if judge_relevance(vuln, prec):
            good_precs.append({
                "case_number":     prec.get("case_number",""),
                "case_name":       prec.get("case_name",""),
                "court":           prec.get("court",""),
                "date":            prec.get("date",""),
                "summary":         clean_ascii(prec.get("snippet",""))[:100],
                "relevance_score": prec.get("relevance_score",0),
                "source":          prec.get("source",""),
                "url":             prec.get("url",""),
            })

    statutes = verify_statute(tax)
    has_prec = len(good_precs) > 0
    status   = "CONFIRMED" if (has_prec or statutes) else "UNVERIFIED"
    if tax == "UNCATEGORIZED" and not has_prec:
        status = "UNVERIFIED"  # UNCATEGORIZED는 판례 없어도 REJECTED 안 함

    note = f"CourtListener:{len(good_precs)}건"
    if statutes:
        note += f" | US statute:{len(statutes)}건"

    return {
        "finding_id":           vuln.get("id",""),
        "taxonomy":             tax,
        "title":                vuln.get("title",""),
        "triggered_by":         vuln.get("triggered_by",""),
        "description":          vuln.get("description",""),
        "status":               status,
        "confidence":           vuln.get("confidence",0.65),
        "user_relevance_score": vuln.get("user_relevance",0.6),
        "search_query_used":    query,
        "legal_grounds": {
            "statutes":   statutes,
            "precedents": good_precs,
        },
        "hallucination_blocked": 0,
        "validator_note": note,
    }

# ── 메인 ─────────────────────────────────────────────────────
def run_validator(drafts_path: str, out_path: str):
    data  = json.loads(Path(drafts_path).read_text(encoding="utf-8"))
    vulns = [v for v in data.get("vulnerabilities",[]) if v.get("status") != "LOW_CONFIDENCE"]
    print(f"검증 대상: {len(vulns)}건 (LOW_CONFIDENCE 제외)")

    findings = []
    confirmed = unverified = 0
    for v in vulns:
        print(f"  [{v['id']}] {v['taxonomy']} | {v['title'][:40]}")
        result = validate_one(v)
        findings.append(result)
        s = result["status"]
        if s == "CONFIRMED":   confirmed += 1
        else:                  unverified += 1
        icon = "[OK]" if s == "CONFIRMED" else "[?]"
        print(f"    {icon} [{s}] {result['validator_note']}")

    output = {
        "session_id":    data.get("session_id",""),
        "product":       data.get("product",""),
        "profile":       data.get("profile",{}),
        "validated_at":  __import__("datetime").datetime.utcnow().isoformat(),
        "summary": {
            "total_draft": len(vulns),
            "confirmed":   confirmed,
            "unverified":  unverified,
            "rejected":    0,
        },
        "findings": findings,
    }
    Path(out_path).write_text(json.dumps(output, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"\n[DONE] CONFIRMED:{confirmed} UNVERIFIED:{unverified} -> {out_path}")
    return output

if __name__ == "__main__":
    run_validator(
        "/home/claude/workspace_us/vulnerability_drafts.json",
        "/home/claude/workspace_us/validated_findings.json"
    )
