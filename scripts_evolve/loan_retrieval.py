"""Prepared-pool reuse around the exact original loan Ours retriever.

No query-result cache, new ranking formula, model request or runtime default change.
"""
from __future__ import annotations

import ast
from collections import defaultdict
from copy import deepcopy
import math
from pathlib import Path
import re

from scripts_evolve.loan_reference import ORIGINAL_PATH, ORIGINAL_SHA256
from scripts_evolve.main_preflight import checked_path


def load_retrieval(root: Path) -> dict:
    """Load only hash-verified pure declarations; never run module/API initializers."""
    path = checked_path(root, ORIGINAL_PATH, ORIGINAL_SHA256)
    names = {'LOAN_TAXONOMY', 'tokenize', 'build_idf', 'tfidf_vec', 'cosine',
             'bm25_scores', 'retrieve', 'extract_queries'}
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    nodes = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in names)
             or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets))]
    namespace = {'re': re, 'math': math, 'defaultdict': defaultdict}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


class PreparedLoanRetriever:
    """Own one frozen ordered pool; reuse only query-independent preparation."""

    def __init__(self, pool: list[dict], root: Path):
        if len({r['chunk_id'] for r in pool}) != len(pool):
            raise ValueError('Unknown duplicate chunk identity')
        self._pool = deepcopy(pool)
        self._original = load_retrieval(root)
        tokenize = self._original['tokenize']
        tokens = {r['text']: tokenize(r['text']) for r in self._pool}
        self._original['tokenize'] = lambda text: tokens[text] if text in tokens else tokenize(text)
        self._bm25 = None
        self.scoring_calls = 0
        self.fallback_scoring_calls = 0
        self.backend = 'original_tf_overlap_fallback'
        if self._pool:
            try:
                from rank_bm25 import BM25Okapi
                self._bm25 = BM25Okapi([tokens[r['text']] for r in self._pool])
                self.backend = 'rank_bm25.BM25Okapi'
            except Exception:
                # Preserve the original bm25_scores fallback, including empty vocabulary.
                self._bm25 = None
        self._original['bm25_scores'] = self._scores

    def _scores(self, query_tokens: list[str], docs_tokens: list[list[str]]) -> list[float]:
        self.scoring_calls += 1
        if self._bm25 is not None:
            try:
                return self._bm25.get_scores(query_tokens).tolist()
            except Exception:
                # Original scoring uses TF overlap on any BM25 backend failure.
                pass
        self.fallback_scoring_calls += 1
        q_set = set(query_tokens)
        return [sum(1 for t in doc if t in q_set) / max(len(doc), 1) for doc in docs_tokens]

    def retrieve(self, query: dict, top_k: int = 5) -> list[dict]:
        """Return detached original rows; no caller can mutate the prepared pool."""
        return deepcopy(self._original['retrieve']('Ours', query, self._pool, top_k))
