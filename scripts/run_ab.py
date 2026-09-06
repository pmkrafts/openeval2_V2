"""Prompt A/B (v2): run two prompt versions on the SAME ids -> ab_runs/ab_labels.

Usage:
    python scripts/run_ab.py [--count 200] [--seed 7] [--provider mock|llm] [--db DB]

Default provider is mock (offline, key-free). With `--provider llm`, prompt v1
and v2 are both sent to the model over the OpenAI-compatible endpoint (.env).
Each run records n, cost (LLM usage * config prices), p50 latency, timestamp —
the /metrics endpoint compares the two most recent runs (SPEC v2 / Flow 9).

Mock runs use the same deterministic labeler for both versions, so v1-vs-v2
agreement is 1.0 (cheap CI signal: two run records exist, agree is well-defined).
"""
from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run as a script

import httpx

import config
import db as db_module
from scripts.label_sample import (MockLabeler, LLMLabeler,
                                  build_prompt, load_dotenv, LLM_MODEL)

load_dotenv()

PRICE_PER_1M = {"input": 0.15, "output": 0.60}   # illustrative gpt-4o-mini pricing


def _llm_call_with_metrics(client, url, headers, payload) -> tuple:
    """Returns (label, invalid, error, cost, ms)."""
    started = time.monotonic()
    try:
        resp = client.post(url, json=payload, headers=headers, timeout=60.0)
        resp.raise_for_status()
        body = resp.json()
        usage = body.get("usage", {})
        cost = (
            usage.get("prompt_tokens", 0) / 1e6 * PRICE_PER_1M["input"]
            + usage.get("completion_tokens", 0) / 1e6 * PRICE_PER_1M["output"]
        )
        content = body["choices"][0]["message"]["content"]
        import json as _json
        try:
            raw = _json.loads(content).get("label")
        except (_json.JSONDecodeError, AttributeError):
            raw = content.strip()
        from scripts.label_sample import sanitize_label
        label, invalid = sanitize_label(raw)
        return label, invalid, None, cost, (time.monotonic() - started) * 1000
    except Exception as exc:
        return None, False, f"{type(exc).__name__}: {exc}", 0.0, 0.0


def _mock_call(text: str) -> tuple:
    started = time.monotonic()
    label = MockLabeler().label(text)
    return label, False, None, 0.0, (time.monotonic() - started) * 1000


def _run_version(db_path, prompt_version: str, ids: list[int], provider: str) -> dict:
    with db_module.connect(db_path) as conn:
        texts = {
            r["id"]: r["text"]
            for r in conn.execute(
                f"SELECT id, text FROM reviews WHERE id IN ({','.join('?' * len(ids))})",
                ids,
            )
        }
    started = time.monotonic()
    if provider == "mock":
        with ThreadPoolExecutor(max_workers=16) as pool:
            outcomes = dict(zip(ids, pool.map(_mock_call, (texts[i] for i in ids))))
    else:
        labeler = LLMLabeler(prompt_version)
        url = f"{os.environ.get('OPENEND_LLM_BASE_URL', 'https://api.openai.com/v1')}/chat/completions"
        headers = {"Authorization": f"Bearer {labeler.key}"}
        payloads = {
            i: {"model": LLM_MODEL, "messages": [
                {"role": "system", "content": "You classify hotel complaints."},
                {"role": "user", "content": build_prompt(prompt_version, texts[i])},
            ], "temperature": 0, "response_format": {"type": "json_object"}}
            for i in ids
        }
        with ThreadPoolExecutor(max_workers=16) as pool:
            def work(i):
                return i, _llm_call_with_metrics(httpx.Client(), url, headers, payloads[i])
            outcomes = dict(pool.map(work, ids))

    durations = [o[4] for o in outcomes.values() if o[4]]
    cost = sum(o[3] for o in outcomes.values() if o[3] is not None)
    errors = sum(1 for o in outcomes.values() if o[2])
    with db_module.connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO ab_runs (prompt_version, n, cost, p50_ms, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (prompt_version, len(ids), round(cost, 6),
             round(statistics.median(durations), 2) if durations else None,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        run_id = cur.lastrowid
        conn.executemany(
            "INSERT OR REPLACE INTO ab_labels (run_id, review_id, label) VALUES (?, ?, ?)",
            [(run_id, i, outcomes[i][0]) for i in ids],
        )
    return {"run_id": run_id, "prompt_version": prompt_version, "n": len(ids),
            "cost": round(cost, 6), "errors": errors,
            "elapsed_s": round(time.monotonic() - started, 2)}


def run_ab(db_path=None, count: int | None = None, seed: int = 7,
           provider: str = "mock") -> dict:
    db_module.init_db(db_path)
    if count is None:
        count = config.AB_SAMPLE_SIZE
    with db_module.connect(db_path) as conn:
        all_ids = [r["id"] for r in conn.execute("SELECT id FROM reviews ORDER BY id")]
    ids = random.Random(seed).sample(all_ids, min(count, len(all_ids)))
    first = _run_version(db_path, "v1", ids, provider)
    second = _run_version(db_path, "v2", ids, provider)
    return {"ids": len(ids), "runs": [first, second], "provider": provider}


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=config.AB_SAMPLE_SIZE)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--provider", choices=["mock", "llm"], default="mock")
    parser.add_argument("--db", default=None)
    args = parser.parse_args(argv)
    result = run_ab(db_path=args.db, count=args.count, seed=args.seed, provider=args.provider)
    print(f"ids={result['ids']} provider={result['provider']}")
    for run in result["runs"]:
        print(f"  run {run['run_id']} [{run['prompt_version']}] n={run['n']} "
              f"cost=${run['cost']} errors={run['errors']} elapsed={run['elapsed_s']}s")


if __name__ == "__main__":
    main()
