"""Auditable lexical retrieval and document-level pilot statistics.

No embeddings, model calls, taxonomy labels, or fallback scoring are used.
Relevance must explicitly judge every ranked ID: unjudged is not irrelevant.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
import math
import random
import re
from statistics import fmean
import unicodedata


MetricRow = dict[str, float | int | bool | None]
_METADATA = {"n_relevant", "n_ranked", "no_relevant"}


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _identifier(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("IDs must be nonempty strings")
    return value


def tokenize(text: str) -> list[str]:
    """NFKC/casefold Unicode words plus Hangul bigrams; no stemming.

Whole words retain English and numeric tokens. Overlapping Hangul bigrams
support Korean suffix/compound matching without claiming morphology analysis.
Each word's bigrams are added only when they differ from the whole word.
"""
    if not isinstance(text, str):
        raise ValueError("Text must be a string")
    words = re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", text).casefold())
    tokens = []
    for word in words:
        tokens.append(word)
        for hangul in re.findall(r"[가-힣]+", word):
            tokens.extend(hangul[i:i + 2] for i in range(len(hangul) - 1)
                          if hangul[i:i + 2] != word)
    return tokens


def rank_passages(
    query: str,
    passages: Sequence[Mapping[str, object]],
    config: Mapping[str, object],
) -> list[str]:
    """Rank all passage IDs with BM25 Okapi, TF-IDF cosine, or their RRF.

BM25 uses positive Robertson IDF log(1 + (N-df+.5)/(df+.5)), standard
term saturation/length normalization, and unique query terms. TF-IDF uses
raw term counts and smoothed IDF log((1+N)/(1+df))+1. RRF sums reciprocal
ranks 1/(rrf_k+rank) of those two lexical rankings. Ties use ascending ID.
Config keys: retriever=bm25, k1=1.5, b=.75, rrf_k=60. No other keys allowed.
"""
    unknown = set(config) - {"retriever", "k1", "b", "rrf_k"}
    if unknown:
        raise ValueError(f"Unknown retrieval config keys: {sorted(unknown)}")
    method = config.get("retriever", "bm25")
    if method not in ("bm25", "tfidf", "rrf"):
        raise ValueError("retriever must be bm25, tfidf, or rrf")
    k1 = _number(config.get("k1", 1.5), "k1")
    b = _number(config.get("b", 0.75), "b")
    rrf_k = _number(config.get("rrf_k", 60), "rrf_k")
    if k1 <= 0 or not 0 <= b <= 1 or rrf_k <= 0:
        raise ValueError("Require k1 > 0, 0 <= b <= 1, and rrf_k > 0")
    query_counts = Counter(tokenize(query))
    counts = {}
    for passage in passages:
        doc_id = _identifier(passage.get("id"))
        if doc_id in counts:
            raise ValueError(f"Duplicate corpus ID: {doc_id}")
        counts[doc_id] = Counter(tokenize(passage.get("text")))
    if not counts:
        return []
    n_docs = len(counts)
    document_frequency = Counter(term for doc in counts.values() for term in doc)
    average_length = fmean(sum(doc.values()) for doc in counts.values())
    bm25 = {}
    tfidf = {}
    idf = {term: math.log((1 + n_docs) / (1 + df)) + 1
           for term, df in document_frequency.items()}
    query_vector = {term: tf * idf[term] for term, tf in query_counts.items()
                    if term in idf}
    query_norm = math.sqrt(sum(weight ** 2 for weight in query_vector.values()))
    for doc_id, doc in counts.items():
        length_ratio = sum(doc.values()) / average_length if average_length else 0
        bm25[doc_id] = sum(
            math.log1p((n_docs - document_frequency[term] + 0.5)
                       / (document_frequency[term] + 0.5))
            * doc[term] * (k1 + 1)
            / (doc[term] + k1 * (1 - b + b * length_ratio))
            for term in query_counts if doc[term] > 0
        )
        doc_norm = math.sqrt(sum((tf * idf[term]) ** 2 for term, tf in doc.items()))
        dot = sum(weight * doc[term] * idf[term]
                  for term, weight in query_vector.items())
        tfidf[doc_id] = dot / (query_norm * doc_norm) if query_norm and doc_norm else 0.0
    if method == "rrf":
        scores = dict.fromkeys(counts, 0.0)
        for component in (bm25, tfidf):
            for rank, doc_id in enumerate(sorted(component, key=lambda d: (-component[d], d)), 1):
                scores[doc_id] += 1 / (rrf_k + rank)
    else:
        scores = bm25 if method == "bm25" else tfidf
    return sorted(scores, key=lambda doc_id: (-scores[doc_id], doc_id))


def check_mrr_bound(mrr: float, p1: float, tolerance: float = 1e-12) -> None:
    """Validate P@1 <= MRR <= (1+P@1)/2 for a common binary query cohort."""
    mrr = _number(mrr, "MRR")
    p1 = _number(p1, "P@1")
    tolerance = _number(tolerance, "tolerance")
    if tolerance < 0 or not 0 <= mrr <= 1 or not 0 <= p1 <= 1:
        raise ValueError("MRR and P@1 must be in [0,1]; tolerance must be nonnegative")
    if mrr < p1 - tolerance or mrr > (1 + p1) / 2 + tolerance:
        raise ValueError(f"Inconsistent common-cohort MRR={mrr}, P@1={p1}")


def retrieval_metrics(
    ranked_ids: Sequence[str],
    relevance: Mapping[str, int],
    ks: Sequence[int] = (1, 3, 5),
) -> MetricRow:
    """Compute full-ranking MRR and cutoff metrics from explicit qrels.

Grades must be integers 0..3. Positive grades define binary relevance;
nDCG uses gain 2**grade-1. Precision divides by requested k even for short
rankings. Recall divides by ALL positive qrels, not returned positives.
No-positive queries have None for every effectiveness metric and must be
counted separately. Unknown ranked IDs and duplicates raise ValueError.
"""
    if not ks or any(isinstance(k, bool) or not isinstance(k, int) or k <= 0 for k in ks):
        raise ValueError("Cutoffs must be positive integers")
    if len(set(ks)) != len(ks):
        raise ValueError("Cutoffs must be unique")
    for doc_id, grade in relevance.items():
        _identifier(doc_id)
        if isinstance(grade, bool) or not isinstance(grade, int) or not 0 <= grade <= 3:
            raise ValueError("Relevance grades must be integers in 0..3")
    seen = set()
    for doc_id in ranked_ids:
        _identifier(doc_id)
        if doc_id in seen:
            raise ValueError(f"Duplicate ranked ID: {doc_id}")
        if doc_id not in relevance:
            raise ValueError(f"Unjudged ranked ID: {doc_id}")
        seen.add(doc_id)
    n_relevant = sum(grade > 0 for grade in relevance.values())
    result: MetricRow = {"n_relevant": n_relevant, "n_ranked": len(ranked_ids),
                         "no_relevant": n_relevant == 0}
    flags = [relevance[doc_id] > 0 for doc_id in ranked_ids]
    result["MRR"] = (next((1 / rank for rank, hit in enumerate(flags, 1) if hit), 0.0)
                     if n_relevant else None)
    ideal = sorted(relevance.values(), reverse=True)
    for k in ks:
        hits = sum(flags[:k])
        dcg = sum((2 ** relevance[doc_id] - 1) / math.log2(rank + 1)
                  for rank, doc_id in enumerate(ranked_ids[:k], 1))
        idcg = sum((2 ** grade - 1) / math.log2(rank + 1)
                   for rank, grade in enumerate(ideal[:k], 1))
        result[f"P@{k}"] = hits / k if n_relevant else None
        result[f"Recall@{k}"] = hits / n_relevant if n_relevant else None
        result[f"Hit@{k}"] = float(hits > 0) if n_relevant else None
        result[f"nDCG@{k}"] = dcg / idcg if n_relevant else None
    if n_relevant and 1 in ks:
        check_mrr_bound(result["MRR"], result["P@1"])
    return result


def aggregate_retrieval(rows: Sequence[MetricRow]) -> dict[str, object]:
    """Macro-average queries with explicit valid denominators and invariants.

Rows must share metric keys and a common no-relevance missingness policy.
For document-macro estimates, first average each document's query scores,
then pass the document mapping to bootstrap_mean.
"""
    names = set(rows[0]) - _METADATA if rows else set()
    if rows and ("MRR" not in names or any(
        name != "MRR" and not re.fullmatch(r"(P|Recall|Hit|nDCG)@[1-9][0-9]*", name)
        for name in names
    )):
        raise ValueError("Invalid retrieval metric schema")
    values: dict[str, list[float]] = {name: [] for name in sorted(names)}
    n_no_relevant = 0
    for row in rows:
        if set(row) != names | _METADATA:
            raise ValueError("Retrieval rows must share metric keys and metadata")
        for name in ("n_relevant", "n_ranked"):
            if isinstance(row[name], bool) or not isinstance(row[name], int) or row[name] < 0:
                raise ValueError(f"Invalid {name}")
        missing = row["no_relevant"]
        if not isinstance(missing, bool) or missing != (row["n_relevant"] == 0):
            raise ValueError("Inconsistent no-relevance metadata")
        n_no_relevant += missing
        for name in names:
            if (row[name] is None) != missing:
                raise ValueError("Metrics must share no-relevance missingness")
            if not missing:
                value = _number(row[name], name)
                if not 0 <= value <= 1:
                    raise ValueError(f"Invalid effectiveness metric: {name}")
                values[name].append(value)
        if not missing and "P@1" in names:
            check_mrr_bound(row["MRR"], row["P@1"])
    means = {name: fmean(numbers) if numbers else None for name, numbers in values.items()}
    if means.get("MRR") is not None and "P@1" in means:
        check_mrr_bound(means["MRR"], means["P@1"])
    return {"n_queries": len(rows), "n_no_relevant": n_no_relevant,
            "metrics": means, "denominators": {name: len(v) for name, v in values.items()}}


def _document_values(values: Mapping[str, float | None]) -> dict[str, float | None]:
    return {_identifier(doc_id): None if value is None else _number(value, doc_id)
            for doc_id, value in values.items()}


def bootstrap_mean(
    document_values: Mapping[str, float | None], *, seed: int = 42,
    n_resamples: int = 2000, confidence: float = 0.95,
) -> dict[str, float | int | None]:
    """Percentile bootstrap over equally weighted documents, not queries.

Each input value must already be one document's score. None is excluded
and counted. Fewer than two valid documents yield no confidence interval.
The interval describes sampling variability, not LLM-judge correctness.
"""
    checked = _document_values(document_values)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if isinstance(n_resamples, bool) or not isinstance(n_resamples, int) or n_resamples <= 0:
        raise ValueError("n_resamples must be a positive integer")
    confidence = _number(confidence, "confidence")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between zero and one")
    values = [checked[key] for key in sorted(checked) if checked[key] is not None]
    n_docs = len(values)
    result = {"mean": fmean(values) if values else None, "low": None, "high": None,
              "n_documents": n_docs, "n_missing": len(checked) - n_docs,
              "seed": seed, "n_resamples": n_resamples, "confidence": confidence}
    if n_docs < 2:
        return result
    rng = random.Random(seed)
    draws = sorted(fmean(rng.choices(values, k=n_docs)) for _ in range(n_resamples))
    for name, probability in (("low", (1 - confidence) / 2),
                              ("high", (1 + confidence) / 2)):
        position = (n_resamples - 1) * probability
        lower = math.floor(position)
        upper = math.ceil(position)
        result[name] = draws[lower] + (draws[upper] - draws[lower]) * (position - lower)
    return result


def bootstrap_paired_delta(
    baseline: Mapping[str, float | None], candidate: Mapping[str, float | None],
    *, seed: int = 42, n_resamples: int = 2000, confidence: float = 0.95,
) -> dict[str, float | int | None]:
    """Bootstrap candidate-minus-baseline using paired document differences.

Document ID sets must match. A document missing from either condition's
valid scores is excluded as a pair and counted in n_missing.
"""
    baseline = _document_values(baseline)
    candidate = _document_values(candidate)
    if baseline.keys() != candidate.keys():
        raise ValueError("Paired bootstrap requires identical document ID sets")
    differences = {doc_id: candidate[doc_id] - value
                   if value is not None and candidate[doc_id] is not None else None
                   for doc_id, value in baseline.items()}
    return bootstrap_mean(differences, seed=seed, n_resamples=n_resamples,
                          confidence=confidence)
