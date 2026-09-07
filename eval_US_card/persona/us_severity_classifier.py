"""
us_severity_classifier.py — Stage 4
validated_findings.json → 심각도 분류 + 최종 리포트 생성
"""
import json, os, re
from pathlib import Path
from datetime import datetime, timezone

try:
    import anthropic
    _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY",""))
    HAS_LLM = True
except:
    HAS_LLM = False

def calc_user_relevance(finding: dict, profile: dict) -> float:
    score = finding.get("user_relevance_score", 0.6)
    tax   = finding.get("taxonomy","")
    flags = profile.get("risk_flags",[])

    if "carry_balance" in flags and tax in ("CC-02","CC-03"):   score += 0.20
    if "late_payment_history" in flags and tax == "CC-02":      score += 0.15
    if "irregular_income" in flags and tax in ("CC-03","CC-04"): score += 0.15
    if "low_income" in flags and tax in ("CC-01","CC-03"):       score += 0.20
    if "elderly" in flags and tax in ("CC-04","CC-05"):          score += 0.15
    if "credit_risk" in flags and tax in ("CC-02","CC-04"):      score += 0.20
    return round(min(score, 1.0), 2)

def classify_severity(finding: dict, profile: dict) -> str:
    status    = finding.get("status","UNVERIFIED")
    conf      = finding.get("confidence", 0.65)
    rel       = calc_user_relevance(finding, profile)
    n_prec    = len(finding.get("legal_grounds",{}).get("precedents",[]))
    tax       = finding.get("taxonomy","")
    flags     = profile.get("risk_flags",[])

    if status == "CONFIRMED":
        if conf >= 0.85 and rel >= 0.80 and n_prec >= 2:
            sev = "CRITICAL"
        elif conf >= 0.70 and rel >= 0.60:
            sev = "HIGH"
        elif conf >= 0.55:
            sev = "MEDIUM"
        else:
            sev = "LOW"
    elif status == "UNVERIFIED":
        # UNCATEGORIZED는 판례 없어도 MEDIUM 가능
        if tax == "UNCATEGORIZED":
            sev = "MEDIUM" if rel >= 0.60 else "LOW"
        else:
            sev = "MEDIUM" if rel >= 0.65 else "LOW"
    else:
        sev = "LOW"

    # 프로필 업그레이드
    if "carry_balance" in flags and tax in ("CC-02","CC-03"):
        sev = {"LOW":"MEDIUM","MEDIUM":"HIGH","HIGH":"CRITICAL","CRITICAL":"CRITICAL"}[sev]
    if "low_income" in flags and tax == "CC-01":
        sev = {"LOW":"MEDIUM","MEDIUM":"HIGH","HIGH":"CRITICAL","CRITICAL":"CRITICAL"}[sev]

    return sev

def gen_plain_language(finding: dict, profile: dict) -> dict:
    if not HAS_LLM:
        return {
            "plain_language_explanation": f"This clause may disadvantage consumers: {finding.get('triggered_by','')[:80]}",
            "user_impact": "Review this clause carefully before signing.",
            "estimated_risk_scenario": "You may face unexpected costs or limited rights.",
            "recommended_actions": [{"action":"Review with a consumer advocate","priority":"immediate","contact":"CFPB 1-855-411-2372"}]
        }

    profile_str = (
        f"Age {profile.get('age','')}, {profile.get('occupation','')}, "
        f"risk flags: {', '.join(profile.get('risk_flags',[]))}"
    )
    prompt = f"""You are a US consumer financial protection advisor.

[Vulnerability]
Type: {finding.get('taxonomy','')} — {finding.get('title','')}
Clause: {finding.get('triggered_by','')[:300]}
Status: {finding.get('status','')}

[User Profile]
{profile_str}

Write at a plain English level (8th grade):
1. plain_language_explanation (≤150 chars): What is the problem?
2. user_impact (≤100 chars): How does this affect THIS specific user?
3. estimated_risk_scenario (≤200 chars): Most realistic harm scenario
4. recommended_actions: 1-3 actions, each with action/priority/contact

DO NOT invent new cases or statutes.
Reply ONLY as JSON:
{{"plain_language_explanation":"...","user_impact":"...","estimated_risk_scenario":"...","recommended_actions":[{{"action":"...","priority":"immediate|pre-signing|optional","contact":"..."}}]}}"""

    try:
        resp = _client.messages.create(
            model="claude-sonnet-4-20250514", max_tokens=600,
            messages=[{"role":"user","content":prompt}]
        )
        text = resp.content[0].text.strip()
        m = re.search(r'\{.*\}', text, re.DOTALL)
        return json.loads(m.group()) if m else {}
    except Exception as e:
        print(f"  [생성오류] {e}")
        return {}

def overall_risk(findings: list) -> str:
    sevs = [f.get("severity","LOW") for f in findings]
    if "CRITICAL" in sevs: return "HIGH"
    if "HIGH" in sevs:     return "MEDIUM"
    if sevs:               return "LOW"
    return "NONE"

def run_classifier(validated_path: str, out_path: str):
    data     = json.loads(Path(validated_path).read_text(encoding="utf-8"))
    findings = [f for f in data.get("findings",[]) if f.get("status") != "REJECTED"]
    profile  = data.get("profile",{})
    product  = data.get("product","")

    print(f"심각도 분류: {len(findings)}건")

    ranked = []
    for f in findings:
        rel = calc_user_relevance(f, profile)
        sev = classify_severity(f, profile)
        f["user_relevance_score"] = rel
        f["severity"] = sev

        print(f"  [{f['finding_id']}] {sev:<8} | {f['taxonomy']} | {f['title'][:40]}")

        if sev not in ("LOW",):
            lang = gen_plain_language(f, profile)
            f.update(lang)

        ranked.append(f)

    # 정렬: severity → user_relevance_score
    sev_order = {"CRITICAL":0,"HIGH":1,"MEDIUM":2,"LOW":3}
    ranked.sort(key=lambda x: (sev_order.get(x.get("severity","LOW"),3), -x.get("user_relevance_score",0)))
    for i, f in enumerate(ranked):
        f["rank"] = i+1

    ov_risk = overall_risk(ranked)
    counts  = {s:sum(1 for f in ranked if f.get("severity")==s) for s in ("CRITICAL","HIGH","MEDIUM","LOW")}
    unc_count = sum(1 for f in ranked if f.get("taxonomy")=="UNCATEGORIZED")

    exec_summary = (
        f"Analysis of {product} identified {len(ranked)} consumer vulnerabilities. "
        f"Overall risk level: {ov_risk}. "
        f"Key concerns: {', '.join(f['title'] for f in ranked[:3] if f.get('title'))}."
    )

    output = {
        "session_id":       data.get("session_id",""),
        "generated_at":     datetime.now(timezone.utc).isoformat(),
        "product":          product,
        "doc_type":         "credit_card_agreement",
        "user_profile":     profile,
        "executive_summary": exec_summary,
        "overall_risk_level": ov_risk,
        "vulnerability_count": {**counts, "uncategorized": unc_count},
        "findings":         ranked,
        "general_recommendations": [
            "Read all terms carefully before signing any credit card agreement.",
            "Compare APR and fees across multiple issuers before applying.",
            "Note any arbitration clauses that waive your right to sue.",
            "Contact CFPB (1-855-411-2372) if you believe a term is unfair.",
            "For disputes, contact your state Attorney General's consumer protection office.",
        ],
        "disclaimer": (
            "This report is generated by AI analysis and has no legal effect. "
            "For specific legal advice, consult a consumer protection attorney or contact the CFPB."
        ),
    }

    Path(out_path).write_text(json.dumps(output, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"\n전체 위험도: {ov_risk}")
    print(f"CRITICAL:{counts['CRITICAL']} HIGH:{counts['HIGH']} MEDIUM:{counts['MEDIUM']} LOW:{counts['LOW']} UNCATEGORIZED:{unc_count}")
    print(f"[DONE] -> {out_path}")
    return output

if __name__ == "__main__":
    run_classifier(
        "/home/claude/workspace_us/validated_findings.json",
        "/home/claude/workspace_us/final_report.json"
    )
