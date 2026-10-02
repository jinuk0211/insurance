"""Metered Anthropic Messages calls with immutable request/response artifacts.

No heuristic fallback, automatic model substitution or implicit retries. This
module deliberately uses the standard library so evaluation needs no SDK.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

# USD / million tokens, official Anthropic pricing checked 2026-09-05.
PRICES = {
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-sonnet-4-5-20250929": (3.0, 15.0),
}


class ModelFailure(RuntimeError):
    """A model response is unavailable, unmetered or not usable as evidence."""


def parse_object(text: str) -> dict:
    """Accept exactly a JSON object, optionally in one Markdown code fence."""
    value = re.sub(r"\A```(?:json)?\s*|\s*```\Z", "", text.strip())
    try:
        obj = json.loads(value)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ModelFailure("Response is not a complete JSON object") from exc
    if not isinstance(obj, dict):
        raise ModelFailure("Response root must be an object")
    return obj


def load_api_key(root: Path) -> str:
    """Read only the required credential and never return it in diagnostics."""
    import os

    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    for name in (".env.local", ".env"):
        path = root / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and key.strip() == "ANTHROPIC_API_KEY":
                value = value.strip().strip("\"'")
                if value:
                    return value
    raise ModelFailure("ANTHROPIC_API_KEY is missing")


def write_json(path: Path, value: object) -> None:
    """Write derived experiment data, not source code."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


class ModelClient:
    """Sequential client with a persistent spend ceiling and content-address cache."""

    def __init__(self, directory: Path, api_key: str, budget_usd: float = 20.0):
        if not api_key:
            raise ModelFailure("Missing model API key")
        if type(budget_usd) not in (int, float) or not math.isfinite(budget_usd) or budget_usd < 0:
            raise ModelFailure("Pilot budget must be finite and nonnegative")
        self.directory = directory
        self.api_key = api_key
        self.budget_usd = budget_usd
        self.directory.mkdir(parents=True, exist_ok=True)

    @property
    def spent_usd(self) -> float:
        records = [json.loads(p.read_text(encoding="utf-8"))
                   for p in self.directory.glob("*/record.json")]
        return sum(r["cost_usd"] if r.get("cost_usd") is not None
                   else r["reserved_usd"] for r in records)

    def _send(self, payload: dict) -> dict:
        request = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise ModelFailure(f"Provider HTTP {exc.code}; no fallback performed") from None
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ModelFailure(f"Provider transport failure: {type(exc).__name__}") from None

    def call(self, label: str, model: str, system: str, prompt: str,
             max_tokens: int = 2400, schema: dict | None = None) -> dict:
        if type(max_tokens) is not int or not 1 <= max_tokens <= 10000:
            raise ModelFailure("max_tokens must be an integer in 1..10000")
        if model not in PRICES:
            raise ModelFailure("Model must have an explicitly verified price")
        payload = {"model": model, "max_tokens": max_tokens, "temperature": 0,
                   "system": system, "messages": [{"role": "user", "content": prompt}]}
        if schema is not None:
            payload["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        request_id = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        folder = self.directory / request_id
        record_path = folder / "record.json"
        if record_path.exists():
            record = json.loads(record_path.read_text(encoding="utf-8"))
            if record["status"] != "success":
                raise ModelFailure(f"Prior failed request {request_id}; explicit retry required")
            return {**record, "cache_hit": True}
        if folder.exists():
            raise ModelFailure(f"Incomplete request {request_id}; inspect before retry")
        input_price, output_price = PRICES[model]
        # UTF-8 bytes plus overhead is a conservative input-token reservation.
        reservation = ((len(serialized.encode("utf-8")) + 1024) * input_price
                       + max_tokens * output_price) / 1_000_000
        if self.spent_usd + reservation > self.budget_usd:
            raise ModelFailure("Pilot budget would be exceeded; no request sent")
        write_json(folder / "request.json", payload)
        started = time.perf_counter()
        record = {"request_id": request_id, "label": label, "requested_model": model,
                  "status": "pending", "cost_usd": None,
                  "reserved_usd": reservation, "cache_hit": False}
        # Persist the worst-case reservation before a possibly charged request.
        write_json(record_path, record)
        try:
            response = self._send(payload)
            write_json(folder / "response.json", response)
            record["resolved_model"] = response.get("model")
            if record["resolved_model"] != model:
                raise ModelFailure("Provider model is missing or differs from the pinned model")
            usage = response.get("usage", {})
            if not all(type(usage.get(k)) is int and usage[k] >= 0
                       for k in ("input_tokens", "output_tokens")):
                raise ModelFailure("Missing or invalid provider token usage")
            if any(type(usage.get(k, 0)) is not int or usage.get(k, 0) < 0
                   for k in ("cache_read_input_tokens", "cache_creation_input_tokens")):
                raise ModelFailure("Invalid provider cache token usage")
            record["usage"] = usage
            record["cost_usd"] = (usage["input_tokens"] * input_price
                                  + usage["output_tokens"] * output_price
                                  + usage.get("cache_read_input_tokens", 0) * input_price * .1
                                  + usage.get("cache_creation_input_tokens", 0) * input_price * 1.25) / 1_000_000
            if response.get("stop_reason") != "end_turn":
                raise ModelFailure("Response did not finish normally")
            output = "".join(block["text"] for block in response.get("content", [])
                             if block.get("type") == "text")
            record["output"] = parse_object(output)
            record["status"] = "success"
        except (ModelFailure, ValueError, KeyError, TypeError) as exc:
            record["status"] = "failure"
            record["error"] = str(exc)
            raise ModelFailure(str(exc)) from None
        finally:
            record["latency_seconds"] = time.perf_counter() - started
            write_json(record_path, record)
        return record
