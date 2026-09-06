# OpenEval2 — user flows and test scenarios

Dataset: 515K Hotel Reviews (Kaggle) → 50k sample in SQLite → label 200 negatives.  
Repo: github.com/pmkrafts/openeval2

---

## A. Who uses it

| Actor | Goal |
|---|---|
| You (builder) | Ingest sample, label, run API + UI |
| Analyst (you on a call) | Find bad tags, save gold, export |
| Hiring manager | Open URL or watch you click for 10 minutes |
| CI / pytest | Prove rules without Kaggle or API key |

---

## B. User flows

### Flow 1 — First run (builder)

1. Download hotel CSV from Kaggle into `data/` (not git).  
2. Run ingest with `--sample 50000 --seed 42`. Drop rows where Negative_Review is empty / "No Negative".  
3. Confirm DB count ≈ sample after drops.  
4. Run `label_sample.py` (mock first).  
5. Start API. Open `/health` and `/stats`.  
6. Start UI. Table loads with hotel, rating, negative text, two labels, status.  
7. Stop.

**Done when:** stats.total > 0 and table shows both `ok` and `needs_review`.

---

### Flow 2 — Hiring manager (read-only)

1. Opens hosted URL **or** watches localhost.  
2. Sees counts: Total / OK / Needs review / Unlabeled.  
3. Scrolls virtualized table (does not freeze).  
4. Filters status = needs_review.  
5. Reads one complaint + two different tags.  
6. Clicks Export CSV. File opens in Excel.  
7. Leaves.

**Success:** they understand “model can be wrong; those rows are queued.”  
**Fail:** they think it is a hotel booking site.

---

### Flow 3 — Screen-share story (you)

1. Show README: 515k source → 50k store → 200 LLM.  
2. Filter a dirty-room / rude-staff row.  
3. Point at label_a ≠ label_b → needs_review.  
4. Say: same loop as survey open-ends; this text is public.  
5. (v2) Save gold = Staff or Cleanliness. Row keeps A/B, gold appears.  
6. (v2) Open metrics: prompt v1 vs v2.  
7. Stop at 10 minutes. No client names.

---

### Flow 4 — Quality / short text

1. A negative review is "ok" or "bad" (< 4 words).  
2. Status is needs_review even if both labels match.  
3. No extra LLM retry.

---

### Flow 5 — Empty negative

1. Raw CSV has "No Negative".  
2. Ingest drops the row (chosen rule).  
3. That text never appears and is never sent to a model.

---

### Flow 6 — Model failure

1. One LLM call errors on id=17.  
2. Row still in table.  
3. status = needs_review, error field set.  
4. API and UI do not crash.

---

### Flow 7 — Filters and export

1. Filter rating band or hotel (top hotels list).  
2. Counts change.  
3. Export downloads **only filtered** rows.  
4. CSV has header: id, hotel, rating, text, label_a, label_b, agree, status, gold_label.

---

### Flow 8 — v2 gold

1. Open a needs_review row.  
2. Set gold_label = Room. Save.  
3. Refresh: gold = Room; A/B unchanged.  
4. Invalid gold "cheap!!!" → API 400.  
5. After 30 golds, metrics may show agree_with_gold; before that it is null.

---

### Flow 9 — v2 prompt A/B

1. Run prompt v1 and v2 on the same 100 ids (mock or LLM).  
2. Metrics show n, cost, p50_ms, agree v1↔v2.  
3. Default path is mock so CI needs no key.

---

### Flow 10 — Public demo

1. Deploy with synthetic hotel-shaped CSV.  
2. No Kaggle file on the server.  
3. No real API key required to view.  
4. Recruiter URL works when you are offline.

---

## C. Test scenarios (tick these)

### Ingest / data

| ID | Scenario | Expected |
|---|---|---|
| TS01 | Full Kaggle file present locally | git does not contain it |
| TS02 | ingest --sample 50000 --seed 42 twice | same ids both times |
| TS03 | "No Negative" / blank negative | dropped (or flagged; pick drop) |
| TS04 | "No Positive" | text_pos empty; row can stay if negative exists |
| TS05 | word_count on negative text | integer, 0 if empty |

### Rules

| ID | Scenario | Expected |
|---|---|---|
| TS10 | label_a = label_b = Staff, words >= 4 | agree=yes, status=ok |
| TS11 | label_a = Staff, label_b = Room | agree=no, needs_review |
| TS12 | text = "bad bed" (2 words) | needs_review even if labels match |
| TS13 | model returns "dirty!!!" | stored as Other, needs_review |
| TS14 | rating <= 4 (10-pt) and both Other, long text | needs_review (clash) |
| TS15 | unlabeled (not in 200 sample), long text | status=unlabeled |

### API

| ID | Scenario | Expected |
|---|---|---|
| TS20 | GET /health | 200 |
| TS21 | GET /stats | total, ok, needs_review, unlabeled |
| TS22 | GET /rows?limit=20&offset=0 | 20 rows |
| TS23 | GET /rows?offset=20&limit=20 | next page, no overlap with TS22 |
| TS24 | GET /rows?status=needs_review | only that status |
| TS25 | GET /rows?hotel=... | only that hotel |
| TS26 | GET /export.csv with same filters | Excel + BOM + header |
| TS27 | API down | UI error state, not blank crash |

### UI

| ID | Scenario | Expected |
|---|---|---|
| TS30 | 50k in DB | page stays smooth (virtualized) |
| TS31 | needs_review rows visible | color or badge |
| TS32 | counts match /stats | pass |
| TS33 | long review text | wrap, layout holds |
| TS34 | zero rows after filter | empty message |

### v2

| ID | Scenario | Expected |
|---|---|---|
| TS40 | POST gold=Cleanliness | 200, persisted |
| TS41 | POST gold=hello | 400 |
| TS42 | gold_count < 30 | agree_with_gold is null |
| TS43 | two prompt runs | two run records |
| TS44 | pytest with no key | all green |

### Legal / story

| ID | Scenario | Expected |
|---|---|---|
| TS50 | README names Kaggle dataset + sample cap | yes |
| TS51 | README says not employer data | yes |
| TS52 | public host has no hotel CSV from Kaggle | yes |

---

## D. Demo script (10 minutes)

1. Stats bar (50k / 200 labeled).  
2. Filter needs_review.  
3. One disagreement row — read the negative sentence aloud.  
4. Gold save (if v2 live).  
5. Export.  
6. “At work this is survey open-ends behind private APIs. This file is public hotel text.”

If any step needs a client name, skip that step.
