# openeval2_V2

OpenEval2 — hotel reviews → SQLite → dual-LLM label of a 200-row sample →
human-review queue (`needs_review`) → FastAPI REST → Streamlit dashboard.

An end-to-end data demo built for interviews: 515k public hotel reviews,
a warehouse-shaped 50k store, a deliberately capped LLM spend (200 rows × 2
calls), an automated disagreement / short-text / rating-clash review queue,
optional human **gold** labels and **prompt A/B** (v2), and a dashboard styled
to a brand design system. **No Spark, no Snowflake, no Toluna/survey data, no
employer data** — SQLite is enough by design.

---

## Features

- **Ingest** — deterministic random sample of the Kaggle hotel CSV
  (`--sample 50000 --seed 42`); rows whose negative review is empty or
  `"No Negative"` are **dropped** (complaints-only table; that text is never
  sent to a model); `word_count` computed for every row at ingest.
- **Dual labeling** — one random 200-row sample, two independent LLM calls per
  review (themes: `Location | Staff | Room | Cleanliness | Food | Price | Other`).
- **Review rules** (single source: `config.py`; status is *derived* at query
  time, never stored):
  - `needs_review` ⇔ word_count < 4 **or** labels disagree **or** a label is
    missing **or** an LLM call errored/returned garbage (`"dirty!!!"` → stored
    as `Other` **and** flagged — TS13);
  - v2 **rating clash** ⇔ rating ≤ 4 on the **10-point Booking scale** AND both
    labels `Other` AND word_count ≥ 4;
  - unsampled rows are `unlabeled` — except short texts, which are
    `needs_review` with zero LLM spend.
- **REST API** — `/health`, `/stats`, `/hotels` (top 50), `/rows`
  (limit/offset + hotel / rating / status filters), `/export.csv`
  (Excel-friendly BOM, honors filters), `/metrics`, `POST /rows/{id}/gold`.
- **Dashboard** — Streamlit (≥1.57, replaces the v1 React UI): virtualized
  data grid, stats bar, sidebar filters, `needs_review` red tint + badges,
  gold save, filtered CSV export, metrics view (gold + prompt A/B). Styled from
  `DOCS/design.md` tokens via `.streamlit/config.toml` (single red accent
  `#e60000`, ink/canvas surfaces, pill buttons, Inter font — the Vodafone
  proprietary face is not bundled and no Vodafone brand assets are used).
- **Offline by default** — tests and mock labeling need no dataset download and
  no API key (deterministic mock labeler); real-LLM mode is one flag away.

---

## Requirements

| Component | Requirement | Verified with |
|---|---|---|
| Python | 3.11+ | 3.13 (Windows 11) |
| OS | any (commands below are Windows) | Windows 11 |
| Network | first run only (pip install; optional Inter font fetch at runtime) | — |

Python deps (`requirements.txt`): `pandas`, `fastapi`, `uvicorn[standard]`,
`httpx`, `streamlit>=1.57`, `pytest`. No Node / npm — the whole stack is Python.

---

## Dataset

- **Primary:** *515K Hotel Reviews Data in Europe* (Kaggle, Jiashen Liu; CC0).
  Columns used: `Hotel_Name`, `Reviewer_Nationality`, `Reviewer_Score` (1–10),
  `Positive_Review`, `Negative_Review`, `Review_Date`.
- Store cap: **50,000** sampled rows (seed 42). Label cap: **200** rows (2 calls
  each); never more than 300 rows with a paid model.
- Reviews are 1–10 scores (Booking.com), not 1–5.
- Download from kaggle.com → save the CSV (gitignored). This repo ships no
  dataset contents and no review text. The public demo serves a synthetic
  hotel-shaped CSV — never the Kaggle file.

No dataset handy? The section below seeds from a synthetic CSV with the same
shape; or point `ingest.py` at any CSV with the hotel columns above.

---

## Quickstart

```bash
# 1) Python environment
python -m venv .venv
.venv\Scripts\activate              # Windows; POSIX: source .venv/bin/activate
pip install -r requirements.txt

# 2) Data (pick one)
#    a) real Kaggle CSV -> 50k deterministic sample, empty negatives dropped
python scripts\ingest.py path\to\Hotel_Reviews.csv --sample 50000 --seed 42
#    b) synthetic (no download) — dev/test shape, tiny
python -c "import sys; sys.path.insert(0,'tests'); from conftest import write_review_csv; write_review_csv('data/synthetic.csv')"
python scripts\ingest.py data\synthetic.csv

# 3) Label 200 rows twice (mock, offline) + optional v2 A/B runs
python scripts\label_sample.py --seed 42
python scripts\run_ab.py --count 200 --seed 7

# 4) API + dashboard (two processes, two terminals)
python -m uvicorn api.app:app              # http://127.0.0.1:8000/docs
streamlit run app.py                       # http://127.0.0.1:8501

# 5) Tests (no dataset / key needed)
python -m pytest tests -q                  # 38 passed
```

The Streamlit app talks to the API server-side (`httpx`) — no CORS config.
`OPENEND_API_URL` overrides the API base if it is not on `:8000`.

---

## Real-LLM labeling

Configure once in `.env` (repo root, gitignored — never committed). Real
environment variables win over `.env`.

```
OPENEND_LLM_KEY=PASTE_YOUR_KEY_HERE        # <- your API key
# OPENEND_LLM_BASE_URL=https://api.openai.com/v1   # uncomment if not OpenAI
# OPENEND_LLM_MODEL=gpt-4o-mini                    # default when unset
```

Then:

```bash
python scripts\label_sample.py --seed 42 --provider llm
python scripts\run_ab.py --count 200 --provider llm    # prompt v1 vs v2 on same ids
```

The provider is OpenAI-compatible (`/chat/completions`). Behavior: parallel
labeling (16 workers); two independent calls per review; a failed call is
recorded (`llm_error` + error text) and the row surfaces as `needs_review`; the
run never dies mid-sample; missing/placeholder keys abort before any HTTP call.

**Cost of the sample:** 200 reviews × 2 calls = 400 LLM calls. Illustrative at
`gpt-4o-mini` pricing (≈ $0.15/1M in, $0.60/1M out) ≈ **$0.01 per full sample**.
The other ~37k rows never reach a model. `run_ab.py` records cost + p50 latency
per run for `/metrics`.

---

## API

| Endpoint | Params | Returns |
|---|---|---|
| `GET /health` | — | status + review/label/gold/ab-run counts |
| `GET /stats` | — | `{total, ok, needs_review, unlabeled}` |
| `GET /hotels` | — | top-50 hotels by review count (filter dropdown) |
| `GET /rows` | `limit` (≤2000), `offset`, `hotel`, `status`, `rating`, `rating_min`, `rating_max` | `{total, offset, limit, rows[]}` — id, text, text_pos, rating, hotel, nationality, label_a, label_b, agree, status, gold_label |
| `GET /export.csv` | same filters | attachment CSV, UTF-8 BOM (opens in Excel) |
| `GET /metrics` | — | status counts, labeled, gold_count, agree_with_gold (null < 30 golds), A/B run records + comparison |
| `POST /rows/{id}/gold` | `{"gold_label": "Staff"}` | saves gold (validated theme; 400 on anything else); never overwrites A/B labels |

Interactive docs at `http://127.0.0.1:8000/docs`.

---

## Project structure

```
config.py                Constants + status rules (single source of truth)
db.py                    SQLite schema (reviews, labels, ab_runs, ab_labels)
scripts/ingest.py        CSV -> 50k sample -> reviews (empty negatives dropped)
scripts/label_sample.py  Sample 200 -> two labeling rounds -> labels table
scripts/run_ab.py        Prompt v1 vs v2 on the same ids -> ab_* tables
api/app.py               FastAPI endpoints
app.py                   Streamlit dashboard (client of the API)
.streamlit/config.toml   design.md theme (red #e60000 / ink / canvas / Inter)
tests/                   38 tests, synthetic CSV, no keys/network (conftest seeds)
DOCS/                    spec, flows/tests, requirements flow, tech stack,
                         explainer, design.md, change log
data/                    gitignored — CSV + openeval2.sqlite3
```

---

## Tests

`python -m pytest tests -q` → 38 passed, ~1 s, offline. Mapping to the spec:

| Spec minimum | Test |
|---|---|
| Ingest count == cleaned count; empty negatives dropped | `test_ingest.py` |
| 50k sample deterministic (seed 42) | `test_ingest.py` |
| Short texts ⇒ needs_review with zero LLM spend | `test_api.py`, `test_rules.py` |
| Hotel themes, not clothing | `test_rules.py` |
| Disagreement / invalid label ⇒ needs_review (+error) | `test_api.py`, `test_rules.py` |
| Rating clash (≤4 + both Other + long) | `test_api.py`, `test_rules.py` |
| `/rows` limit/offset, no overlap | `test_api.py` |
| Filters (status, hotel, rating band) change results | `test_api.py` |
| 200 labeled rows have label_a + label_b | `test_label_sample.py` |
| Gold save: persists, does not overwrite A/B, 400 on invalid | `test_api.py` |
| Export opens in Excel (BOM CSV) + honors filters | `test_api.py` |
| Metrics: agree_with_gold null < 30 golds; A/B two runs | `test_api.py` |

---

## Privacy & licensing

- No employer data, no client data, no review text in git: `data/`, `*.csv`,
  SQLite files, `.env`, and caches are all ignored.
- Dataset license (CC0 for the hotel CSV): verify on the Kaggle page before
  redistribution; this repo ships no dataset contents.
- Fonts: the design system's proprietary face is not bundled; the dashboard
  substitutes Inter per `DOCS/design.md`. No Vodafone logo/photography/assets
  are used — only token metrics (colors, sizes, radii).

## Status semantics (what you should see)

- `ok` — sampled, both labels agree on a theme, text ≥ 4 words, no rating clash
- `needs_review` — short text, disagreement, missing/garbage/errored label,
  or the v2 rating clash
- `unlabeled` — never sampled (the bulk of the ~37k stored rows)

## Docs

`DOCS/OpenEval2-HOTEL-SPEC.md` (spec), `DOCS/OpenEval2-FLOWS-TESTS.md`
(flows + test scenarios), `DOCS/OpenEval2-REQUIREMENTS-FLOW.md` (requirement →
flow → test traceability), `DOCS/OpenEval2-TECH-STACK.md`, `DOCS/design.md`
(design tokens), `DOCS/OpenEval2-EXPLAINER.md` (plain language),
`DOCS/OpenEval2-CHANGES.md` (change & decision log).
