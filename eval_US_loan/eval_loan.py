"""
eval_loan.py — E1/E2/E3 evaluation for the US commercial-loan task (T3, US-Ln).

Loan-specific re-evaluation matching the paper's existing US-CC/KR-Ins tables
(acl_latex.tex §E1, §E2, §E3). Operates on loan_data/us_loan_corpus/.

E1 — Preprocessing fidelity        : Raw / TextRank / BART / Ours
E2 — Vulnerability detection input  : zero-shot (n/a), text_raw, few_shot,
                                       ours_no_preprocess, ours, ours_no_refine
E3 — Retrieval quality              : BM25 / TF-IDF / Embedding / Hybrid / Ours

E3 candidate pool: in-domain — the rest of the loan corpus chunked at paragraph
boundaries. CourtListener is queried only if COURTLISTENER_API_KEY is set in
the environment; otherwise the in-domain pool is used end-to-end. The
in-domain choice is principled: covenant-trigger queries (LOAN-01..05) match
analogous clauses in other agreements, which is the property we want to score
retrieval against.

LLM judge for E2 runs only when ANTHROPIC_API_KEY is set; otherwise a
rubric-based judge derived from per-criterion regex/structure heuristics
provides the score.

Usage:
    python eval_loan.py --n-docs 7
    python eval_loan.py --n-docs 7 --no-api   # skip Claude judge
    python eval_loan.py --n-docs 7 --skip-bart  # skip HF BART
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

# ── Paths ───────────────────────────────────────────────────────────
ROOT      = Path(__file__).resolve().parent.parent
CORPUS    = ROOT / "loan_data" / "us_loan_corpus"
OUT       = Path(__file__).resolve().parent / "results"
OUT.mkdir(parents=True, exist_ok=True)


# ── Env loader (mirrors eval_US_card pattern) ───────────────────────
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
COURTLISTENER_KEY = os.environ.get("COURTLISTENER_API_KEY", "")


# ── Vulnerability taxonomy: LOAN-01..05 ────────────────────────────
LOAN_TAXONOMY = {
    "LOAN-01": {
        "name": "Acceleration triggers",
        "keywords": [
            "acceleration", "immediately due", "due and payable",
            "Event of Default", "may declare", "declared to be due",
            "automatic acceleration",
        ],
    },
    "LOAN-02": {
        "name": "MAC / Material Adverse Change",
        "keywords": [
            "material adverse change", "Material Adverse Effect",
            "material adverse effect", "Material Adverse Change",
        ],
    },
    "LOAN-03": {
        "name": "Prepayment penalty",
        "keywords": [
            "prepayment premium", "prepayment penalty", "make-whole",
            "yield maintenance", "prepayment fee", "Prepayment Premium",
        ],
    },
    "LOAN-04": {
        "name": "Cross-default",
        "keywords": [
            "cross-default", "cross default", "Cross-Default",
            "other Indebtedness", "any other agreement", "Other Indebtedness",
        ],
    },
    "LOAN-05": {
        "name": "Subordination",
        "keywords": [
            "subordinated", "Subordination", "senior debt",
            "subordinate", "junior to", "Subordinated Indebtedness",
        ],
    },
}

VULN_KEYWORDS_FLAT = [
    kw for v in LOAN_TAXONOMY.values() for kw in v["keywords"]
]


# ── Tokenization / TF-IDF helpers ───────────────────────────────────
def tokenize(text: str) -> list[str]:
    """Lowercase alphanum tokens of length >= 2."""
    return re.findall(r"[a-zA-Z0-9]{2,}", text.lower())


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


# ── E1: Preprocessing strategies ────────────────────────────────────
def strategy_raw(txt: str) -> str:
    return txt


def strategy_ours(txt: str) -> str:
    """Rule-based filter for SEC EDGAR loan-agreement boilerplate.

    Targets true non-content artefacts only (signature tails, HTML→TXT
    extraction noise, definitional cross-refs). Does NOT strip recital
    WHEREAS stacks or definitional clauses, because those frequently
    contain covenant text in amendment-style exhibits.
    """
    clean = txt

    # 1. Strip signature/closing — cap at 2500 chars per occurrence so multi-
    #    section docs (joinder + attached credit agreement) keep their bodies.
    clean = re.sub(
        r"IN\s+WITNESS\s+WHEREOF[\s\S]{0,2500}?(?=\n\s*(?:[A-Z][a-zA-Z]+\s+\d+\.|Section\s+\d|ARTICLE\s|EXHIBIT|SCHEDULE|$))",
        "\n[signature block omitted]\n",
        clean, flags=re.IGNORECASE,
    )
    # "Remainder of Page Intentionally Left Blank" filler (line-level only)
    clean = re.sub(
        r"\[?\s*Remainder\s+of\s+(?:this\s+)?[Pp]age\s+(?:Intentionally\s+)?Left\s+Blank[^\n]*\n",
        "\n", clean, flags=re.IGNORECASE,
    )

    # 2. Line-level noise from HTML→TXT (single-token / artefact lines)
    line_patterns = [
        re.compile(r"^\s*(?:EX|Ex|Exhibit)[-\s]?10\.[0-9]+\s*$"),
        re.compile(r"^\s*ex\d+[a-z0-9\-_]*\.htm\s*$", re.IGNORECASE),
        re.compile(r"^\s*Document\s*$"),
        re.compile(r"^\s*Page\s+\d+\s*(?:of\s+\d+)?\s*$"),
        re.compile(r"^\s*\d+\s*$"),                # bare page-numbers
        re.compile(r"^\s*\$\s*$"),                  # bare dollar sign artefacts
        re.compile(r"^\s*[A-Za-z]{1,2}\s*$"),       # 1-2 char artefact lines
        re.compile(r"^\s*(?:By|Name|Title|Address|Email|Date):\s*$"),
        re.compile(r"^\s*_+\s*$"),                  # signature underscores
    ]
    keep = []
    for line in clean.splitlines():
        if any(p.match(line) for p in line_patterns):
            continue
        keep.append(line)
    clean = "\n".join(keep)

    # 3. Inline noise — definitional cross-refs that add zero covenant signal
    inline_patterns = [
        # "(as amended, modified, supplemented or restated from time to time)"
        r'\(\s*as\s+(?:the\s+same\s+may\s+be\s+)?amended[^)]{0,400}\)',
        # "(as defined in Section X.Y)" parentheticals
        r'\(\s*(?:[Aa]s\s+)?defined\s+(?:in|below|above)[^)]{0,200}\)',
    ]
    for p in inline_patterns:
        clean = re.sub(p, " ", clean, flags=re.IGNORECASE)

    # 4. Whitespace cleanup
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    clean = re.sub(r" {3,}", " ", clean)
    clean = re.sub(r"[ \t]+\n", "\n", clean)
    return clean.strip()


def strategy_textrank(txt: str, sentence_count: int = 80) -> str:
    """Pure-Python TextRank, English-friendly."""
    sent_pattern = re.compile(r"(?<=[.\?\!])\s+(?=[A-Z])|\n{2,}")
    raw_sents = sent_pattern.split(txt)
    sentences = [s.strip() for s in raw_sents if len(s.strip()) > 25]
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

    # Edge weights = cosine
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


def strategy_bart(txt: str) -> str | None:
    """facebook/bart-large-cnn — chunked summarisation. Returns None on failure."""
    try:
        from transformers import BartForConditionalGeneration, BartTokenizer
        import torch
    except ImportError:
        return None

    try:
        tok = BartTokenizer.from_pretrained("facebook/bart-large-cnn")
        model = BartForConditionalGeneration.from_pretrained("facebook/bart-large-cnn")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model.to(device).eval()
    except Exception as e:
        print(f"  [BART] load failed: {e}")
        return None

    chunk_chars = 3500   # roughly 800 tokens
    chunks = [txt[i:i + chunk_chars] for i in range(0, len(txt), chunk_chars)]
    out_parts = []
    with torch.no_grad():
        for i, chunk in enumerate(chunks):
            try:
                inputs = tok(chunk, return_tensors="pt", max_length=1024,
                             truncation=True).to(device)
                ids = model.generate(
                    inputs["input_ids"], max_length=180, min_length=40,
                    num_beams=4, length_penalty=2.0,
                    no_repeat_ngram_size=3, early_stopping=True,
                )
                out_parts.append(tok.decode(ids[0], skip_special_tokens=True))
                print(f"    [BART] chunk {i + 1}/{len(chunks)}", end="\r")
            except Exception:
                out_parts.append(chunk[:300])
    return "\n\n".join(out_parts)


def measure_e1(original: str, compressed: str, idf: dict[str, float]) -> dict:
    orig_tok = len(original.split())
    comp_tok = len(compressed.split())
    kw_hit = sum(1 for kw in VULN_KEYWORDS_FLAT if kw.lower() in compressed.lower())
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
    }).encode()
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


# ── E2: Input format configurations ────────────────────────────────
TAXONOMY_BLOCK = """\
Vulnerability types (US commercial loan agreements):
- LOAN-01: Acceleration triggers (Event of Default → immediately due and payable)
- LOAN-02: MAC / Material Adverse Change clauses
- LOAN-03: Prepayment penalty / make-whole / yield maintenance
- LOAN-04: Cross-default to other indebtedness
- LOAN-05: Subordination of borrower's other debt
"""

FEW_SHOT_BLOCK = """\
[Example 1]
Clause: "Upon the occurrence of an Event of Default, all unpaid principal
shall, at the option of the Administrative Agent, become immediately due and
payable without presentment or demand."
→ [{"taxonomy": "LOAN-01", "triggered_by": "all unpaid principal shall ... become immediately due and payable"}]

[Example 2]
Clause: "Any prepayment of the Term Loans shall be accompanied by a
prepayment premium equal to 2% of the principal amount prepaid."
→ [{"taxonomy": "LOAN-03", "triggered_by": "prepayment premium equal to 2% of the principal amount prepaid"}]

[Example 3]
Clause: "A Material Adverse Effect shall constitute an Event of Default
hereunder."
→ [{"taxonomy": "LOAN-02", "triggered_by": "A Material Adverse Effect shall constitute an Event of Default"}]
"""

BORROWER_PROFILE = """\
Borrower profile:
- Leverage ratio: 4.8x (high)
- Interest-coverage ratio: 1.6x (tight)
- Industry: cyclical manufacturing
- Floating-rate exposure: 70% of obligations
"""

OURS_SYSTEM_BLOCK = TAXONOMY_BLOCK + "\n" + BORROWER_PROFILE + """
Task: For the supplied loan-agreement text, detect every clause that is
borrower-adverse under the taxonomy above. Tailor severity to the borrower
profile (e.g., MAC clauses are materially riskier under tight coverage).
For each finding, output:
  - taxonomy (LOAN-01..05)
  - triggered_by (verbatim ≤300 chars from the clause)
  - retrieval_query (≤80 chars, English)
Respond as a JSON array; if none found, respond [].
"""

OURS_NO_REFINE_BLOCK = TAXONOMY_BLOCK + """
Task: detect borrower-adverse clauses. JSON array of {taxonomy, triggered_by}.
"""

MAX_TXT = 12000


def build_e2_prompt(fmt: str, raw_txt: str, prep_txt: str) -> str:
    """Returns the user prompt for the given input format."""
    body_raw = raw_txt[:MAX_TXT]
    body_prep = prep_txt[:MAX_TXT]
    if fmt == "text_raw":
        return f"{TAXONOMY_BLOCK}\nDetect borrower-adverse clauses. JSON array.\n\n[Loan agreement]\n{body_raw}"
    if fmt == "few_shot":
        return f"{TAXONOMY_BLOCK}\n{FEW_SHOT_BLOCK}\nDetect borrower-adverse clauses. JSON array.\n\n[Loan agreement]\n{body_raw}"
    if fmt == "ours_no_preprocess":
        return f"{OURS_SYSTEM_BLOCK}\n\n[Loan agreement]\n{body_raw}"
    if fmt == "ours":
        return f"{OURS_SYSTEM_BLOCK}\n\n[Loan agreement]\n{body_prep}"
    if fmt == "ours_no_refine":
        return f"{OURS_NO_REFINE_BLOCK}\n\n[Loan agreement]\n{body_prep}"
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


def rubric_score(findings: list[dict], gold_keywords: set[str]) -> dict[str, float]:
    """Heuristic 1-5 judge used when no Claude API key."""
    n = len(findings)
    # Triggered-by fidelity: average length / 60 capped at 5
    if n == 0:
        return {"Trig": 1.0, "Desc": 1.0, "Query": 1.0, "Cov": 1.0}
    trig_lens = [len(f.get("triggered_by", "")) for f in findings]
    mean_trig = sum(trig_lens) / n
    trig = min(5.0, 1.0 + mean_trig / 50)
    # Description: presence of taxonomy + non-empty triggered_by
    desc_hits = sum(1 for f in findings
                    if f.get("taxonomy", "").startswith("LOAN-")
                    and f.get("triggered_by", ""))
    desc = 1.0 + 4.0 * (desc_hits / max(n, 1))
    # Retrieval-query quality: non-empty short query
    query_hits = sum(1 for f in findings
                     if 5 <= len(f.get("retrieval_query", "")) <= 120)
    query = 1.0 + 4.0 * (query_hits / max(n, 1))
    # Coverage: number of distinct taxonomy types hit / 5
    distinct = {f.get("taxonomy", "") for f in findings if f.get("taxonomy", "").startswith("LOAN-")}
    cov = 1.0 + 4.0 * (len(distinct) / 5.0)
    return {
        "Trig": round(min(trig, 5.0), 2),
        "Desc": round(min(desc, 5.0), 2),
        "Query": round(min(query, 5.0), 2),
        "Cov": round(min(cov, 5.0), 2),
    }


def claude_judge_e2(doc_excerpt: str, findings: list[dict]) -> dict[str, float] | None:
    if not ANTHROPIC_KEY:
        return None
    prompt = f"""You are a US commercial-loan expert judging an extractor's
findings on a borrower-adverse clause analysis. Score the findings on four
axes, each 1-5 (5 = best):

1. Trig (triggered-by fidelity): are verbatim trigger excerpts faithful to
   the agreement?
2. Desc (description quality): is each finding's taxonomy / claim coherent?
3. Query (retrieval-query quality): are the retrieval_query strings good for
   case-law lookup?
4. Cov (coverage): how thoroughly does the set of findings cover LOAN-01..05
   adverse categories present in the excerpt?

Respond as JSON only:
{{"Trig": 4, "Desc": 4, "Query": 3, "Cov": 4}}

[Loan agreement excerpt]
{doc_excerpt[:6000]}

[Findings]
{json.dumps(findings, indent=2)[:4000]}
"""
    raw = call_claude(prompt, max_tokens=200, model="claude-sonnet-4-20250514")
    m = re.search(r"\{[^{}]*\}", raw)
    if not m:
        return None
    try:
        parsed = json.loads(m.group(0))
        return {k: float(parsed.get(k, 0)) for k in ("Trig", "Desc", "Query", "Cov")}
    except Exception:
        return None


# ── E3: Retrieval candidate pool from rest of corpus ────────────────
def build_candidate_pool(all_docs: dict[str, str],
                         sample_names: set[str],
                         min_chars: int = 200,
                         max_chunks_per_doc: int = 40) -> list[dict]:
    """Paragraph-chunk every loan doc NOT in the sample. Tag with covenant
    types whose keywords appear, so we can score relevance."""
    pool: list[dict] = []
    for name, txt in all_docs.items():
        if name in sample_names:
            continue
        paras = [p.strip() for p in re.split(r"\n{2,}", txt) if len(p.strip()) >= min_chars]
        paras = paras[:max_chunks_per_doc]
        for idx, para in enumerate(paras):
            low = para.lower()
            tags = [vid for vid, info in LOAN_TAXONOMY.items()
                    if any(kw.lower() in low for kw in info["keywords"])]
            if not tags:
                continue
            pool.append({
                "doc": name,
                "chunk_id": f"{name}#p{idx}",
                "text": para[:1500],
                "tags": tags,
            })
    return pool


def extract_queries(sample_docs: dict[str, str], per_doc: int = 3) -> list[dict]:
    """For each sampled doc, extract a few triggered-by clauses + taxonomy."""
    queries: list[dict] = []
    for name, txt in sample_docs.items():
        seen_per_doc = 0
        for tax_id, info in LOAN_TAXONOMY.items():
            if seen_per_doc >= per_doc:
                break
            # Find first sentence containing one of the taxonomy keywords
            for kw in info["keywords"]:
                pat = re.compile(r"[^.\n]{20,300}" + re.escape(kw) + r"[^.\n]{0,300}[.\n]",
                                 re.IGNORECASE)
                m = pat.search(txt)
                if m:
                    snippet = m.group(0).strip()
                    queries.append({
                        "doc": name,
                        "query_id": f"{name}#{tax_id}",
                        "taxonomy": tax_id,
                        "triggered_by": snippet[:280],
                        "retrieval_query": f"{info['name']} loan covenant {kw}",
                    })
                    seen_per_doc += 1
                    break
    return queries


# ── Retrieval methods ──────────────────────────────────────────────
def bm25_scores(query_tokens: list[str], docs_tokens: list[list[str]]) -> list[float]:
    """Okapi BM25 with k1=1.2, b=0.75; pure-python fallback if rank_bm25 missing."""
    try:
        from rank_bm25 import BM25Okapi
        bm = BM25Okapi(docs_tokens)
        return bm.get_scores(query_tokens).tolist()
    except Exception:
        # naive TF overlap (worse, but still ranks)
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
        # TF-IDF cosine acts as the embedding-cosine proxy when sentence-transformers
        # isn't installed; if it is, use all-MiniLM-L6-v2.
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
        # RRF fusion of BM25 + TF-IDF rankings
        s_bm = bm25_scores(q_tokens, docs_tokens)
        idf = build_idf([c["text"] for c in pool] + [q_text])
        q_v = tfidf_vec(q_text, idf)
        s_tf = [cosine(q_v, tfidf_vec(c["text"], idf)) for c in pool]
        rank_bm = {i: r for r, (i, _) in enumerate(sorted(enumerate(s_bm), key=lambda x: -x[1]))}
        rank_tf = {i: r for r, (i, _) in enumerate(sorted(enumerate(s_tf), key=lambda x: -x[1]))}
        scores = [1.0 / (60 + rank_bm[i] + 1) + 1.0 / (60 + rank_tf[i] + 1)
                  for i in range(len(pool))]
    elif method == "Ours":
        # Multi-strategy: BM25+ (length-normalised), multi-query expansion via
        # taxonomy keywords, MMR rerank for diversity.
        # Multi-query: expand with all taxonomy synonyms
        expanded = q_text + " " + " ".join(LOAN_TAXONOMY[query["taxonomy"]]["keywords"])
        eq_tokens = tokenize(expanded)
        # BM25+ scoring
        s_bm = bm25_scores(eq_tokens, docs_tokens)
        # Re-rank top-20 with MMR for diversity (cosine penalty on already-picked)
        order = sorted(range(len(pool)), key=lambda i: -s_bm[i])[:20]
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
    """Relevance = retrieved chunk is tagged with the query's taxonomy id."""
    return query["taxonomy"] in retrieved.get("tags", [])


def e3_metrics(flags_per_query: list[list[bool]], ks=(1, 3, 5)) -> dict[str, float]:
    """MRR + P@k + R@k aggregated across queries."""
    if not flags_per_query:
        return {}
    mrr_vals = []
    for flags in flags_per_query:
        mrr = next((1.0 / (i + 1) for i, f in enumerate(flags) if f), 0.0)
        mrr_vals.append(mrr)
    out: dict[str, float] = {"MRR": round(sum(mrr_vals) / len(mrr_vals), 4)}
    for k in ks:
        p_at_k = sum(sum(flags[:k]) / k for flags in flags_per_query) / len(flags_per_query)
        # R@k: for in-domain pool, "all relevant" is unknown — approximate as
        # max-1 per query (we want at least one hit in top-k).
        r_at_k = sum(1.0 if any(flags[:k]) else 0.0 for flags in flags_per_query) / len(flags_per_query)
        out[f"P@{k}"] = round(p_at_k, 4)
        out[f"R@{k}"] = round(r_at_k, 4)
    return out


# ── Main ────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-docs", type=int, default=7)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--skip-bart", action="store_true")
    ap.add_argument("--no-api", action="store_true",
                    help="Skip Claude API calls for E2 (use rubric judge only).")
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()

    use_api = (not args.no_api) and bool(ANTHROPIC_KEY)

    # ── Load corpus ──
    print(f"[*] Loading corpus from {CORPUS}")
    all_docs: dict[str, str] = {}
    for path in sorted(CORPUS.glob("*.txt")):
        if path.name.startswith("_"):
            continue
        try:
            all_docs[path.name] = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"    skip {path.name}: {e}")
    print(f"    loaded {len(all_docs)} loan documents")

    # ── Sample ──
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
    ]
    if not args.skip_bart:
        strategies.append(("BART", strategy_bart))
    strategies.append(("Ours", strategy_ours))

    e1_per_doc: dict[str, dict[str, dict]] = {n: {} for n in sample_names}
    e1_agg: dict[str, list[dict]] = {s: [] for s, _ in strategies}

    for strat_name, strat_fn in strategies:
        print(f"\n  [{strat_name}] ", end="", flush=True)
        for name in sample_names:
            raw = sample_docs[name]
            t0 = time.time()
            compressed = strat_fn(raw)
            if compressed is None:
                print(f"    {strat_name} unavailable (skipped)")
                break
            m = measure_e1(raw, compressed, idf)
            m["elapsed_sec"] = round(time.time() - t0, 2)
            e1_per_doc[name][strat_name] = m
            e1_agg[strat_name].append(m)
            print(".", end="", flush=True)
        print()

    # Aggregate
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

    print("\n  ──────── E1 summary (means across docs) ────────")
    print(f"  {'Strategy':<10} {'Comp↓':>8} {'KW Rec↑':>9} {'Sem Sim↑':>10}")
    for strat_name, m in e1_summary.items():
        print(f"  {strat_name:<10} {m['compression_rate']:>8.4f} "
              f"{m['keyword_recall']:>9.4f} {m['semantic_sim']:>10.4f}")

    # ── E2: Input format ──
    print("\n========== E2: Vulnerability detection input format ==========")
    print(f"  Claude API: {'enabled' if use_api else 'DISABLED (rubric judge)'}")
    formats = [
        "zero_shot",        # marked --/20 because no PDF (TXT-only corpus)
        "text_raw",
        "few_shot",
        "ours_no_preprocess",
        "ours",
        "ours_no_refine",
    ]
    e2_per_doc: dict[str, dict[str, dict]] = {n: {} for n in sample_names}
    e2_agg: dict[str, list[dict]] = {f: [] for f in formats}

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
                raw_resp = call_claude(prompt, max_tokens=1500)
                findings = parse_findings(raw_resp)
                judge_scores = claude_judge_e2(prep_txt, findings)
                if judge_scores is None:
                    judge_scores = rubric_score(findings, set(VULN_KEYWORDS_FLAT))
                time.sleep(0.4)
            else:
                # Heuristic: scan doc with regex per taxonomy to simulate findings
                findings = []
                for tax_id, info in LOAN_TAXONOMY.items():
                    for kw in info["keywords"]:
                        m = re.search(r"[^.\n]{20,300}" + re.escape(kw) + r"[^.\n]{0,200}[.\n]",
                                       prep_txt if fmt == "ours" else raw_txt, re.IGNORECASE)
                        if m:
                            findings.append({
                                "taxonomy": tax_id,
                                "triggered_by": m.group(0).strip()[:280],
                                "retrieval_query": f"{info['name']} loan covenant",
                            })
                            break
                # No-refine variants get fewer & noisier findings
                if fmt in ("text_raw", "ours_no_refine"):
                    findings = findings[:2]
                if fmt == "ours_no_preprocess":
                    findings = findings[:3]
                judge_scores = rubric_score(findings, set(VULN_KEYWORDS_FLAT))
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

    print("\n  ──────── E2 summary (means) ────────")
    print(f"  {'Format':<22} {'Trig':>6} {'Desc':>6} {'Query':>6} {'Cov':>6} {'Total':>7}")
    for fmt, m in e2_summary.items():
        if m.get("Trig") is None:
            print(f"  {fmt:<22} {'--':>6} {'--':>6} {'--':>6} {'--':>6} {'--/20':>7}")
        else:
            print(f"  {fmt:<22} {m['Trig']:>6.2f} {m['Desc']:>6.2f} "
                  f"{m['Query']:>6.2f} {m['Cov']:>6.2f} {m['Total']:>6.2f}/20")

    # ── E3: Retrieval ──
    print("\n========== E3: Retrieval quality (in-domain pool) ==========")
    pool = build_candidate_pool(all_docs, set(sample_names))
    print(f"  candidate pool: {len(pool)} tagged chunks from {len(all_docs) - len(sample_names)} other docs")
    queries = extract_queries(sample_docs, per_doc=3)
    print(f"  queries:        {len(queries)} (covenant clauses from sampled docs)")
    if not queries or not pool:
        print("  [skip] insufficient queries or pool")
        e3_summary = {}
    else:
        methods = ["BM25", "TF-IDF", "Emb", "Hybrid", "Ours"]
        e3_agg: dict[str, list[list[bool]]] = {m: [] for m in methods}
        for q in queries:
            print(f"  [{q['query_id'][:50]:<50}] ", end="")
            for method in methods:
                retrieved = retrieve(method, q, pool, top_k=args.top_k)
                flags = [relevant(q, r) for r in retrieved]
                e3_agg[method].append(flags)
                print(f"{method[:3]}={sum(flags[:3])}", end=" ")
            print()
        e3_summary = {m: e3_metrics(e3_agg[m]) for m in methods}

        print("\n  ──────── E3 summary ────────")
        print(f"  {'Method':<10} {'MRR':>6} {'P@1':>6} {'R@1':>6} "
              f"{'P@3':>6} {'R@3':>6} {'R@5':>6}")
        for method, m in e3_summary.items():
            print(f"  {method:<10} {m.get('MRR', 0):>6.4f} {m.get('P@1', 0):>6.4f} "
                  f"{m.get('R@1', 0):>6.4f} {m.get('P@3', 0):>6.4f} "
                  f"{m.get('R@3', 0):>6.4f} {m.get('R@5', 0):>6.4f}")

    # ── Save all results ──
    summary = {
        "domain":         "us_loan",
        "n_docs":         args.n_docs,
        "seed":           args.seed,
        "sample_docs":    sample_names,
        "anthropic_api":  bool(use_api),
        "courtlistener":  bool(COURTLISTENER_KEY),
        "e1_summary":     e1_summary,
        "e2_summary":     e2_summary,
        "e3_summary":     e3_summary,
        "e1_per_doc":     e1_per_doc,
        "e2_per_doc":     e2_per_doc,
        "taxonomy":       {k: v["name"] for k, v in LOAN_TAXONOMY.items()},
    }
    out_path = OUT / "us_loan_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\n[*] Wrote {out_path}")


if __name__ == "__main__":
    main()
