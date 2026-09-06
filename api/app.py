"""FastAPI surface for OpenEval2 (hotel reviews).

Endpoints (SPEC §6):
  GET /health              status + table counts
  GET /stats               {total, ok, needs_review, unlabeled}
  GET /hotels              top-50 hotels by review count (filter dropdown)
  GET /rows                limit/offset + rating(status)/hotel filters
  GET /export.csv          same filters, Excel-friendly BOM CSV (spec header)
  GET /metrics             statuses + gold agree (v2) + A/B run comparison
  POST /rows/{id}/gold     save a validated gold theme (v2; 400 on invalid)

Status is always DERIVED at query time from config rules — never stored.
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run as a script

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

import config
import db as db_module

app = FastAPI(title="OpenEval2 — hotel reviews", version="2.0.0")

EXPORT_HEADER = ["id", "hotel", "rating", "text", "label_a", "label_b",
                 "agree", "status", "gold_label"]  # exact header per Flow 7 / TS26


class GoldIn(BaseModel):
    gold_label: str


def _joined_rows(db_path=None) -> list[dict]:
    """Reviews LEFT JOIN labels, each with derived status (config is the source)."""
    with db_module.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT r.id, r.hotel, r.nationality, r.rating, r.text, r.text_pos, "
            "       r.review_date, r.word_count, "
            "       l.label_a, l.label_b, l.agree, l.llm_error, l.error, l.gold_label "
            "FROM reviews r LEFT JOIN labels l ON l.review_id = r.id ORDER BY r.id"
        ).fetchall()
    out = []
    for r in rows:
        # "labeled" = at least one A/B label exists. A gold-only labels row (gold
        # saved on an unsampled row) must NOT flip the row to labeled/needs_review —
        # its status stays derived by status_unlabeled.
        labeled = r["label_a"] is not None or r["label_b"] is not None
        out.append({
            "id": r["id"],
            "hotel": r["hotel"],
            "nationality": r["nationality"],
            "rating": r["rating"],
            "text": r["text"],
            "text_pos": r["text_pos"],
            "review_date": r["review_date"],
            "word_count": r["word_count"],
            "label_a": r["label_a"],
            "label_b": r["label_b"],
            "agree": bool(r["agree"]),
            "llm_error": bool(r["llm_error"]),
            "error": r["error"],
            "gold_label": r["gold_label"],
            "labeled": labeled,
        })
    for row in out:
        if row["labeled"]:
            row["status"] = config.status_for(
                row["word_count"], row["label_a"], row["label_b"],
                llm_error=row["llm_error"], rating=row["rating"])
        else:
            row["status"] = config.status_unlabeled(row["word_count"])
    return out


def _filter_rows(rows: list[dict], rating: float | None = None,
                 rating_min: float | None = None, rating_max: float | None = None,
                 hotel: str | None = None, status: str | None = None) -> list[dict]:
    matched = rows
    if rating is not None:
        matched = [r for r in matched if r["rating"] == rating]
    if rating_min is not None:
        matched = [r for r in matched if r["rating"] is not None and r["rating"] >= rating_min]
    if rating_max is not None:
        matched = [r for r in matched if r["rating"] is not None and r["rating"] <= rating_max]
    if hotel is not None:
        matched = [r for r in matched if r["hotel"] == hotel]
    if status is not None:
        matched = [r for r in matched if r["status"] == status]
    return matched


def _visible(row: dict) -> dict:
    """SPEC §6 row shape. `error` is appended only when set (Flow 6 / TS13)."""
    out = {k: row[k] for k in (
        "id", "text", "text_pos", "rating", "hotel", "nationality",
        "label_a", "label_b", "agree", "status", "gold_label")}
    if row.get("error"):
        out["error"] = row["error"]
    return out


@app.get("/health")
def health():
    return {"status": "ok", **db_module.counts()}


@app.get("/stats")
def stats():
    counts = {status: 0 for status in config.STATUSES}
    for row in _joined_rows():
        counts[row["status"]] += 1
    return {"total": sum(counts.values()), **counts}


@app.get("/hotels")
def hotels():
    """Distinct hotels by review count, capped at the 50 most frequent (SPEC §6)."""
    with db_module.connect() as conn:
        rows = conn.execute(
            "SELECT hotel, COUNT(*) AS n FROM reviews "
            "WHERE hotel IS NOT NULL GROUP BY hotel "
            "ORDER BY n DESC, hotel LIMIT ?",
            (config.HOTELS_TOP_N,),
        ).fetchall()
    return {"hotels": [{"name": r["hotel"], "count": r["n"]} for r in rows]}


@app.get("/rows")
def rows(
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    rating: float | None = Query(None),
    rating_min: float | None = Query(None),
    rating_max: float | None = Query(None),
    hotel: str | None = Query(None),
    status: Literal["ok", "needs_review", "unlabeled"] | None = Query(None),
):
    matched = _filter_rows(_joined_rows(), rating, rating_min, rating_max, hotel, status)
    page = [_visible(r) for r in matched[offset: offset + limit]]
    return {"total": len(matched), "offset": offset, "limit": limit, "rows": page}


@app.get("/export.csv")
def export_csv(
    rating: float | None = Query(None),
    rating_min: float | None = Query(None),
    rating_max: float | None = Query(None),
    hotel: str | None = Query(None),
    status: Literal["ok", "needs_review", "unlabeled"] | None = Query(None),
):
    matched = _filter_rows(_joined_rows(), rating, rating_min, rating_max, hotel, status)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(EXPORT_HEADER)
    for r in matched:
        writer.writerow([r["id"], r["hotel"], r["rating"], r["text"],
                         r["label_a"], r["label_b"], "yes" if r["agree"] else "no",
                         r["status"], r["gold_label"] or ""])
    content = "\ufeff" + buf.getvalue()   # UTF-8 BOM so Excel opens it (TS26)
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=export.csv"},
    )


@app.post("/rows/{row_id}/gold")
def save_gold(row_id: int, body: GoldIn):
    """v2: save a human gold theme. Never overwrites A/B labels (SPEC §5.6)."""
    label = body.gold_label.strip()
    if not config.is_valid_theme(label):
        raise HTTPException(
            status_code=400,
            detail=f"gold_label must be one of {', '.join(config.THEMES)}",
        )
    with db_module.connect() as conn:
        exists = conn.execute("SELECT id FROM reviews WHERE id = ?", (row_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="row not found")
        conn.execute(
            "INSERT INTO labels (review_id, gold_label) VALUES (?, ?) "
            "ON CONFLICT(review_id) DO UPDATE SET gold_label=excluded.gold_label",
            (row_id, label),
        )
    for row in _joined_rows():
        if row["id"] == row_id:
            return _visible(row)
    raise HTTPException(status_code=404, detail="row not found")  # pragma: no cover


@app.get("/metrics")
def metrics():
    joined = _joined_rows()
    status_counts = {status: 0 for status in config.STATUSES}
    gold_rows = []
    labeled = 0
    for row in joined:
        status_counts[row["status"]] += 1
        if row["labeled"]:
            labeled += 1
        if row["gold_label"]:
            gold_rows.append(row)
    gold_count = len(gold_rows)
    agree_with_gold = None
    if gold_count >= config.GOLD_MIN_FOR_AGREEMENT:
        agree = sum(1 for r in gold_rows if r["label_a"] == r["gold_label"])
        agree_with_gold = round(agree / gold_count, 4)

    with db_module.connect() as conn:
        runs = conn.execute(
            "SELECT run_id, prompt_version, n, cost, p50_ms, created_at "
            "FROM ab_runs ORDER BY run_id DESC LIMIT 2"
        ).fetchall()
        ab = {"runs": [dict(r) for r in reversed(runs)]}
        if len(runs) == 2:
            r1, r2 = (runs[1]["run_id"], runs[0]["run_id"])
            rows = conn.execute(
                "SELECT a.label AS l1, b.label AS l2 FROM ab_labels a "
                "JOIN ab_labels b ON b.review_id = a.review_id AND b.run_id = ? "
                "WHERE a.run_id = ?",
                (r2, r1),
            ).fetchall()
            compared = len(rows)
            agreed = sum(1 for r in rows if r["l1"] == r["l2"])
            ab["comparison"] = {
                "runs": [runs[1]["prompt_version"], runs[0]["prompt_version"]],
                "n": compared,
                "agree": round(agreed / compared, 4) if compared else None,
            }
        else:
            ab["comparison"] = None

    return {
        "total": sum(status_counts.values()),
        **status_counts,
        "labeled": labeled,
        "gold_count": gold_count,
        "agree_with_gold": agree_with_gold,
        "ab": ab,
    }
