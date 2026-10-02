"""Codex transport tests use recorded-style events, never a live model."""
import json
import subprocess

import pytest

from scripts.pilot.client import ModelFailure
from scripts.pilot.codex_client import (
    MODEL,
    SPARK_MODEL,
    CodexClient,
    parse_events,
    verify_codex_storage,
)


def event_stream(output='{"ok": true}', usage=None, extra=None):
    events = [{"type": "thread.started", "thread_id": "test-thread"},
              {"type": "turn.started"}]
    events.extend(extra or [])
    events.extend([
        {"type": "item.completed", "item": {"type": "agent_message", "text": output}},
        {"type": "turn.completed", "usage": usage or {
            "input_tokens": 100, "cached_input_tokens": 20, "output_tokens": 8,
            "reasoning_output_tokens": 0}},
    ])
    return "\n".join(json.dumps(event) for event in events)


def make_client(tmp_path, monkeypatch, **kwargs):
    executable = tmp_path / "codex.exe"
    executable.write_bytes(b"test binary, never executed")
    monkeypatch.setattr(CodexClient, "_version", lambda self: "codex-cli 0.153.4")
    return CodexClient(tmp_path / "calls", executable, **kwargs)


def test_success_cache_and_honest_billing(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    seen = []
    def execute(command, **kwargs):
        seen.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, event_stream(), "startup warning")
    monkeypatch.setattr(subprocess, "run", execute)
    result = client.call("test", MODEL, "system", "prompt", schema={"type": "object"})
    cached = client.call("other-label", MODEL, "system", "prompt", schema={"type": "object"})
    assert result["output"] == {"ok": True}
    assert result["cost_usd"] is None
    assert result["billing_kind"] == "chatgpt_subscription"
    assert result["resolved_model"] is None
    assert cached["cache_hit"] is True
    assert len(seen) == 1
    assert client.usage_summary()["observed_total_tokens"] == 108
    command, kwargs = seen[0]
    assert "--ignore-rules" not in command
    assert "read-only" in command and "--ignore-user-config" in command
    assert kwargs["shell"] is False
    assert kwargs["input"].endswith("prompt")
    assert list(client.directory.glob("*/events.jsonl"))


def test_explicit_spark_model_is_provenanced_and_cannot_mix(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch, model=SPARK_MODEL)
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs:
                        subprocess.CompletedProcess(command, 0, event_stream(), ""))
    client.call("spark", SPARK_MODEL, "system", "prompt")
    path = next(client.directory.glob("*/record.json"))
    record = verify_codex_storage(path, SPARK_MODEL)
    assert record["requested_model"] == SPARK_MODEL
    assert client.provenance()["generator_model"] == SPARK_MODEL
    assert SPARK_MODEL in json.loads(path.with_name("command.json").read_text())
    with pytest.raises(ModelFailure):
        verify_codex_storage(path, MODEL)
    with pytest.raises(ModelFailure, match="model"):
        client.call("mixed", MODEL, "system", "different")


@pytest.mark.parametrize("extra", [
    [{"type": "turn.failed", "error": {"message": "failed"}}],
    [{"type": "item.completed", "item": {"type": "command_execution"}}],
    [{"type": "item.started", "item": {"type": "web_search"}}],
])
def test_failed_or_tool_using_run_rejected(extra):
    with pytest.raises(ModelFailure):
        parse_events(event_stream(extra=extra))


@pytest.mark.parametrize("usage", [
    {"input_tokens": True, "output_tokens": 8},
    {"input_tokens": 10, "output_tokens": -1},
    {"input_tokens": 10},
    {"input_tokens": 10, "output_tokens": 8, "cached_input_tokens": 11},
])
def test_bad_usage_rejected(usage):
    with pytest.raises(ModelFailure):
        parse_events(event_stream(usage=usage))


def test_failure_persisted_and_not_retried(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    def fail(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, '{"type":"turn.failed"}', "failure")
    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(ModelFailure):
        client.call("test", MODEL, "system", "prompt")
    record = json.loads(next(client.directory.glob("*/record.json")).read_text())
    assert record["status"] == "failure"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("must not retry"))
    with pytest.raises(ModelFailure, match="reconciliation"):
        client.call("test", MODEL, "system", "prompt")
    with pytest.raises(ModelFailure, match="reconciliation"):
        client.call("test", MODEL, "system", "different")


def test_call_budget_stops_before_process(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch, max_calls=0)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("budget must stop"))
    with pytest.raises(ModelFailure, match="budget"):
        client.call("test", MODEL, "system", "prompt")


def test_timeout_preserves_partial_output(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    def fail(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 180, output=b'{"type":"turn.started"}', stderr=b"timeout")
    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(ModelFailure, match="timeout"):
        client.call("test", MODEL, "system", "prompt")
    assert next(client.directory.glob("*/events.jsonl")).read_text() == '{"type":"turn.started"}'


def test_reject_wrong_model_and_invalid_limits(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    with pytest.raises(ModelFailure, match="model"):
        client.call("test", "other", "system", "prompt")
    with pytest.raises(ValueError):
        make_client(tmp_path, monkeypatch, max_calls=True)
    with pytest.raises(ValueError, match="Unsupported"):
        make_client(tmp_path, monkeypatch, model="unknown")


def test_incomplete_output_is_not_success():
    for text in ("", '{"type":"turn.started"}', event_stream(output="not json")):
        with pytest.raises(ModelFailure):
            parse_events(text)


@pytest.mark.parametrize("damage", ["output", "usage", "billing", "model", "stdin", "command"])
def test_native_verification_rejects_tampering(tmp_path, monkeypatch, damage):
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs:
                        subprocess.CompletedProcess(command, 0, event_stream(), ""))
    client.call("test", MODEL, "system", "prompt")
    path = next(client.directory.glob("*/record.json"))
    record = json.loads(path.read_text())
    assert verify_codex_storage(path) == record
    if damage == "stdin":
        path.with_name("stdin.txt").write_text("different")
    elif damage == "command":
        path.with_name("command.json").write_text('["wrong"]')
    else:
        if damage == "output":
            record["output"] = {"ok": 1}
        elif damage == "usage":
            record["usage"]["input_tokens"] = True
        elif damage == "billing":
            record["cost_usd"] = 0
        else:
            record["resolved_model"] = MODEL
        path.write_text(json.dumps(record))
    with pytest.raises(ModelFailure):
        verify_codex_storage(path)


def test_report_replays_native_codex_records(tmp_path, monkeypatch):
    from scripts.pilot.report import RecordedClient, summarize_costs, verify_call_storage
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs:
                        subprocess.CompletedProcess(command, 0, event_stream(), ""))
    original = client.call("test", MODEL, "system", "prompt")
    record = verify_call_storage(next(client.directory.glob("*/record.json")))
    replay = RecordedClient([record], client.provenance())
    assert replay.call("replay", MODEL, "system", "prompt") == original
    cost = summarize_costs([record])
    assert cost["subscription_call_count"] == 1
    assert cost["actual_cost_estimate_usd"] is None
    with pytest.raises(ValueError, match="No verified"):
        replay.call("replay", MODEL, "system", "changed")


def test_missing_usage_blocks_next_request(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs:
                        subprocess.CompletedProcess(command, 0, event_stream(), ""))
    client.call("test", MODEL, "system", "prompt")
    path = next(client.directory.glob("*/record.json"))
    record = json.loads(path.read_text())
    record.pop("usage")
    path.write_text(json.dumps(record))
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("invalid accounting"))
    with pytest.raises(ModelFailure, match="reconciliation"):
        client.call("next", MODEL, "system", "different")


@pytest.mark.parametrize("extra", [
    [{"type": "unexpected_tool"}],
    [{"type": "item.completed", "item": {"type": "error", "message": "bad"}}],
])
def test_unknown_or_error_events_fail_closed(extra):
    with pytest.raises(ModelFailure):
        parse_events(event_stream(extra=extra))


def test_only_observed_startup_warning_is_allowed():
    from scripts.pilot.codex_client import SKILL_BUDGET_WARNING

    messages = [
        SKILL_BUDGET_WARNING,
        ("Exceeded skills context budget. All skill descriptions were removed and 56 "
         "additional skills were not included in the model-visible skills list."),
    ]
    for message in messages:
        warning = {"type": "item.completed", "item": {"type": "error", "message": message}}
        output, _, _ = parse_events(event_stream(extra=[warning]))
        assert output == {"ok": True}
        events = event_stream().splitlines()
        events.insert(-1, json.dumps(warning))
        with pytest.raises(ModelFailure):
            parse_events("\n".join(events))


@pytest.mark.parametrize("status", ["Not logged in; previous: Logged in using ChatGPT", "API key"])
def test_auth_attribution_requires_exact_status(tmp_path, monkeypatch, status):
    client = object.__new__(CodexClient)
    client.executable = tmp_path / "codex.exe"
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs:
                        subprocess.CompletedProcess(command, 0, status, ""))
    with pytest.raises(ModelFailure, match="subscription"):
        client._version()
