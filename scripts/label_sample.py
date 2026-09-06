"""Label a deterministic random sample twice -> `labels` table (OpenEval2).

Usage:
    python scripts/label_sample.py [--count 200] [--seed 42]
                                   [--provider mock|llm] [--force]

Default provider is `mock` (deterministic, offline, zero cost) so CI and demos
never need a key (SPEC: TS44). Real labeling: `--provider llm` uses an
OpenAI-compatible /chat/completions endpoint configured via .env:

    OPENEND_LLM_KEY        (required for llm; missing/placeholder aborts early)
    OPENEND_LLM_BASE_URL   (default https://api.openai.com/v1)
    OPENEND_LLM_MODEL      (default gpt-4o-mini)

Behavior (SPEC rules L3/L5/L8, Flow 6, TS13):
  * two independent calls per review
  * a failed call is recorded (llm_error + error text) -> row is needs_review
  * invalid output ("dirty!!!") is sanitized to "Other" AND flagged, so the row
    still queues for review (TS13)
  * the run never dies mid-sample; the first root cause is printed at the end
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run as a script

import httpx

import config
import db as db_module

CALL_TIMEOUT = 60.0
WORKERS = 16
_KEY_PLACEHOLDER = "PASTE_YOUR_KEY_HERE"

# OpenAI-compatible chat config (used only by LLMLabeler)
LLM_BASE_URL = os.environ.get("OPENEND_LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.environ.get("OPENEND_LLM_MODEL", "gpt-4o-mini")

# Prompt templates per version (v1 vs v2 = the A/B comparison axis).
PROMPTS = {
    "v1": (
        "Read this hotel guest complaint. Pick ONE theme from "
        f"{', '.join(config.THEMES)}. Reply with JSON only: {{\"label\": \"...\"}}\n\n"
        "Complaint:\n{text}"
    ),
    "v2": (
        "You are an expert hotel customer-experience analyst. A guest wrote a "
        "negative review. Classify the PRIMARY reason for the complaint into exactly "
        f"one of {', '.join(config.THEMES)}. Reply with JSON only: "
        "{\"label\": \"...\"}. Complaint:\n{text}"
    ),
}


def load_dotenv(path: str | Path | None = None) -> None:
    """Load KEY=VALUE lines from a .env file into the environment."""
    path = Path(path) if path else Path(__file__).resolve().parent.parent / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()  # module import: .env supplies defaults for the llm provider


class MockLabeler:
    """Deterministic offline classifier: first hotel keyword hit -> theme, else Other."""

    KEYWORDS = [
        ("location", "Location"), ("area", "Location"),
        ("staff", "Staff"), ("rude", "Staff"), ("service", "Staff"), ("waiter", "Staff"),
        ("room", "Room"), ("bed", "Room"), ("bathroom", "Room"), ("noise", "Room"),
        ("clean", "Cleanliness"), ("dirty", "Cleanliness"), ("smell", "Cleanliness"),
        ("food", "Food"), ("breakfast", "Food"), ("dinner", "Food"), ("restaurant", "Food"),
        ("price", "Price"), ("cost", "Price"), ("expensive", "Price"), ("money", "Price"),
    ]

    def label(self, text: str) -> str:
        low = text.lower()
        for keyword, theme in self.KEYWORDS:
            if keyword in low:
                return theme
        return "Other"


def sanitize_label(raw: str | None) -> tuple[str | None, bool]:
    """Map a model output to (label, was_invalid).

    Valid theme -> (label, False). Anything else (or None) -> ("Other", True):
    stored as Other and flagged so the row still needs review (TS13).
    """
    if raw is None:
        return None, True
    label = raw.strip().strip('"').strip("'").strip()
    if config.is_valid_theme(label):
        return label, False
    return "Other", True


class LLMLabeler:
    """Real labeler over an OpenAI-compatible /chat/completions endpoint."""

    def __init__(self, prompt_version: str = "v1") -> None:
        self.key = os.environ.get("OPENEND_LLM_KEY", "")
        if not self.key or self.key == _KEY_PLACEHOLDER:
            raise SystemExit(
                "OPENEND_LLM_KEY missing or still the placeholder — set it in .env "
                "before using --provider llm"
            )
        self.prompt_version = prompt_version
        self.headers = {"Authorization": f"Bearer {self.key}"}

    def label(self, text: str) -> tuple[str | None, bool, str | None]:
        """Returns (label, was_invalid, error_message)."""
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": "You classify hotel complaints."},
                {"role": "user", "content": PROMPTS[self.prompt_version].format(text=text)},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        try:
            with httpx.Client(timeout=CALL_TIMEOUT) as client:
                resp = client.post(f"{LLM_BASE_URL}/chat/completions", json=payload,
                                   headers=self.headers)
                resp.raise_for_status()
                usage = resp.json().get("usage", {})
                raw = None
                content = resp.json()["choices"][0]["message"]["content"]
                try:
                    raw = json.loads(content).get("label")
                except (json.JSONDecodeError, AttributeError):
                    raw = content.strip()
                label, invalid = sanitize_label(raw)
                return label, invalid, None
        except Exception as exc:  # network, HTTP, parse — row must survive (Flow 6)
            return None, False, f"{type(exc).__name__}: {exc}"


def pick_sample_ids(db_path, count: int, seed: int, force: bool) -> list[int]:
    """Random sample of review ids not yet labeled (all ids when force=True)."""
    with db_module.connect(db_path) as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM reviews ORDER BY id")]
        if not force:
            labeled = {r["review_id"] for r in conn.execute("SELECT review_id FROM labels")}
            ids = [i for i in ids if i not in labeled]
    if count is None:
        count = config.SAMPLE_SIZE
    return random.Random(seed).sample(ids, min(count, len(ids)))


def _call(labeler, text: str, started_at: float) -> tuple:
    """One labeling call -> (label, invalid, error, duration_ms)."""
    try:
        result = labeler.label(text)
        if isinstance(result, str):          # mock labeler
            return result, False, None
        return result                         # llm: (label, invalid, error)
    finally:
        pass


def _run_round(labeler, texts: dict[int, str]) -> tuple[dict, Exception | None]:
    """Label every id once, in parallel. Returns ({id: (label, invalid, error)}, first_error)."""
    first_error = [None]

    def work(item):
        rid, text = item
        try:
            return rid, _call(labeler, text, time.monotonic())
        except Exception as exc:  # belt & braces — never die mid-sample (Flow 6)
            first_error[0] = first_error[0] or exc
            return rid, (None, False, f"{type(exc).__name__}: {exc}")

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = dict(pool.map(work, texts.items()))
    return results, first_error[0]


def label_sample(db_path=None, count: int | None = None, seed: int = 42,
                 provider: str = "mock", force: bool = False,
                 prompt_version: str = "v1") -> dict:
    """Sample `count` unlabeled rows, label twice, upsert into `labels`."""
    db_module.init_db(db_path)
    ids = pick_sample_ids(db_path, count, seed, force)
    labeler = MockLabeler() if provider == "mock" else LLMLabeler(prompt_version)

    with db_module.connect(db_path) as conn:
        texts = {
            r["id"]: r["text"]
            for r in conn.execute(
                f"SELECT id, text FROM reviews WHERE id IN ({','.join('?' * len(ids))})",
                ids,
            )
        } if ids else {}

    round_a, err_a = _run_round(labeler, texts)
    round_b, err_b = _run_round(labeler, texts)

    labeled = 0
    with db_module.connect(db_path) as conn:
        for rid in ids:
            la, a_invalid, a_err = round_a.get(rid, (None, False, "no result"))
            lb, b_invalid, b_err = round_b.get(rid, (None, False, "no result"))
            errored = a_invalid or b_invalid or bool(a_err) or bool(b_err)
            detail = " | ".join(x for x in (a_err, b_err) if x) or None
            if errored and not detail:
                detail = "label sanitized to Other (not in theme list)"
            agree = 1 if config.labels_agree(la, lb) else 0
            conn.execute(
                "INSERT INTO labels (review_id, label_a, label_b, agree, llm_error, error) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(review_id) DO UPDATE SET label_a=excluded.label_a, "
                "label_b=excluded.label_b, agree=excluded.agree, "
                "llm_error=excluded.llm_error, error=excluded.error",
                (rid, la, lb, agree, 1 if errored else 0, detail),
            )
            labeled += 1

    first_error = err_a or err_b
    return {"sample": len(ids), "labeled": labeled, "provider": provider,
            "errors": sum(1 for rid in ids if round_a.get(rid, (None, False, "e"))[2]
                          or round_b.get(rid, (None, False, "e"))[2]),
            "first_error": str(first_error) if first_error else None}


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=config.SAMPLE_SIZE,
                        help=f"sample size (default {config.SAMPLE_SIZE})")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--provider", choices=["mock", "llm"], default="mock")
    parser.add_argument("--force", action="store_true",
                        help="re-label already-labeled rows too")
    parser.add_argument("--db", default=None)
    args = parser.parse_args(argv)
    result = label_sample(db_path=args.db, count=args.count, seed=args.seed,
                          provider=args.provider, force=args.force)
    print(f"sample={result['sample']} labeled={result['labeled']} "
          f"provider={result['provider']} errors={result['errors']}")
    if result["first_error"]:
        print(f"first error: {result['first_error'][:400]}")


if __name__ == "__main__":
    main()
