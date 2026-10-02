"""Model-client tests: no live requests."""
import pytest

from scripts.pilot.client import ModelClient, ModelFailure, parse_object


def test_parse_object_rejects_missing_or_non_object_output():
    assert parse_object('```json\n{"ok": true}\n```') == {"ok": True}
    for value in ('', '[]', 'not json', '{"ok": true} trailing'):
        with pytest.raises(ModelFailure):
            parse_object(value)


def test_missing_key_fails_before_any_call(tmp_path):
    with pytest.raises(ModelFailure, match="key"):
        ModelClient(tmp_path, api_key="", budget_usd=1)


def test_budget_refuses_request_without_network(tmp_path):
    client = ModelClient(tmp_path, api_key="test-only", budget_usd=0)
    with pytest.raises(ModelFailure, match="budget"):
        client.call("test", "claude-haiku-4-5-20251001", "system", "hello")


def test_success_records_usage_and_cache_is_request_specific(tmp_path, monkeypatch):
    response = {"model": "claude-haiku-4-5-20251001", "stop_reason": "end_turn",
                "content": [{"type": "text", "text": '{"ok": true}'}],
                "usage": {"input_tokens": 10, "output_tokens": 5}}
    seen = []
    def fake_send(payload):
        seen.append(payload)
        return response
    client = ModelClient(tmp_path, api_key="test-only", budget_usd=1)
    monkeypatch.setattr(client, "_send", fake_send)
    first = client.call("a", response["model"], "sys", "hello")
    again = client.call("b", response["model"], "sys", "hello")
    assert first["output"] == {"ok": True}
    assert again["cache_hit"] is True
    assert len(seen) == 1
    assert client.spent_usd > 0
    for path in tmp_path.rglob('*.json'):
        assert "test-only" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("response", [
    {"stop_reason": "max_tokens", "usage": {"input_tokens": 2, "output_tokens": 2}, "content": []},
    {"stop_reason": "end_turn", "content": [{"type": "text", "text": '{}'}]},
])
def test_truncated_or_unmetered_response_is_failure(tmp_path, monkeypatch, response):
    client = ModelClient(tmp_path, api_key="test-only", budget_usd=1)
    monkeypatch.setattr(client, "_send", lambda payload: response)
    with pytest.raises(ModelFailure):
        client.call("bad", "claude-haiku-4-5-20251001", "sys", "hello")
    assert list(tmp_path.glob("*/response.json"))


def test_unknown_charge_keeps_reservation_and_blocks_more_calls(tmp_path, monkeypatch):
    client = ModelClient(tmp_path, api_key="test-only", budget_usd=.025)
    def timeout(payload):
        raise ModelFailure("transport timeout")
    monkeypatch.setattr(client, "_send", timeout)
    with pytest.raises(ModelFailure, match="transport"):
        client.call("timeout", "claude-haiku-4-5-20251001", "sys", "hello")
    assert client.spent_usd > .01
    with pytest.raises(ModelFailure, match="budget"):
        client.call("next", "claude-haiku-4-5-20251001", "sys", "new prompt")


@pytest.mark.parametrize("resolved", [None, "different-model"])
def test_missing_or_changed_model_cannot_become_success(tmp_path, monkeypatch, resolved):
    client = ModelClient(tmp_path, api_key="test-only", budget_usd=1)
    response = {"model": resolved, "stop_reason": "end_turn",
                "content": [{"type": "text", "text": '{}'}],
                "usage": {"input_tokens": 10, "output_tokens": 5}}
    monkeypatch.setattr(client, "_send", lambda payload: response)
    with pytest.raises(ModelFailure, match="pinned model"):
        client.call("wrong-model", "claude-haiku-4-5-20251001", "sys", "hello")
    assert client.spent_usd > 0


@pytest.mark.parametrize("budget", [float('nan'), float('inf'), -1, True])
def test_invalid_budget_is_rejected(tmp_path, budget):
    with pytest.raises(ModelFailure, match="finite"):
        ModelClient(tmp_path, api_key="test", budget_usd=budget)


def test_pending_charge_is_reserved_after_restart(tmp_path, monkeypatch):
    client = ModelClient(tmp_path, api_key="test-only", budget_usd=1)
    def timeout(payload):
        raise ModelFailure("timeout")
    monkeypatch.setattr(client, "_send", timeout)
    with pytest.raises(ModelFailure):
        client.call("first", "claude-haiku-4-5-20251001", "sys", "hello")
    resumed = ModelClient(tmp_path, api_key="test-only", budget_usd=1)
    assert resumed.spent_usd == client.spent_usd > 0
