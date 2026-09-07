"""
e3_retrieval_us.py  — E3 (US): CourtListener + Claude-as-Judge

방법 13종:
  BM25 / BM25Plus / Embedding(TF-IDF) / Hybrid(RRF) /
  PRF / MMR / CourtWeight / DateDecay / CombMNZ /
  DenseEmbed(sentence-transformers) /
  HyDE / MultiQuery / SnippetExpand  (후 3개: Claude/API 추가 호출)

지표: MRR, P@1, P@2, P@3, R@3

사용법:
  python e3_retrieval_us.py --demo
  python e3_retrieval_us.py --input drafts/sample.json
  python e3_retrieval_us.py --demo --skip-expensive   # API 절약
"""

import json, re, sys, os, time, math, argparse, io, datetime
from pathlib import Path
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── env loader ───────────────────────────────────────────────────
def _load_env():
    for p in [Path(__file__).parent.parent / ".env.local", Path(".env.local")]:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())
            break

_load_env()

try:
    import requests
except ImportError:
    print("[오류] pip install requests")
    sys.exit(1)

try:
    import anthropic
    _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
except Exception:
    _client = None

_HAS_BM25 = False
try:
    from rank_bm25 import BM25Okapi, BM25Plus
    _HAS_BM25 = True
except ImportError:
    pass

_HAS_ST = False
_st_model = None
try:
    from sentence_transformers import SentenceTransformer, util as st_util
    _HAS_ST = True
except ImportError:
    pass

def _get_st_model():
    global _st_model
    if _st_model is None and _HAS_ST:
        _st_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _st_model

# ── argparse ─────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--input",          type=str)
parser.add_argument("--demo",           action="store_true")
parser.add_argument("--top-k",          type=int,   default=3)
parser.add_argument("--rrf-k",          type=int,   default=60)
parser.add_argument("--out-dir",        type=str,   default="results")
parser.add_argument("--skip-expensive", action="store_true",
                    help="HyDE/MultiQuery/SnippetExpand 스킵")
parser.add_argument("--decay-rate",     type=float, default=0.05)
parser.add_argument("--mmr-lambda",     type=float, default=0.5)
args = parser.parse_args()

OUT = Path(args.out_dir)
OUT.mkdir(parents=True, exist_ok=True)

# ── demo data ─────────────────────────────────────────────────────
DEMO_DRAFTS = {
    "product": "CFPB_Sample_CreditCard",
    "vulnerabilities": [
        {"id": "US-V001", "taxonomy": "CC-02",
         "title": "Penalty APR escalation",
         "triggered_by": "Penalty APR of 29.99% applies upon late payment",
         "retrieval_query": "credit card penalty APR late payment consumer protection"},
        {"id": "US-V002", "taxonomy": "CC-05",
         "title": "Mandatory arbitration class action waiver",
         "triggered_by": "binding arbitration, class action waiver",
         "retrieval_query": "credit card arbitration clause class action waiver unconscionable"},
        {"id": "US-V003", "taxonomy": "CC-04",
         "title": "Unilateral change in terms",
         "triggered_by": "We may change the APR, fees at any time",
         "retrieval_query": "credit card change in terms unilateral modification consumer rights"},
        {"id": "US-V004", "taxonomy": "CC-01",
         "title": "Undisclosed fee structure",
         "triggered_by": "foreign transaction fee 3%, cash advance fee 5%",
         "retrieval_query": "credit card hidden fees disclosure TILA Truth in Lending"},
    ]
}

if args.demo:
    vulns, product = DEMO_DRAFTS["vulnerabilities"], DEMO_DRAFTS["product"]
elif args.input:
    data    = json.loads(Path(args.input).read_text(encoding="utf-8"))
    vulns   = data.get("vulnerabilities", [])
    product = data.get("product", Path(args.input).stem)
else:
    print("[오류] --input 또는 --demo 필요"); sys.exit(1)

EXPENSIVE = {"HyDE", "MultiQuery", "SnippetExpand"}
ALL_METHODS = [
    "BM25", "BM25Plus", "Embedding", "Hybrid",
    "PRF", "MMR", "CourtWeight", "DateDecay", "CombMNZ",
    "DenseEmbed", "HyDE", "MultiQuery", "SnippetExpand",
]
METHODS = [m for m in ALL_METHODS if not (args.skip_expensive and m in EXPENSIVE)]

if not _HAS_BM25:
    print("[경고] rank_bm25 미설치 — pip install rank-bm25  (BM25/BM25Plus 성능 저하)")
if not _HAS_ST:
    print("[경고] sentence-transformers 미설치 — pip install sentence-transformers"
          "  (DenseEmbed → TF-IDF fallback)")
if _client is None:
    print("[경고] ANTHROPIC_API_KEY 없음 — HyDE/MultiQuery keyword fallback 사용")

print(f"상품: {product} | 취약점: {len(vulns)}개 | 방법: {len(METHODS)}개")
print(f"top_k={args.top_k} | rrf_k={args.rrf_k} | skip_expensive={args.skip_expensive}")
print("=" * 75)

# ── CourtListener API ─────────────────────────────────────────────
CL_BASE    = "https://www.courtlistener.com/api/rest/v4"
CL_API_KEY = os.environ.get("COURTLISTENER_API_KEY", "")
CL_HEADERS = {"User-Agent": "KFinLegalHarness-US-Research/1.0"}
if CL_API_KEY:
    CL_HEADERS["Authorization"] = f"Token {CL_API_KEY}"

def cl_search(query: str, n: int = 20) -> list[dict]:
    params = {"q": query, "type": "o", "order_by": "score desc",
              "stat_Precedential": "on", "count": n}
    try:
        r = requests.get(f"{CL_BASE}/search/", params=params,
                         headers=CL_HEADERS, timeout=15)
        r.raise_for_status()
        candidates = []
        for item in r.json().get("results", []):
            candidates.append({
                "case_number": item.get("docket_id", ""),
                "cluster_id":  item.get("cluster_id", ""),
                "case_name":   item.get("caseName", ""),
                "court":       item.get("court_id", ""),
                "date":        item.get("dateFiled", ""),
                "snippet":     item.get("snippet", ""),
                "_full":       item.get("caseName", "") + " " + item.get("snippet", ""),
                "source":      "courtlistener.com",
                "url":         "https://www.courtlistener.com" + item.get("absolute_url", ""),
            })
        print(f"  [CL] '{query[:45]}' → {len(candidates)}건")
        return candidates
    except Exception as e:
        print(f"  [CL 오류] {e}"); return []

def cl_fetch_opinion_text(cluster_id) -> str:
    if not cluster_id:
        return ""
    try:
        r = requests.get(f"{CL_BASE}/opinions/", params={"cluster": cluster_id},
                         headers=CL_HEADERS, timeout=15)
        r.raise_for_status()
        results = r.json().get("results", [])
        if results:
            return (results[0].get("plain_text", "")
                    or results[0].get("html_with_citations", ""))[:3000]
    except Exception as e:
        print(f"  [SnippetExpand 오류] {e}")
    return ""

# ── query preparation ─────────────────────────────────────────────
TAX_PREFIX = {
    "CC-01": "credit card fee disclosure consumer",
    "CC-02": "credit card interest rate APR consumer",
    "CC-03": "credit card billing balance payment consumer",
    "CC-04": "credit card change terms cancellation consumer",
    "CC-05": "credit card arbitration class action waiver consumer",
    "UNCATEGORIZED": "credit card consumer protection unfair practice",
}
STOPWORDS = {"the","and","for","are","you","your","any","all","our","may","will",
             "that","this","with","from","have","been","each","per","not","has",
             "its","but","use","can","shall","also","upon","which","than","such",
             "other","after","into","more","less"}

def clean_query(vuln: dict) -> str:
    tax   = vuln.get("taxonomy", "")
    raw   = vuln.get("retrieval_query", "") or vuln.get("triggered_by", "")
    words = re.findall(r"[a-zA-Z]{3,}", raw)
    kws   = list(dict.fromkeys(w.lower() for w in words if w.lower() not in STOPWORDS))[:8]
    return f"{TAX_PREFIX.get(tax, 'credit card consumer')} {' '.join(kws)}".strip()

def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z]+(?:'[a-zA-Z]+)?", text.lower())

# ── shared scoring helpers ────────────────────────────────────────

def _normalize(scores: list[float]) -> list[float]:
    m = max(scores) if scores else 0.0
    return [s / m if m > 0 else 0.0 for s in scores]

def _bm25_scores(query: str, candidates: list) -> list[float]:
    if not candidates:
        return []
    if _HAS_BM25:
        docs   = [tokenize(c["_full"]) or ["_"] for c in candidates]
        scores = list(BM25Okapi(docs).get_scores(tokenize(query) or query.split()))
    else:
        q = set(tokenize(query))
        scores = [len(q & set(tokenize(c["_full"]))) / max(len(q), 1) for c in candidates]
    return _normalize(scores)

def _bm25plus_scores(query: str, candidates: list) -> list[float]:
    if not candidates:
        return []
    if _HAS_BM25:
        docs   = [tokenize(c["_full"]) or ["_"] for c in candidates]
        scores = list(BM25Plus(docs).get_scores(tokenize(query) or query.split()))
        return _normalize(scores)
    return _bm25_scores(query, candidates)

def _tfidf_vecs(candidates: list):
    corpus = [c["_full"] for c in candidates]
    N  = len(corpus)
    df = defaultdict(int)
    for doc in corpus:
        for t in set(tokenize(doc)):
            df[t] += 1
    idf = {t: math.log((N + 1) / (df[t] + 1)) + 1 for t in df}

    def vec(text):
        tokens = tokenize(text)
        tf = defaultdict(int)
        for t in tokens:
            tf[t] += 1
        total = len(tokens) or 1
        return {t: (cnt / total) * idf.get(t, 1.0) for t, cnt in tf.items()}

    def cos(v1, v2):
        keys = set(v1) & set(v2)
        if not keys:
            return 0.0
        dot = sum(v1[k] * v2[k] for k in keys)
        n1  = math.sqrt(sum(x * x for x in v1.values()))
        n2  = math.sqrt(sum(x * x for x in v2.values()))
        return dot / (n1 * n2) if n1 * n2 > 0 else 0.0

    return vec, cos

def _tfidf_scores(query: str, candidates: list) -> list[float]:
    if not candidates:
        return []
    vec, cos = _tfidf_vecs(candidates)
    q_vec = vec(query)
    return [cos(q_vec, vec(c["_full"])) for c in candidates]

def _dense_scores(query: str, candidates: list) -> list[float]:
    if not candidates:
        return []
    model = _get_st_model()
    if model is None:
        return _tfidf_scores(query, candidates)
    q_emb  = model.encode(query, convert_to_tensor=True)
    d_embs = model.encode([c["_full"][:512] for c in candidates], convert_to_tensor=True)
    scores = st_util.cos_sim(q_emb, d_embs)[0].tolist()
    min_s  = min(scores)
    return _normalize([s - min_s for s in scores])

def _fmt(doc: dict, score: float) -> dict:
    return {k: v for k, v in doc.items() if k != "_full"} | {
        "relevance_score": round(score, 4)
    }

def _top_k(candidates: list, scores: list[float]) -> list[dict]:
    pairs  = sorted(zip(candidates, scores), key=lambda x: -x[1])[:args.top_k]
    return [_fmt(d, s) for d, s in pairs]

# ── court weight / date decay helpers ────────────────────────────

def _court_weight(court_id: str) -> float:
    if court_id == "scotus":
        return 2.0
    if re.match(r"^ca(\d{1,2}|dc|fc)$", court_id):
        return 1.5
    if re.search(r"\bd\b", court_id):  # district
        return 1.1
    return 1.0

def _date_decay(date_str: str) -> float:
    if not date_str:
        return 1.0
    try:
        d     = datetime.datetime.strptime(date_str[:10], "%Y-%m-%d")
        years = (datetime.datetime.now() - d).days / 365.25
        return math.exp(-args.decay_rate * max(years, 0))
    except Exception:
        return 1.0

# ── 13 retrieval methods ──────────────────────────────────────────

def rerank_bm25(query: str, candidates: list) -> list:
    return _top_k(candidates, _bm25_scores(query, candidates))

def rerank_bm25plus(query: str, candidates: list) -> list:
    return _top_k(candidates, _bm25plus_scores(query, candidates))

def rerank_embedding(query: str, candidates: list) -> list:
    return _top_k(candidates, _tfidf_scores(query, candidates))

def rerank_hybrid(query: str, candidates: list) -> list:
    b = rerank_bm25(query, candidates)
    e = rerank_embedding(query, candidates)
    rrf: dict = defaultdict(float)
    for rank, r in enumerate(b, 1):
        rrf[r["case_number"]] += 1.0 / (args.rrf_k + rank)
    for rank, r in enumerate(e, 1):
        rrf[r["case_number"]] += 1.0 / (args.rrf_k + rank)
    doc_map = {r["case_number"]: r for r in b + e}
    out = []
    for cn, score in sorted(rrf.items(), key=lambda x: -x[1])[:args.top_k]:
        if cn in doc_map:
            d = dict(doc_map[cn]); d["relevance_score"] = round(score, 4); out.append(d)
    return out

def rerank_prf(query: str, candidates: list) -> list:
    """Pseudo Relevance Feedback: 상위 3건 키워드로 쿼리 확장 후 재검색"""
    initial = rerank_bm25(query, candidates)
    if not initial:
        return []
    top_text = " ".join(r.get("snippet", "") + " " + r.get("case_name", "")
                        for r in initial[:3])
    q_terms = set(tokenize(query))
    freq    = defaultdict(int)
    for t in tokenize(top_text):
        if t not in q_terms and len(t) > 4:
            freq[t] += 1
    expansion     = " ".join(t for t, _ in sorted(freq.items(), key=lambda x: -x[1])[:6])
    expanded      = f"{query} {expansion}".strip()
    return _top_k(candidates, _bm25_scores(expanded, candidates))

def rerank_mmr(query: str, candidates: list) -> list:
    """Maximal Marginal Relevance: 관련성-다양성 균형"""
    if not candidates:
        return []
    vec, cos = _tfidf_vecs(candidates)
    q_vec   = vec(query)
    d_vecs  = [vec(c["_full"]) for c in candidates]
    rel_sc  = [cos(q_vec, dv) for dv in d_vecs]

    lam          = args.mmr_lambda
    selected_idx = []
    remaining    = list(range(len(candidates)))

    while len(selected_idx) < args.top_k and remaining:
        best_i, best_s = None, float("-inf")
        for i in remaining:
            max_sim = max((cos(d_vecs[i], d_vecs[j]) for j in selected_idx), default=0.0)
            score   = lam * rel_sc[i] - (1 - lam) * max_sim
            if score > best_s:
                best_s, best_i = score, i
        if best_i is None:
            break
        selected_idx.append(best_i)
        remaining.remove(best_i)

    return [_fmt(candidates[i], rel_sc[i]) for i in selected_idx]

def rerank_court_weight(query: str, candidates: list) -> list:
    """BM25 × 법원 레벨 가중치 (SCOTUS 2×, Circuit 1.5×, District 1.1×)"""
    bm25   = _bm25_scores(query, candidates)
    scores = [b * _court_weight(c.get("court", "")) for b, c in zip(bm25, candidates)]
    return _top_k(candidates, _normalize(scores))

def rerank_date_decay(query: str, candidates: list) -> list:
    """BM25 × 날짜 감쇠 (최신 판례 우대, λ=--decay-rate)"""
    bm25   = _bm25_scores(query, candidates)
    decay  = [_date_decay(c.get("date", "")) for c in candidates]
    return _top_k(candidates, _normalize([b * d for b, d in zip(bm25, decay)]))

def rerank_combmnz(query: str, candidates: list) -> list:
    """CombMNZ: (BM25 + BM25Plus + TF-IDF 합산) × 히트 방법 수"""
    if not candidates:
        return []
    s1, s2, s3 = (_bm25_scores(query, candidates),
                  _bm25plus_scores(query, candidates),
                  _tfidf_scores(query, candidates))
    thresh   = 0.01
    combined = []
    for i in range(len(candidates)):
        total = s1[i] + s2[i] + s3[i]
        hits  = sum(1 for s in (s1[i], s2[i], s3[i]) if s > thresh)
        combined.append(total * hits)
    return _top_k(candidates, _normalize(combined))

def rerank_dense_embed(query: str, candidates: list) -> list:
    """sentence-transformers all-MiniLM-L6-v2; TF-IDF fallback"""
    return _top_k(candidates, _dense_scores(query, candidates))

# ── expensive methods ─────────────────────────────────────────────

_HYDE_CACHE: dict = {}

def _hyde_text(vuln: dict) -> str:
    vid = vuln.get("id", "")
    if vid in _HYDE_CACHE:
        return _HYDE_CACHE[vid]
    if _client is None:
        _HYDE_CACHE[vid] = ""
        return ""
    prompt = (
        "Write a 3-sentence US court holding relevant to this credit card issue.\n\n"
        f"Issue: {vuln.get('title', '')}\n"
        f"Clause: {vuln.get('triggered_by', '')[:250]}\n\n"
        "Include TILA / CFPB / consumer protection concepts. Return holding text only."
    )
    try:
        resp = _client.messages.create(
            model="claude-haiku-4-5", max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
    except Exception as e:
        print(f"  [HyDE 오류] {e}"); text = ""
    _HYDE_CACHE[vid] = text
    return text

def rerank_hyde(vuln: dict, query: str, candidates: list) -> list:
    """HyDE: 가상 판례 holding 텍스트로 BM25"""
    hyp = _hyde_text(vuln)
    if not hyp:
        return rerank_bm25(query, candidates)
    return _top_k(candidates, _bm25_scores(hyp, candidates))

_MQ_POOL_CACHE:   dict = {}  # vid → merged candidate list
_MQ_RANKED_CACHE: dict = {}  # vid → [(query, ranked_list)]

def _generate_mq_queries(vuln: dict) -> list[str]:
    if _client is not None:
        prompt = (
            "Generate 4 diverse US legal search queries for this credit card issue.\n"
            f"Title: {vuln.get('title', '')}\n"
            f"Clause: {vuln.get('triggered_by', '')[:200]}\n"
            f"Taxonomy: {vuln.get('taxonomy', '')}\n\n"
            "One query per line, no numbering. Focus: TILA, CFPB, FCBA, "
            "class action, consumer rights, state law. Under 10 words each."
        )
        try:
            resp = _client.messages.create(
                model="claude-haiku-4-5", max_tokens=150,
                messages=[{"role": "user", "content": prompt}],
            )
            lines = [l.strip() for l in resp.content[0].text.strip().splitlines()
                     if l.strip() and len(l.strip()) > 5]
            return lines[:4]
        except Exception as e:
            print(f"  [MultiQuery 쿼리 생성 오류] {e}")
    tax = vuln.get("taxonomy", "")
    return [
        f"{TAX_PREFIX.get(tax, 'credit card')} federal court ruling",
        f"CFPB enforcement {vuln.get('title', '').lower()[:30]}",
    ]

def _prepare_multiquery(vuln: dict, base_query: str, base_candidates: list):
    vid = vuln.get("id", "")
    if vid in _MQ_POOL_CACHE:
        return
    extra_queries = _generate_mq_queries(vuln)
    all_docs: dict = {c["case_number"]: c for c in base_candidates}
    ranked_lists   = [(base_query, base_candidates)]
    for q in extra_queries:
        results = cl_search(q, n=10)
        if results:
            ranked_lists.append((q, results))
            for c in results:
                all_docs[c["case_number"]] = c
        time.sleep(1.2)
    _MQ_POOL_CACHE[vid]   = list(all_docs.values())
    _MQ_RANKED_CACHE[vid] = ranked_lists

def rerank_multiquery(vuln: dict, query: str, candidates: list) -> list:
    """Multi-query RRF: Claude생성 쿼리 4개로 CourtListener 검색 후 RRF 합산"""
    vid          = vuln.get("id", "")
    ranked_lists = _MQ_RANKED_CACHE.get(vid, [])
    if not ranked_lists:
        return rerank_bm25(query, candidates)
    rrf: dict = defaultdict(float)
    doc_map: dict = {}
    for _q, ranked in ranked_lists:
        for rank, doc in enumerate(ranked, 1):
            cn = doc["case_number"]
            rrf[cn] += 1.0 / (args.rrf_k + rank)
            doc_map[cn] = doc
    out = []
    for cn, score in sorted(rrf.items(), key=lambda x: -x[1])[:args.top_k]:
        if cn in doc_map:
            d = dict(doc_map[cn]); d["relevance_score"] = round(score, 4); out.append(d)
    return out

_FULL_TEXT_CACHE: dict = {}

def _prepare_snippet_expand(candidates: list) -> dict:
    result = {}
    for c in candidates[:5]:
        cn = c.get("case_number", "")
        if cn in _FULL_TEXT_CACHE:
            result[cn] = _FULL_TEXT_CACHE[cn]
            continue
        text = cl_fetch_opinion_text(c.get("cluster_id", ""))
        _FULL_TEXT_CACHE[cn] = text
        result[cn] = text
        time.sleep(0.8)
    return result

def rerank_snippet_expand(query: str, candidates: list, full_texts: dict) -> list:
    """판례 전문(최대 3000자) 추가 후 BM25 재계산"""
    if not candidates:
        return []
    expanded = []
    for c in candidates:
        ec = dict(c)
        ec["_full"] = c["_full"] + " " + full_texts.get(c.get("case_number", ""), "")[:2000]
        expanded.append(ec)
    return _top_k(expanded, _bm25_scores(query, expanded))

# ── dispatcher ────────────────────────────────────────────────────
def run_search(method: str, query: str, candidates: list,
               vuln: dict, full_texts: dict) -> list:
    if method == "BM25":          return rerank_bm25(query, candidates)
    if method == "BM25Plus":      return rerank_bm25plus(query, candidates)
    if method == "Embedding":     return rerank_embedding(query, candidates)
    if method == "Hybrid":        return rerank_hybrid(query, candidates)
    if method == "PRF":           return rerank_prf(query, candidates)
    if method == "MMR":           return rerank_mmr(query, candidates)
    if method == "CourtWeight":   return rerank_court_weight(query, candidates)
    if method == "DateDecay":     return rerank_date_decay(query, candidates)
    if method == "CombMNZ":       return rerank_combmnz(query, candidates)
    if method == "DenseEmbed":    return rerank_dense_embed(query, candidates)
    if method == "HyDE":          return rerank_hyde(vuln, query, candidates)
    if method == "MultiQuery":    return rerank_multiquery(vuln, query, candidates)
    if method == "SnippetExpand": return rerank_snippet_expand(query, candidates, full_texts)
    return []

# ── Claude judge ──────────────────────────────────────────────────
_JUDGE: dict = {}
TAX_KEYWORDS = {
    "CC-01": ["fee", "disclosure", "tila"],
    "CC-02": ["apr", "interest", "penalty"],
    "CC-03": ["minimum payment", "billing", "balance"],
    "CC-04": ["change in terms", "modification", "cancel"],
    "CC-05": ["arbitration", "class action", "waiver"],
}

def judge(vuln: dict, prec: dict) -> bool:
    key = vuln.get("id", "") + "|" + str(prec.get("case_number", ""))
    if key in _JUDGE:
        return _JUDGE[key]

    if _client is None:
        kws  = TAX_KEYWORDS.get(vuln.get("taxonomy", ""), [])
        text = (prec.get("case_name", "") + " " + prec.get("snippet", "")).lower()
        _JUDGE[key] = any(kw in text for kw in kws)
        return _JUDGE[key]

    prompt = (
        f"Is this US court case relevant to the credit card vulnerability?\n\n"
        f"[Vuln] {vuln.get('taxonomy', '')} — {vuln.get('title', '')}\n"
        f"[Clause] {vuln.get('triggered_by', '')[:200]}\n\n"
        f"[Case: {prec.get('case_name', '')[:80]}]\n"
        f"Snippet: {prec.get('snippet', '')[:400]}\n\nReply YES or NO only."
    )
    try:
        resp = _client.messages.create(
            model="claude-haiku-4-5", max_tokens=5,
            messages=[{"role": "user", "content": prompt}],
        )
        result = resp.content[0].text.strip().upper().startswith("Y")
    except Exception as e:
        print(f"  [Judge 오류] {e}"); result = False
    _JUDGE[key] = result
    return result

# ── evaluation metrics ────────────────────────────────────────────
def evaluate(flags: list) -> dict:
    if not any(flags):
        return {}
    n   = sum(flags)
    mrr = next((1.0 / (i + 1) for i, f in enumerate(flags) if f), 0.0)
    m   = {"MRR": round(mrr, 4)}
    for k in (1, 2, 3):
        hit        = sum(flags[:k])
        m[f"P@{k}"] = round(hit / k, 4)
        m[f"R@{k}"] = round(hit / n, 4) if n else 0.0
    return m

# ── main loop ─────────────────────────────────────────────────────
raw_results = []
method_agg  = {m: defaultdict(list) for m in METHODS}
_CAND: dict = {}

for vuln in vulns:
    vid   = vuln.get("id", "")
    tax   = vuln.get("taxonomy", "")
    title = vuln.get("title", "")
    query = clean_query(vuln)

    print(f"\n[{vid}] {tax} | {title[:45]}")
    print(f"  쿼리: {query[:65]}")

    if query not in _CAND:
        _CAND[query] = cl_search(query, n=20)
        time.sleep(1.0)

    candidates = _CAND[query]
    if not candidates:
        print("  → 후보 없음, 스킵")
        raw_results.append({"vuln_id": vid, "taxonomy": tax, "skipped": True})
        continue

    full_texts: dict = {}

    if not args.skip_expensive:
        if "MultiQuery" in METHODS:
            print("  [MultiQuery] 쿼리 확장 중...")
            _prepare_multiquery(vuln, query, candidates)
            pool = _MQ_POOL_CACHE.get(vid, candidates)
            print(f"  [MultiQuery] 확장 후보: {len(pool)}건")

        if "SnippetExpand" in METHODS:
            print("  [SnippetExpand] 전문 가져오는 중 (최대 5건)...")
            full_texts = _prepare_snippet_expand(candidates)

    row = {"vuln_id": vid, "taxonomy": tax, "title": title, "query": query}

    for method in METHODS:
        results = run_search(method, query, candidates, vuln, full_texts)
        flags, detail = [], []
        for prec in results:
            is_rel = judge(vuln, prec)
            flags.append(is_rel)
            print(f"    [{method:<13}] {'[Y]' if is_rel else '[ ]'} {prec.get('case_name','')[:50]}")
            detail.append({
                "case_name": prec.get("case_name", ""),
                "score":     prec.get("relevance_score", 0),
                "relevant":  is_rel,
                "url":       prec.get("url", ""),
            })
            time.sleep(0.1)

        m = evaluate(flags)
        row[method] = {"metrics": m, "results": detail}
        if m:
            for k, v in m.items():
                method_agg[method][k].append(v)
            print(f"    → MRR={m['MRR']:.3f}  P@1={m['P@1']:.3f}  P@3={m.get('P@3',0):.3f}")
        else:
            print("    → relevant 없음")

    raw_results.append(row)

# ── summary ───────────────────────────────────────────────────────
summary = {
    m: {k: round(sum(v) / len(v), 4) for k, v in agg.items() if v}
    for m, agg in method_agg.items()
}

output = {
    "experiment":  "E3_retrieval_US_v2",
    "product":     product,
    "top_k":       args.top_k,
    "methods":     METHODS,
    "n_evaluated": len([r for r in raw_results if not r.get("skipped")]),
    "summary":     summary,
    "raw":         raw_results,
}
out_path = OUT / "e3_retrieval_us.json"
out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

print("\n" + "=" * 75)
print(f"E3 결과 — {len(METHODS)}개 방법")
print("=" * 75)
print(f"{'방법':<14} {'MRR':>7} {'P@1':>7} {'P@2':>7} {'P@3':>7}")
print("-" * 55)
for m in METHODS:
    v = summary.get(m, {})
    print(f"{m:<14} {v.get('MRR',0):>7.4f} {v.get('P@1',0):>7.4f} "
          f"{v.get('P@2',0):>7.4f} {v.get('P@3',0):>7.4f}")
print(f"\n[완료] 저장: {out_path}")
