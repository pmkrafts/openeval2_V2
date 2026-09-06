# OpenEval2 — How to run (runbook)

Everything needed to go from a clean machine to the live dashboard, plus what
"working" looks like at each step. Windows commands (this machine is Windows 11,
Python 3.13); POSIX = swap `python`/`.venv\Scripts\` for `python3`/`.venv/bin/`.

Repo: github.com/pmkrafts/openeval2_V2 — Docs: see `OpenEval2-HOTEL-SPEC.md`
(what it is), `OpenEval2-REQUIREMENTS-FLOW.md` (rules), `README.md` (overview).

---

## 1. Prerequisites

| What | Version | Check with |
|---|---|---|
| Python | ≥ 3.11 | `python --version` |
| No Node/npm needed | — | the whole stack (API + UI) is Python |

One-time network: `pip install` (below) and — at dashboard runtime only — the
Inter font fetch from Google Fonts (falls back to sans-serif offline).

## 2. One-time setup

```powershell
cd E:\Projects\ToluNaProjects\Prjct2_V2

python -m venv .venv
.venv\Scripts\activate        # POSIX: source .venv/bin/activate
pip install -r requirements.txt
```

Expected: installs pandas, fastapi, uvicorn, httpx, streamlit (≥1.57), pytest.

> A `.venv` already exists in this workspace (streamlit 1.63.0). If Python was
> upgraded or the folder was moved, delete `.venv` and re-run the two lines above.

## 3. Data

### Option A — the real Kaggle file (this workspace has it)

The 227 MB `Dataset/Hotel_Reviews.csv` (515,738 rows) is already here:

```powershell
python scripts\ingest.py Dataset\Hotel_Reviews.csv --sample 50000 --seed 42
```

Expected (takes a few seconds):
`read 515738 rows; ingested 37496 complaints -> data\openeval2.sqlite3`

- 50,000 sampled deterministically (seed 42), then empty/"No Negative" rows are
  dropped → 37,496 complaints stored. The CSV and DB are gitignored.
- Re-run with the same seed ⇒ identical ids. To rebuild from scratch add
  `--replace` (wipes labels/A-B tables too).

### Option B — synthetic CSV (no download, tiny)

```powershell
python -c "import sys; sys.path.insert(0,'tests'); from conftest import write_review_csv; write_review_csv('data/synthetic.csv')"
python scripts\ingest.py data\synthetic.csv
```

Expected: 216 complaints, ids 1–216 (6 short texts + 210 long ones). Everything
downstream behaves identically — use this for a quick demo or CI-style checks.

## 4. Label the sample (mock is the default — no key, no cost)

```powershell
python scripts\label_sample.py --count 200 --seed 42 --provider mock
python scripts\run_ab.py --count 200 --seed 7 --provider mock   # v2 prompt A/B
```

Expected (mock):
`sample=200 labeled=200 provider=mock errors=0`
then two A/B run records with `cost=$0.0`.

Deterministic: same seed ⇒ identical label pairs. Sampling only touches rows
that are not labeled yet — re-running after a full 200 adds nothing.

## 5. Start the API and the dashboard (two terminals)

Terminal 1 — API:

```powershell
cd E:\Projects\ToluNaProjects\Prjct2_V2
.venv\Scripts\activate
python -m uvicorn api.app:app --reload
```

- Interactive docs: http://127.0.0.1:8000/docs
- Check: http://127.0.0.1:8000/health → `{"status": "ok", "reviews": 37496, ...}`

Terminal 2 — dashboard:

```powershell
cd E:\Projects\ToluNaProjects\Prjct2_V2
.venv\Scripts\activate
streamlit run app.py
```

Open http://127.0.0.1:8501. The dashboard calls the API **server-side** (httpx),
so no CORS setup is needed. If the API is not on `:8000`, set
`OPENEND_API_URL` before starting, e.g.
`$env:OPENEND_API_URL="http://127.0.0.1:9000"`.

### What "working" looks like (with the real dataset)

- Stats row: **Total 37,496 · OK 167 · Needs review 5,948 · Unlabeled 31,381**
- Grid: 375 pages × 100 rows; `needs_review` rows tinted red with red badges.
- Sidebar filters: Hotel (top 50), Status, Rating (1–10 band). Status =
  `needs_review` → page count drops to 60 and every visible row shows
  `Status: needs_review`.
- Row detail & gold: pick a review id, read the full complaint, save a gold
  theme (dropdown). Refresh shows `Gold: <theme>`; A/B labels are untouched.
- Export: "Download export.csv" downloads **only the filtered rows**, BOM
  included — double-click opens in Excel with headers
  `id,hotel,rating,text,label_a,label_b,agree,status,gold_label`.
- Metrics view (radio at top): gold count and `Agree with gold` (shows "—" until
  30 golds are saved), then the prompt A/B runs with their agreement.

## 6. Real-LLM labeling (optional, costs ~$0.01 per 200-row sample)

Create `.env` in the repo root (gitignored):

```
OPENEND_LLM_KEY=PASTE_YOUR_KEY_HERE
# OPENEND_LLM_BASE_URL=https://api.openai.com/v1   # any OpenAI-compatible endpoint
# OPENEND_LLM_MODEL=gpt-4o-mini
```

Then, from a shell with that env (or after editing `.env`):

```powershell
python scripts\label_sample.py --seed 42 --provider llm --force
python scripts\run_ab.py --count 200 --seed 7 --provider llm
```

- Missing key or the literal `PASTE_YOUR_KEY_HERE` aborts before any HTTP call.
- 200 reviews × 2 calls = 400 calls; the run never dies mid-sample — failures
  are recorded and those rows surface as `needs_review` (that is the designed
  behavior, not a bug).
- A/B with `llm` records real per-run cost + p50 latency in `/metrics`.

## 7. Tests (offline, no dataset, no key)

```powershell
python -m pytest tests -q
```

Expected: `38 passed in ~1 s`. The suite builds its own synthetic CSV and uses
the mock labeler; API endpoints are exercised through FastAPI's TestClient.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `'python' is not recognized` | Python not on PATH — use the full path to `python.exe` or reinstall with "Add to PATH". |
| `.venv\Scripts\activate` errors / `ModuleNotFoundError` after moving the folder | Venvs are path-bound — delete `.venv`, re-create, `pip install -r requirements.txt`. |
| Port already in use: `[Errno 10048]` / `Address already in use` on 8000 or 8501 | Something else owns the port. Run with a different port (`--port 9000`, `streamlit run app.py --server.port 8600`) or stop the other process. |
| Dashboard shows "API unreachable: cannot reach API at http://127.0.0.1:8000" | The API process is not running or is on another port — start it (Step 5) or set `OPENEND_API_URL`. Hit **Retry**. The dashboard never shows a blank crash. |
| `Error: CSV missing required columns: [...]` | Wrong CSV. Hotel dataset needs `Hotel_Name, Reviewer_Nationality, Reviewer_Score, Positive_Review, Negative_Review, Review_Date`. |
| `OPENEND_LLM_KEY missing or still the placeholder` | Copy `.env.example` → `.env` and put a real key in before `--provider llm`. |
| 401 / 404 from the LLM endpoint | Wrong `OPENEND_LLM_BASE_URL` (must end in `/v1` and serve `/chat/completions`) or wrong key/model. |
| You expect ~50,000 rows but the DB has 37,496 | Correct: empty/"No Negative" rows are dropped at ingest by design (H1 allows "or less"). |
| `needs_review` rows with `Labeler note:` | A label call failed or returned garbage (TS13) — the row was stored as `Other` and flagged. This is the designed review queue, not an error. |
| Gold save returns 400 | The theme must be one of `Location, Staff, Room, Cleanliness, Food, Price, Other`. |
| Theme/font changes don't apply | `.streamlit/config.toml` font changes need a **full restart** of `streamlit run` (Ctrl-C, restart). |
| Excel shows garbled text / no columns | Open via the download button (BOM is written); if re-encoding, save as UTF-8 with BOM. |
| Numbers look odd (8.8/10) | Booking scores are 1–10, not 1–5 — ratings are stored as decimals on purpose. |

## 8. 10-minute demo script

1. Stats row: 37,496 stored / 200 LLM-labeled / 5,948 in the review queue.
2. Sidebar → Status = `needs_review` (60 pages).
3. Open one row, read the complaint aloud, point at `Label A ≠ Label B` (or the
   red `Labeler note` for a sanitized label).
4. Save gold = the correct theme.
5. Download export.csv, open in Excel.
6. "Same loop as survey open-ends at work — this text is public hotel data."
