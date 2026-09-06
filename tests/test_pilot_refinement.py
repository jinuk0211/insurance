"""Budget/role invariants for bounded refinement, using a deterministic fake."""
from copy import deepcopy

import pytest

from scripts.pilot.refinement import proposal_chain, select_incumbent


BASE = {"instruction": "Find supported issues.", "preprocessor": "layout_cleanup",
        "retriever": "bm25", "k1": 1.5, "b": .75}


class FakeClient:
    def __init__(self, output):
        self.output = output
        self.requests = []

    def call(self, label, model, system, prompt, max_tokens, schema=None):
        self.requests.append((system, prompt, max_tokens))
        return {"request_id": str(len(self.requests)), "output": deepcopy(self.output),
                "cost_usd": .001, "usage": {"input_tokens": 10, "output_tokens": 10}}


@pytest.mark.parametrize("mode", ["single_role", "three_role", "prompt_only"])
def test_every_condition_has_three_calls_and_same_caps(mode):
    client = FakeClient({"config": BASE, "rationale": "No evidence for a change."})
    result = proposal_chain(client, mode, BASE, [{"score": .3}], seed=42, iteration=1)
    assert len(client.requests) == len(result["calls"]) == 3
    assert {item[2] for item in client.requests} == {1800}
    assert all('"score": 0.3' in item[1] for item in client.requests)
    assert result["candidate"] == BASE


def test_prompt_only_cannot_mutate_retrieval():
    altered = {**BASE, "retriever": "tfidf"}
    client = FakeClient({"config": altered, "rationale": "change"})
    result = proposal_chain(client, "prompt_only", BASE, [], seed=42, iteration=1)
    assert result["candidate"] is None
    assert "prompt-only" in result["error"]
    assert len(client.requests) == 3


def test_incumbent_never_regresses_or_accepts_failures():
    assert not select_incumbent(.5, .49, failures=0)
    assert not select_incumbent(.5, .5, failures=0)
    assert not select_incumbent(.5, .6, failures=1)
    assert select_incumbent(.5, .51, failures=0)
