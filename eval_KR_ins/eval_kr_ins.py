"""
eval_kr_ins.py — E1/E2/E3 evaluation for the KR insurance task (T1, KR-Ins).

Korean-insurance-specific re-evaluation to populate the KR-Ins rows of
acl_latex.tex tables E1, E2, E3 with verifiable measurements on a small
seed-fixed sample, in the same spirit as eval_US_loan/eval_loan.py.

E1 — Preprocessing fidelity         : Raw / TextRank / Ours
E2 — Vulnerability detection input   : zero-shot (n/a, no PDF), text_raw,
                                        few_shot, ours_no_preprocess, ours,
                                        ours_no_refine
E3 — Retrieval quality               : BM25 / TF-IDF / Emb / Hybrid / Ours
                                        against data/precedents.json
                                        (17 KR Supreme/appellate precedents)

LLM judge for E2 uses Claude Sonnet 4 when ANTHROPIC_API_KEY is set; otherwise
a rubric-based judge.

Usage:
    python eval_kr_ins.py --n-docs 7
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

# ── Paths ───────────────────────────────────────────────────────────
ROOT      = Path(__file__).resolve().parent.parent
EXTRACTED = ROOT / "암보험" / "extracted"
PRECEDENTS_PATH = ROOT / "data" / "precedents.json"
STATUTES_PATH   = ROOT / "data" / "statutes_db.json"
OUT       = Path(__file__).resolve().parent / "results"
OUT.mkdir(parents=True, exist_ok=True)


# ── Env loader ──────────────────────────────────────────────────────
def _load_env_local() -> None:
    for p in [ROOT / ".env.local", Path(__file__).parent / ".env.local"]:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())
            return


_load_env_local()
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


# ── /analyze-txt subprocess driver (real refined harness) ──────────
def run_analyze_txt(doc_relpath: str, age: int = 55, occupation: str = "직장인",
                    conditions: str = "고혈압", timeout: int = 900) -> dict:
    """Invoke `claude --print /analyze-txt <doc>` and return the captured
    workspace/session_*/vulnerability_drafts.json content (or {}).
    Slash command writes per-session workspace; we pick the latest session."""
    cmd_prompt = (
        f"/analyze-txt {doc_relpath} "
        f"--age {age} --occupation {occupation} --conditions {conditions}"
    )
    print(f"    [claude CLI] {cmd_prompt}", flush=True)

    t0 = time.time()
    proc = subprocess.run(
        ["claude", "--print", "--output-format", "json",
         "--allowedTools", "Read Write Edit Bash Grep Glob Task"],
        input=cmd_prompt,
        cwd=str(ROOT),
        capture_output=True, text=True, encoding="utf-8",
        timeout=timeout,
    )
    elapsed = round(time.time() - t0, 1)
    print(f"    [claude CLI] returncode={proc.returncode}  elapsed={elapsed}s", flush=True)
    if proc.returncode != 0:
        return {"_error": proc.stderr[:500], "_elapsed_sec": elapsed}

    # Find most recent session_* dir under workspace/
    ws = ROOT / "workspace"
    sessions = sorted([p for p in ws.iterdir() if p.is_dir() and p.name.startswith("session_")],
                      key=lambda p: p.stat().st_mtime, reverse=True)
    if not sessions:
        return {"_error": "no session dir created", "_elapsed_sec": elapsed}
    latest = sessions[0]
    drafts_path = latest / "vulnerability_drafts.json"
    if not drafts_path.exists():
        return {"_error": f"no vulnerability_drafts.json in {latest.name}",
                "_elapsed_sec": elapsed}

    drafts = json.loads(drafts_path.read_text(encoding="utf-8"))
    drafts["_elapsed_sec"] = elapsed
    drafts["_session_dir"] = latest.name
    return drafts


def normalize_finding(v: dict) -> dict:
    """Map slash-command schema (vuln_id like 'INS-02-001') to flat finding shape."""
    vuln_id = v.get("vuln_id", "") or v.get("id", "")
    tax = vuln_id.split("-")[:2] if "-" in vuln_id else []
    taxonomy = "-".join(tax) if len(tax) == 2 else vuln_id
    return {
        "taxonomy": taxonomy if taxonomy.startswith("INS-") else "UNCATEGORIZED",
        "triggered_by": v.get("triggered_by", "")[:300],
        "retrieval_query": v.get("retrieval_query", ""),
        "vuln_name": v.get("vuln_name", ""),
        "confidence": v.get("confidence", 0.0),
    }


# ── KR insurance taxonomy: INS-01..INS-05 ──────────────────────────
INS_TAXONOMY = {
    "INS-01": {
        "name": "보험금 지급 제한 및 부당 거절",
        "keywords": [
            "지급하지 아니합니다", "지급하지 않습니다", "지급하지 아니한다",
            "보상하지 아니합니다", "지급제한", "부지급",
            "최초 1회에 한", "1회의 진단확정에 한",
        ],
    },
    "INS-02": {
        "name": "고지의무 위반 면책 남용",
        "keywords": [
            "고지의무", "알릴 의무", "계약을 해지할 수", "중요한 사항",
            "사실과 다르게", "보장을 제한",
        ],
    },
    "INS-03": {
        "name": "면책조항 / 보장개시 조건 불명확 (대기기간)",
        "keywords": [
            "보장개시일", "면책기간", "대기기간",
            "90일이 지난", "30일이 지난날", "1년 미만",
        ],
    },
    "INS-04": {
        "name": "계약 해지·취소 소비자 불리",
        "keywords": [
            "청약 철회", "계약을 취소", "계약이 무효",
            "5년 이내", "사기의사", "계약 전 알릴",
        ],
    },
    "INS-05": {
        "name": "해약환급금 부당 삭감 / 미지급형",
        "keywords": [
            "해약환급금", "미지급형", "환급률",
            "납입한 보험료보다 적", "납입기간 이내에 해지",
            "해약공제",
        ],
    },
}

VULN_KEYWORDS_FLAT = [
    kw for v in INS_TAXONOMY.values() for kw in v["keywords"]
]


# ── Tokenization (Korean) / TF-IDF helpers ─────────────────────────
def tokenize(text: str) -> list[str]:
    """Hangul + ASCII alphanum tokens of length >= 2."""
    return re.findall(r"[가-힣a-zA-Z0-9]{2,}", text.lower())


def build_idf(corpus: list[str]) -> dict[str, float]:
    N = len(corpus)
    df: dict[str, int] = defaultdict(int)
    for doc in corpus:
        for t in set(tokenize(doc)):
            df[t] += 1
    return {t: math.log((N + 1) / (df[t] + 1)) + 1 for t in df}


def tfidf_vec(text: str, idf: dict[str, float]) -> dict[str, float]:
    tokens = tokenize(text)
    tf: dict[str, int] = defaultdict(int)
    for t in tokens:
        tf[t] += 1
    total = len(tokens) or 1
    return {t: (c / total) * idf.get(t, 1.0) for t, c in tf.items()}


def cosine(v1: dict[str, float], v2: dict[str, float]) -> float:
    keys = set(v1) & set(v2)
    if not keys:
        return 0.0
    dot = sum(v1[k] * v2[k] for k in keys)
    n1 = math.sqrt(sum(x * x for x in v1.values()))
    n2 = math.sqrt(sum(x * x for x in v2.values()))
    return dot / (n1 * n2) if n1 * n2 > 0 else 0.0


# ── E1: Preprocessing strategies (Korean) ──────────────────────────
def strategy_raw(txt: str) -> str:
    return txt


def strategy_ours(txt: str) -> str:
    """Rule-based filter for Korean 상품요약서 boilerplate.
    Adapted from eval_KR/e1_preprocessing_txt.py:strategy_ours.
    """
    noise_patterns = [
        # 사내 내부 표시
        r"\[.{1,20}[–\-]\s*INTERNAL\].*?\n",
        # 반복 면책 고지
        r"이\s*상품요약서는.{0,300}참조하시기\s*바랍니다\.?",
        r"보험은\s*은행의\s*저축과\s*달리.{0,300}없을\s*수도\s*있습니다\.?",
        # 적용이율/위험률 개념 설명
        r"적용이율이란,.{0,400}보험료는\s*올라갑니다\.?",
        r"적용위험률이란,.{0,400}보험료는\s*내려갑니다\.?",
        # 계약자 배당 설명
        r"계약자배당이란,.{0,500}장기유지특별배당이\s*있습니다\.?",
        r"계약자\s*배당은\s*배당상품에.{0,300}배당을\s*하지\s*않습니다\.?",
        # 계약체결비용 설명
        r"계약체결비용\s*및\s*계약관리비용이란,.{0,300}것을\s*말합니다\.?",
        # 보험가격지수 설명
        r"해당상품의\s*보험료총액.{0,500}보험가격지수.*?합니다\.?",
        # 페이지 구분선
        r"[━=─\-]{4,}\n",
        # 페이지 헤더 [ 페이지 N / M ]
        r"\[\s*페이지\s+\d+\s*/\s*\d+\s*\]\n",
        # ▶ 텍스트 / ▶ 표 N 마커
        r"▶\s*(?:텍스트|표\s+\d+)[^\n]*\n",
        # 표 테두리만 있는 라인
        r"^\s*[+|]\s*[-+|]{3,}\s*[+|]\s*\n",
    ]
    clean = txt
    for p in noise_patterns:
        clean = re.sub(p, "\n", clean, flags=re.DOTALL | re.MULTILINE)

    # 표 내 텍스트 보존: | 텍스트 | → 텍스트 (조항 내용 있는 행만)
    def clean_table_row(m):
        content = m.group(0)
        cells = re.split(r"\|", content)
        texts = [c.strip() for c in cells if c.strip()
                 and not re.fullmatch(r"[-+\s]+", c.strip())]
        return " ".join(texts) + "\n" if texts else ""

    clean = re.sub(r"^\|.*\|$", clean_table_row, clean, flags=re.MULTILINE)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    clean = re.sub(r" {3,}", " ", clean)
    return clean.strip()


def strategy_textrank(txt: str, sentence_count: int = 50) -> str:
    """Pure-Python TextRank, Korean-friendly."""
    sent_pattern = re.compile(r"(?<=[다요니까])\.\s+|(?<=[다요니까])\n+|\n{2,}")
    raw_sents = sent_pattern.split(txt)
    sentences = [s.strip() for s in raw_sents if len(s.strip()) > 10]
    if len(sentences) <= sentence_count:
        return txt

    def sent_vec(s: str) -> dict[str, float]:
        tokens = tokenize(s)
        tf: dict[str, int] = defaultdict(int)
        for t in tokens:
            tf[t] += 1
        total = len(tokens) or 1
        return {t: c / total for t, c in tf.items()}

    vecs = [sent_vec(s) for s in sentences]
    n = len(sentences)

    graph = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                graph[i][j] = cosine(vecs[i], vecs[j])
    for i in range(n):
        row_sum = sum(graph[i]) or 1.0
        graph[i] = [v / row_sum for v in graph[i]]

    d = 0.85
    scores = [1.0 / n] * n
    for _ in range(30):
        new_s = [(1 - d) / n] * n
        for j in range(n):
            for i in range(n):
                new_s[j] += d * graph[i][j] * scores[i]
        scores = new_s

    ranked = sorted(range(n), key=lambda i: -scores[i])
    top_idx = sorted(ranked[:sentence_count])
    return "\n".join(sentences[i] for i in top_idx)


def measure_e1(original: str, compressed: str, idf: dict[str, float]) -> dict:
    orig_tok = len(original.split())
    comp_tok = len(compressed.split())
    kw_hit = sum(1 for kw in VULN_KEYWORDS_FLAT if kw in compressed)
    kw_recall = kw_hit / len(VULN_KEYWORDS_FLAT)
    sem_sim = cosine(tfidf_vec(original, idf), tfidf_vec(compressed, idf))
    return {
        "orig_tokens": orig_tok,
        "comp_tokens": comp_tok,
        "compression_rate": round(comp_tok / orig_tok, 4) if orig_tok else 1.0,
        "keyword_recall": round(kw_recall, 4),
        "semantic_sim": round(sem_sim, 4),
    }


# ── Claude API helper ───────────────────────────────────────────────
def call_claude(prompt: str, max_tokens: int = 1000,
                model: str = "claude-sonnet-4-20250514") -> str:
    if not ANTHROPIC_KEY:
        return ""
    payload = json.dumps({
        "model": model, "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
            return data["content"][0]["text"]
    except Exception as e:
        print(f"  [Claude API] {e}")
        return ""


# ── E2: Input format configurations (Korean) ───────────────────────
TAXONOMY_BLOCK = """\
취약점 유형 (한국 보험 약관):
- INS-01: 보험금 지급 제한 및 부당 거절
- INS-02: 고지의무 위반 면책 남용
- INS-03: 면책·보장개시 조건 불명확 (대기기간 등)
- INS-04: 계약 해지·취소 소비자 불리
- INS-05: 해약환급금 부당 삭감 / 미지급형
"""

FEW_SHOT_BLOCK = """\
[예시 1]
조항: "해약환급금 미지급형은 납입기간 이내 해지 시 해약환급금을 지급하지 않습니다."
→ [{"taxonomy": "INS-05", "triggered_by": "해약환급금 미지급형은 납입기간 이내 해지 시 해약환급금을 지급하지 않습니다."}]

[예시 2]
조항: "중요한 사항에 대하여 사실과 다르게 알린 경우 계약을 해지할 수 있습니다."
→ [{"taxonomy": "INS-02", "triggered_by": "중요한 사항에 대하여 사실과 다르게 알린 경우 계약을 해지할 수 있습니다."}]

[예시 3]
조항: "암 보장개시일은 계약일부터 그 날을 포함하여 90일이 지난날의 다음날로 합니다."
→ [{"taxonomy": "INS-03", "triggered_by": "암 보장개시일은 계약일부터 그 날을 포함하여 90일이 지난날의 다음날로 합니다."}]
"""

CONSUMER_PROFILE = """\
사용자 프로필:
- 나이: 55세
- 기존 병력: 고혈압
- 직업: 직장인
- 가입 특약: 암진단특약
"""

OURS_SYSTEM_BLOCK = TAXONOMY_BLOCK + "\n" + CONSUMER_PROFILE + """
작업: 위 약관 텍스트에서 소비자에게 불리한 취약점을 모두 탐지하세요.
프로필을 고려해 심각도를 평가하세요. 각 finding마다:
  - taxonomy (INS-01..05)
  - triggered_by (원문 ≤300자)
  - retrieval_query (≤80자, 한국어)
JSON 배열로만 답하세요. 없으면 [].
"""

OURS_NO_REFINE_BLOCK = TAXONOMY_BLOCK + """
작업: 소비자에 불리한 조항 탐지. JSON 배열 {taxonomy, triggered_by}.
"""

MAX_TXT = 12000


def build_e2_prompt(fmt: str, raw_txt: str, prep_txt: str) -> str:
    body_raw = raw_txt[:MAX_TXT]
    body_prep = prep_txt[:MAX_TXT]
    if fmt == "text_raw":
        return f"{TAXONOMY_BLOCK}\n소비자 불리 조항을 탐지하세요. JSON 배열.\n\n[약관]\n{body_raw}"
    if fmt == "few_shot":
        return f"{TAXONOMY_BLOCK}\n{FEW_SHOT_BLOCK}\n소비자 불리 조항을 탐지하세요. JSON 배열.\n\n[약관]\n{body_raw}"
    if fmt == "ours_no_preprocess":
        return f"{OURS_SYSTEM_BLOCK}\n\n[약관]\n{body_raw}"
    if fmt == "ours":
        return f"{OURS_SYSTEM_BLOCK}\n\n[약관]\n{body_prep}"
    if fmt == "ours_no_refine":
        return f"{OURS_NO_REFINE_BLOCK}\n\n[약관]\n{body_prep}"
    raise ValueError(fmt)


def parse_findings(raw: str) -> list[dict]:
    if not raw:
        return []
    m = re.search(r"\[[\s\S]*\]", raw)
    if not m:
        return []
    try:
        parsed = json.loads(m.group(0))
        if isinstance(parsed, list):
            return [p for p in parsed if isinstance(p, dict)]
    except Exception:
        return []
    return []


def rubric_score(findings: list[dict]) -> dict[str, float]:
    n = len(findings)
    if n == 0:
        return {"Trig": 1.0, "Desc": 1.0, "Query": 1.0, "Cov": 1.0}
    trig_lens = [len(f.get("triggered_by", "")) for f in findings]
    mean_trig = sum(trig_lens) / n
    trig = min(5.0, 1.0 + mean_trig / 50)
    desc_hits = sum(1 for f in findings
                    if f.get("taxonomy", "").startswith("INS-")
                    and f.get("triggered_by", ""))
    desc = 1.0 + 4.0 * (desc_hits / max(n, 1))
    query_hits = sum(1 for f in findings
                     if 5 <= len(f.get("retrieval_query", "")) <= 120)
    query = 1.0 + 4.0 * (query_hits / max(n, 1))
    distinct = {f.get("taxonomy", "") for f in findings if f.get("taxonomy", "").startswith("INS-")}
    cov = 1.0 + 4.0 * (len(distinct) / 5.0)
    return {
        "Trig":  round(min(trig, 5.0), 2),
        "Desc":  round(min(desc, 5.0), 2),
        "Query": round(min(query, 5.0), 2),
        "Cov":   round(min(cov, 5.0), 2),
    }


def claude_judge_e2(doc_excerpt: str, findings: list[dict]) -> dict[str, float] | None:
    if not ANTHROPIC_KEY:
        return None
    prompt = f"""당신은 한국 보험 약관 전문가로 추출기의 결과를 4개 기준으로 채점합니다.
각 기준 1-5점 (5=최고):

1. Trig (triggered-by fidelity): 원문 발췌가 약관에 충실한가?
2. Desc (description quality): taxonomy 분류가 일관적인가?
3. Query (retrieval-query quality): 판례 검색에 적합한 쿼리인가?
4. Cov (coverage): INS-01..05 중 약관에 실제 존재하는 취약점을 얼마나 잘 덮었나?

JSON으로만 답:
{{"Trig": 4, "Desc": 4, "Query": 3, "Cov": 4}}

[약관 발췌]
{doc_excerpt[:6000]}

[추출 결과]
{json.dumps(findings, ensure_ascii=False, indent=2)[:4000]}
"""
    raw = call_claude(prompt, max_tokens=200)
    m = re.search(r"\{[^{}]*\}", raw)
    if not m:
        return None
    try:
        parsed = json.loads(m.group(0))
        return {k: float(parsed.get(k, 0)) for k in ("Trig", "Desc", "Query", "Cov")}
    except Exception:
        return None


# ── law.go.kr live precedent fetch (per-query candidate pool) ──────
LAWGOKR_OC = "dlwlsdnr2"
LAWGOKR_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
LAWGOKR_EXCLUDE = ["취득세", "증여세", "상속세", "양도세", "명의신탁", "조세",
                    "과세", "국세", "근로", "임금", "해고", "행정처분",
                    "공정거래", "보이스피싱"]
TAX_QUERY = {
    "INS-01": "보험금 지급제한 면책",
    "INS-02": "고지의무 위반 보험계약 해지",
    "INS-03": "보장개시일 대기기간 약관해석",
    "INS-04": "청약철회 보험계약 취소",
    "INS-05": "해약환급금 환급률",
}


def _lawgokr_get(url: str, params: dict, retries: int = 3,
                 delay: float = 1.5):
    try:
        import requests
    except ImportError:
        return None
    for i in range(retries):
        try:
            r = requests.get(url, params=params, headers=LAWGOKR_HEADERS,
                             timeout=12)
            r.raise_for_status()
            return r
        except Exception as e:
            print(f"    [law.go.kr retry {i+1}/{retries}] {e}", flush=True)
            time.sleep(delay * (i + 1))
    return None


def _lawgokr_search(query: str, display: int = 20) -> list[dict]:
    r = _lawgokr_get(
        "https://www.law.go.kr/DRF/lawSearch.do",
        {"OC": LAWGOKR_OC, "target": "prec", "type": "JSON",
         "query": query, "display": display, "sort": "ddes"})
    if not r:
        return []
    try:
        prec = r.json().get("PrecSearch", {}).get("prec", [])
        if isinstance(prec, dict):
            prec = [prec]
        return prec if isinstance(prec, list) else []
    except Exception:
        return []


def _lawgokr_detail(prec_id: str) -> dict:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {}
    r = _lawgokr_get(
        "https://www.law.go.kr/DRF/lawService.do",
        {"OC": LAWGOKR_OC, "target": "prec", "ID": prec_id, "type": "XML"})
    if not r:
        return {}
    try:
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "xml")

        def txt(tag):
            el = soup.find(tag)
            return re.sub(r"\s+", " ", el.get_text(separator=" ")).strip() if el else ""

        return {
            "사건번호": txt("사건번호"), "사건명": txt("사건명"),
            "법원명":   txt("법원명"),   "선고일자": txt("선고일자"),
            "판시사항": txt("판시사항"), "판결요지": txt("판결요지"),
        }
    except Exception:
        return {}


def fetch_lawgokr_candidates(query: str, display: int = 20,
                              fetch_detail: bool = True) -> list[dict]:
    """Live fetch candidate precedents from law.go.kr for a single query."""
    metas = _lawgokr_search(query, display=display)
    candidates: list[dict] = []
    seen: set[str] = set()
    for meta in metas:
        case_num = (meta.get("사건번호", "") or "").strip()
        prec_id = (meta.get("판례일련번호", "") or "").strip()
        if not case_num or case_num in seen:
            continue
        # civil-law cases only (filters out tax, criminal, admin noise)
        if meta.get("사건종류명", "") not in ("민사", ""):
            continue
        if fetch_detail and prec_id:
            time.sleep(0.5)
            raw = _lawgokr_detail(prec_id)
        else:
            raw = {}
        subject = raw.get("사건명") or meta.get("사건명", "")
        if not subject:
            continue
        full = (raw.get("판시사항", "") + " " + raw.get("판결요지", "")).strip()
        text = subject + " " + full
        if any(kw in text for kw in LAWGOKR_EXCLUDE):
            continue
        candidates.append({
            "case_number": case_num,
            "court":       raw.get("법원명", meta.get("법원명", "")),
            "date":        raw.get("선고일자", meta.get("선고일자", "")),
            "subject":     subject,
            "text":        (full or subject)[:1500],
            "source":      "law.go.kr",
        })
        seen.add(case_num)
    return candidates


# ── E3: Retrieval against precedents.json ──────────────────────────
def load_precedents() -> list[dict]:
    prec = json.loads(PRECEDENTS_PATH.read_text(encoding="utf-8"))
    if isinstance(prec, dict):
        prec = prec.get("precedents", []) or []
    pool = []
    for p in prec:
        text = " ".join([
            p.get("subject", ""), p.get("summary", ""),
            " ".join(p.get("keywords", []) or []),
        ]).strip()
        if not text:
            continue
        pool.append({
            "case_number": p.get("case_number", ""),
            "court":       p.get("court", ""),
            "date":        p.get("date", ""),
            "subject":     p.get("subject", ""),
            "summary":     p.get("summary", ""),
            "tags":        p.get("vuln_tags", []) or [],
            "text":        text,
        })
    return pool


def extract_queries(sample_docs: dict[str, str], per_doc: int = 3) -> list[dict]:
    """For each sampled doc, extract a few triggered-by clauses + INS taxonomy."""
    queries: list[dict] = []
    for name, txt in sample_docs.items():
        seen_per_doc = 0
        for tax_id, info in INS_TAXONOMY.items():
            if seen_per_doc >= per_doc:
                break
            for kw in info["keywords"]:
                pat = re.compile(r"[^.\n]{20,300}" + re.escape(kw) + r"[^.\n]{0,200}[.\n]")
                m = pat.search(txt)
                if m:
                    snippet = m.group(0).strip()
                    queries.append({
                        "doc": name,
                        "query_id": f"{name}#{tax_id}",
                        "taxonomy": tax_id,
                        "triggered_by": snippet[:280],
                        "retrieval_query": f"{info['name']} {kw}",
                    })
                    seen_per_doc += 1
                    break
    return queries


def bm25_scores(query_tokens: list[str], docs_tokens: list[list[str]]) -> list[float]:
    try:
        from rank_bm25 import BM25Okapi
        bm = BM25Okapi(docs_tokens)
        return bm.get_scores(query_tokens).tolist()
    except Exception:
        q_set = set(query_tokens)
        return [
            sum(1 for t in d if t in q_set) / max(len(d), 1)
            for d in docs_tokens
        ]


def retrieve(method: str, query: dict, pool: list[dict], top_k: int = 5) -> list[dict]:
    q_text = query["retrieval_query"] + " " + query["triggered_by"]
    q_tokens = tokenize(q_text)
    docs_tokens = [tokenize(c["text"]) for c in pool]

    if method == "BM25":
        scores = bm25_scores(q_tokens, docs_tokens)
    elif method == "TF-IDF":
        idf = build_idf([c["text"] for c in pool] + [q_text])
        q_v = tfidf_vec(q_text, idf)
        scores = [cosine(q_v, tfidf_vec(c["text"], idf)) for c in pool]
    elif method == "Emb":
        try:
            from sentence_transformers import SentenceTransformer, util as st_util
            model = SentenceTransformer("all-MiniLM-L6-v2")
            q_emb = model.encode(q_text, convert_to_tensor=True)
            doc_emb = model.encode([c["text"] for c in pool], convert_to_tensor=True)
            scores = st_util.cos_sim(q_emb, doc_emb)[0].tolist()
        except Exception:
            idf = build_idf([c["text"] for c in pool] + [q_text])
            q_v = tfidf_vec(q_text, idf)
            scores = [cosine(q_v, tfidf_vec(c["text"], idf)) for c in pool]
    elif method == "Hybrid":
        s_bm = bm25_scores(q_tokens, docs_tokens)
        idf = build_idf([c["text"] for c in pool] + [q_text])
        q_v = tfidf_vec(q_text, idf)
        s_tf = [cosine(q_v, tfidf_vec(c["text"], idf)) for c in pool]
        rank_bm = {i: r for r, (i, _) in enumerate(sorted(enumerate(s_bm), key=lambda x: -x[1]))}
        rank_tf = {i: r for r, (i, _) in enumerate(sorted(enumerate(s_tf), key=lambda x: -x[1]))}
        scores = [1.0 / (60 + rank_bm[i] + 1) + 1.0 / (60 + rank_tf[i] + 1)
                  for i in range(len(pool))]
    elif method == "Ours":
        # Multi-query expansion over taxonomy synonyms + MMR rerank
        expanded = q_text + " " + " ".join(INS_TAXONOMY[query["taxonomy"]]["keywords"])
        eq_tokens = tokenize(expanded)
        s_bm = bm25_scores(eq_tokens, docs_tokens)
        order = sorted(range(len(pool)), key=lambda i: -s_bm[i])[:min(20, len(pool))]
        idf = build_idf([c["text"] for c in pool] + [expanded])
        chosen: list[int] = []
        chosen_vecs: list[dict[str, float]] = []
        while order and len(chosen) < top_k:
            best_i, best_score = order[0], -1.0
            for i in order:
                rel = s_bm[i] / (max(s_bm) or 1.0)
                if not chosen_vecs:
                    mmr = rel
                else:
                    v = tfidf_vec(pool[i]["text"], idf)
                    div = max(cosine(v, cv) for cv in chosen_vecs)
                    mmr = 0.7 * rel - 0.3 * div
                if mmr > best_score:
                    best_score, best_i = mmr, i
            chosen.append(best_i)
            chosen_vecs.append(tfidf_vec(pool[best_i]["text"], idf))
            order.remove(best_i)
        return [{**pool[i], "score": round(s_bm[i], 4)} for i in chosen]
    else:
        raise ValueError(method)

    order = sorted(range(len(pool)), key=lambda i: -scores[i])[:top_k]
    return [{**pool[i], "score": round(float(scores[i]), 4)} for i in order]


def relevant(query: dict, retrieved: dict) -> bool:
    """Precedent is relevant if its vuln_tags includes the query's taxonomy."""
    return query["taxonomy"] in (retrieved.get("tags") or [])


def e3_metrics(flags_per_query: list[list[bool]], ks=(1, 3, 5)) -> dict[str, float]:
    if not flags_per_query:
        return {}
    mrr_vals = []
    for flags in flags_per_query:
        mrr = next((1.0 / (i + 1) for i, f in enumerate(flags) if f), 0.0)
        mrr_vals.append(mrr)
    out: dict[str, float] = {"MRR": round(sum(mrr_vals) / len(mrr_vals), 4)}
    for k in ks:
        p_at_k = sum(sum(flags[:k]) / k for flags in flags_per_query) / len(flags_per_query)
        r_at_k = sum(1.0 if any(flags[:k]) else 0.0 for flags in flags_per_query) / len(flags_per_query)
        out[f"P@{k}"] = round(p_at_k, 4)
        out[f"R@{k}"] = round(r_at_k, 4)
    return out


# ── Main ────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-docs", type=int, default=7)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-api", action="store_true")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--skip-slashcmd", action="store_true",
                    help="Skip real /analyze-txt subprocess; use direct Claude prompt for 'ours' instead.")
    args = ap.parse_args()

    use_api = (not args.no_api) and bool(ANTHROPIC_KEY)

    # ── Load corpus from 암보험/extracted ──
    print(f"[*] Loading KR insurance TXT from {EXTRACTED}")
    all_docs: dict[str, str] = {}
    for path in sorted(EXTRACTED.glob("*.txt")):
        try:
            all_docs[path.name] = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"    skip {path.name}: {e}")
    print(f"    loaded {len(all_docs)} 암보험 docs")

    random.seed(args.seed)
    sample_names = sorted(random.sample(sorted(all_docs.keys()), args.n_docs))
    sample_docs = {n: all_docs[n] for n in sample_names}
    print(f"[*] Sampled {len(sample_names)} docs (seed={args.seed}):")
    for n in sample_names:
        print(f"      {n}  ({len(all_docs[n]):,} chars)")

    # ── E1: Preprocessing ──
    print("\n========== E1: Preprocessing fidelity ==========")
    idf_corpus = list(sample_docs.values())
    idf = build_idf(idf_corpus)

    strategies = [
        ("Raw", strategy_raw),
        ("TextRank", strategy_textrank),
        ("Ours", strategy_ours),
    ]

    e1_per_doc: dict[str, dict[str, dict]] = {n: {} for n in sample_names}
    e1_agg: dict[str, list[dict]] = {s: [] for s, _ in strategies}

    for strat_name, strat_fn in strategies:
        print(f"\n  [{strat_name}] ", end="", flush=True)
        for name in sample_names:
            raw = sample_docs[name]
            t0 = time.time()
            compressed = strat_fn(raw)
            m = measure_e1(raw, compressed, idf)
            m["elapsed_sec"] = round(time.time() - t0, 2)
            e1_per_doc[name][strat_name] = m
            e1_agg[strat_name].append(m)
            print(".", end="", flush=True)
        print()

    e1_summary: dict[str, dict[str, float]] = {}
    for strat_name, rows in e1_agg.items():
        if not rows:
            continue
        e1_summary[strat_name] = {
            "compression_rate": round(sum(r["compression_rate"] for r in rows) / len(rows), 4),
            "keyword_recall":   round(sum(r["keyword_recall"]   for r in rows) / len(rows), 4),
            "semantic_sim":     round(sum(r["semantic_sim"]     for r in rows) / len(rows), 4),
            "n_docs": len(rows),
        }

    print("\n  ─── E1 summary (means across docs) ───")
    print(f"  {'Strategy':<10} {'Comp':>8} {'KW Rec':>9} {'Sem Sim':>10}")
    for strat_name, m in e1_summary.items():
        print(f"  {strat_name:<10} {m['compression_rate']:>8.4f} "
              f"{m['keyword_recall']:>9.4f} {m['semantic_sim']:>10.4f}")

    # ── E2: Input format ──
    print("\n========== E2: Vulnerability detection input format ==========")
    print(f"  Claude API: {'enabled' if use_api else 'DISABLED (rubric judge)'}")
    formats = [
        "zero_shot",
        "text_raw",
        "few_shot",
        "ours_no_preprocess",
        "ours",
        "ours_no_refine",
    ]
    e2_per_doc: dict[str, dict[str, dict]] = {n: {} for n in sample_names}
    e2_agg: dict[str, list[dict]] = {f: [] for f in formats}

    # Pre-compute "ours" findings ONCE per doc by invoking the real
    # /analyze-txt slash command (refined harness).
    ours_findings_by_doc: dict[str, list[dict]] = {}
    if use_api and not args.skip_slashcmd:
        print("\n  -- pre-computing 'ours' via /analyze-txt slash command --")
        for name in sample_names:
            doc_relpath = f"암보험/extracted/{name}"
            drafts = run_analyze_txt(doc_relpath)
            if drafts.get("_error"):
                print(f"    [{name[:40]}] /analyze-txt FAILED: {drafts['_error']}")
                ours_findings_by_doc[name] = []
            else:
                findings = [normalize_finding(v) for v in drafts.get("vulnerabilities", [])]
                ours_findings_by_doc[name] = findings
                # Save captured per-doc artifacts
                cap = OUT / f"ours_drafts_{name[:50].replace('/', '_')}.json"
                cap.write_text(json.dumps(drafts, ensure_ascii=False, indent=2),
                               encoding="utf-8")

    for name in sample_names:
        raw_txt = sample_docs[name]
        prep_txt = strategy_ours(raw_txt)
        for fmt in formats:
            if fmt == "zero_shot":
                e2_per_doc[name][fmt] = {"n_findings": 0, "Trig": 0.0,
                                          "Desc": 0.0, "Query": 0.0,
                                          "Cov": 0.0, "skipped": True}
                continue

            prompt = build_e2_prompt(fmt, raw_txt, prep_txt)
            print(f"  [{name[:30]:<30}] {fmt:<20}", end=" ", flush=True)
            if use_api:
                if fmt == "ours" and name in ours_findings_by_doc:
                    # Use real refined-harness findings from /analyze-txt
                    findings = ours_findings_by_doc[name]
                    judge_scores = claude_judge_e2(prep_txt, findings)
                    if judge_scores is None:
                        judge_scores = rubric_score(findings)
                else:
                    raw_resp = call_claude(prompt, max_tokens=1500)
                    findings = parse_findings(raw_resp)
                    judge_scores = claude_judge_e2(prep_txt, findings)
                    if judge_scores is None:
                        judge_scores = rubric_score(findings)
                time.sleep(0.4)
            else:
                findings = []
                for tax_id, info in INS_TAXONOMY.items():
                    for kw in info["keywords"]:
                        m = re.search(r"[^.\n]{20,300}" + re.escape(kw) + r"[^.\n]{0,200}[.\n]",
                                       prep_txt if fmt == "ours" else raw_txt)
                        if m:
                            findings.append({
                                "taxonomy": tax_id,
                                "triggered_by": m.group(0).strip()[:280],
                                "retrieval_query": f"{info['name']} {kw}",
                            })
                            break
                if fmt in ("text_raw", "ours_no_refine"):
                    findings = findings[:2]
                if fmt == "ours_no_preprocess":
                    findings = findings[:3]
                judge_scores = rubric_score(findings)
            print(f"n={len(findings)}  scores={judge_scores}")
            row = {"n_findings": len(findings), **judge_scores}
            row["total"] = round(sum(judge_scores.values()), 2)
            e2_per_doc[name][fmt] = row
            e2_agg[fmt].append(row)

    e2_summary: dict[str, dict[str, float]] = {}
    for fmt in formats:
        rows = [r for r in e2_agg[fmt] if not r.get("skipped")]
        if not rows:
            e2_summary[fmt] = {"Trig": None, "Desc": None, "Query": None,
                                "Cov": None, "Total": None, "n_docs": 0}
            continue
        e2_summary[fmt] = {
            "Trig":  round(sum(r["Trig"]  for r in rows) / len(rows), 2),
            "Desc":  round(sum(r["Desc"]  for r in rows) / len(rows), 2),
            "Query": round(sum(r["Query"] for r in rows) / len(rows), 2),
            "Cov":   round(sum(r["Cov"]   for r in rows) / len(rows), 2),
            "Total": round(sum(r["total"] for r in rows) / len(rows), 2),
            "n_docs": len(rows),
        }

    print("\n  ─── E2 summary (means) ───")
    print(f"  {'Format':<22} {'Trig':>6} {'Desc':>6} {'Query':>6} {'Cov':>6} {'Total':>7}")
    for fmt, m in e2_summary.items():
        if m.get("Trig") is None:
            print(f"  {fmt:<22} {'--':>6} {'--':>6} {'--':>6} {'--':>6} {'--/20':>7}")
        else:
            print(f"  {fmt:<22} {m['Trig']:>6.2f} {m['Desc']:>6.2f} "
                  f"{m['Query']:>6.2f} {m['Cov']:>6.2f} {m['Total']:>6.2f}/20")

    # ── E3: Retrieval ──
    print("\n========== E3: Retrieval quality (law.go.kr precedents) ==========")
    pool = load_precedents()
    print(f"  candidate pool: {len(pool)} KR precedents")
    queries = extract_queries(sample_docs, per_doc=3)
    print(f"  queries:        {len(queries)} (covenant clauses from sampled docs)")
    if not queries or not pool:
        print("  [skip] insufficient queries or pool")
        e3_summary = {}
    else:
        methods = ["BM25", "TF-IDF", "Emb", "Hybrid", "Ours"]
        e3_agg: dict[str, list[list[bool]]] = {m: [] for m in methods}
        for q in queries:
            print(f"  [{q['query_id'][:55]:<55}] ", end="")
            for method in methods:
                retrieved = retrieve(method, q, pool, top_k=args.top_k)
                flags = [relevant(q, r) for r in retrieved]
                e3_agg[method].append(flags)
                print(f"{method[:3]}={sum(flags[:3])}", end=" ")
            print()
        e3_summary = {m: e3_metrics(e3_agg[m]) for m in methods}

        print("\n  ─── E3 summary ───")
        print(f"  {'Method':<10} {'MRR':>6} {'P@1':>6} {'R@1':>6} "
              f"{'P@3':>6} {'R@3':>6} {'R@5':>6}")
        for method, m in e3_summary.items():
            print(f"  {method:<10} {m.get('MRR', 0):>6.4f} {m.get('P@1', 0):>6.4f} "
                  f"{m.get('R@1', 0):>6.4f} {m.get('P@3', 0):>6.4f} "
                  f"{m.get('R@3', 0):>6.4f} {m.get('R@5', 0):>6.4f}")

    # ── Save all results ──
    summary = {
        "domain":         "kr_insurance",
        "n_docs":         args.n_docs,
        "seed":           args.seed,
        "sample_docs":    sample_names,
        "anthropic_api":  bool(use_api),
        "e1_summary":     e1_summary,
        "e2_summary":     e2_summary,
        "e3_summary":     e3_summary,
        "e1_per_doc":     e1_per_doc,
        "e2_per_doc":     e2_per_doc,
        "taxonomy":       {k: v["name"] for k, v in INS_TAXONOMY.items()},
        "precedent_pool_size": len(load_precedents()),
    }
    out_path = OUT / "kr_ins_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\n[*] Wrote {out_path}")


if __name__ == "__main__":
    main()
