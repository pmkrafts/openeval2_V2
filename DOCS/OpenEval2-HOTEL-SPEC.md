# OpenEval2 — Hotel reviews dataset spec

Repo stays: https://github.com/pmkrafts/openeval2  
This file replaces the clothing-reviews *dataset* only. v1 + v2 product behavior stays.

Owner: Prince Maurya

---

## 1. Project understanding (simple)

People write hotel comments on Booking.com (public Kaggle dump).  
Each row has a **good** comment and a **bad** comment plus a score.  
We store a **50,000 row sample** in SQLite.  
A website shows the comments in a table.  
Two AI taggers read the **negative** comment and pick a theme  
(Location, Staff, Room, Cleanliness, Food, Price, Other).  
If they disagree, or the text is tiny, or a 1–2 star review looks “fine,” the row goes to **needs_review**.  
A human can save a **gold** theme (v2).  
Two prompts can be compared on 200 rows (v2).

This is the same loop as survey open-ends at work. Hotel text is public. Employer data is not used.

---

## 2. Dataset

**Name:** 515K Hotel Reviews Data in Europe  
**URL:** https://www.kaggle.com/datasets/jiashenliu/515k-hotel-reviews-data-in-europe  
**Author:** Jiashen Liu  
**Size:** ~515,738 rows, CSV zip ~45–50 MB  
**License:** CC0 — still do not commit the CSV to git  

### Columns we use

| Kaggle column | We store as | Notes |
|---|---|---|
| (generated) | id | Integer after sample |
| Hotel_Name | hotel | Segment filter |
| Reviewer_Nationality | nationality | Optional filter |
| Reviewer_Score | rating | 1–10 on Booking; treat as score |
| Positive_Review | text_pos | Empty if "No Positive" |
| Negative_Review | text | **Primary text for labeling** |
| Review_Date | review_date | Optional |

`"No Negative"` and `"No Positive"` → empty string.

### Hard caps

| Step | Rows |
|---|---|
| Download | full file |
| Ingest | **50,000** random sample, seed 42 |
| Dual-LLM / A/B | **200** (v1) or **100–200 per prompt** (v2) |
| Browser | only the current page (limit/offset) |

Do not ingest 515k. Do not label 515k.

---

## 3. Architecture

```
HotelReviews.csv  (full, gitignored)
        |
        v
scripts/ingest.py   --sample 50000 --seed 42
        |
        v
SQLite reviews
  id, hotel, nationality, rating, text, text_pos, word_count, review_date
        |
        +--> scripts/label_sample.py   200 rows, two labelers on `text`
        +--> scripts/run_ab.py         v2 prompts
        |
        v
FastAPI  /health /stats /rows /export.csv /metrics  POST /rows/{id}/gold
        |
        v
Streamlit dashboard (st.dataframe virtualized table) + filters (hotel or rating + status)
```

SQLite is the warehouse stand-in. No Snowflake required.

---

## 4. Themes (hotel, not clothing)

`Location` | `Staff` | `Room` | `Cleanliness` | `Food` | `Price` | `Other`

Label **Negative_Review** (`text`) only in this version.

---

## 5. Rules

1. word_count = words in `text` (negative).  
2. Empty negative (`No Negative`) → word_count 0 → **needs_review** (nothing to code) OR skip ingest of those rows. **Pick one:** drop rows with empty negative at ingest so the table is complaints-only. Recommended: **drop empty negatives at ingest**.  
3. agree = label_a == label_b and both in theme list.  
4. needs_review if word_count < 4 OR agree = no OR missing label OR LLM error.  
5. Rating clash (v2): rating <= 4 on a 10-point scale AND both labels Other AND word_count >= 4 → needs_review.  
   (Booking scores are ~1–10, not 1–5. Document this in README.)  
6. Gold label optional; does not overwrite A/B.  
7. Public host uses **synthetic hotel-shaped CSV**, not the Kaggle file.

---

## 6. API (same as now + hotel field)

GET `/rows?limit=&offset=&rating=&status=&hotel=`  
Each row JSON: id, text, text_pos, rating, hotel, nationality, label_a, label_b, agree, status, gold_label  

GET `/hotels` — distinct hotel names for the filter (cap list at 50 most frequent in the sample).

---

## 7. User scenarios

S1 Recruiter: “bigger data than clothing.” You say 515k source, 50k store, 200 labeled.  
S2 Screen-share: filter needs_review, show two tags on a dirty-room complaint.  
S3 Empty “No Negative” rows never hit the LLM.  
S4 v2: save gold=Staff on a disagreement.  
S5 Public URL has fake hotels only.

---

## 8. Test cases

| ID | Case | Expected |
|---|---|---|
| H1 | ingest with --sample 50000 | reviews count = 50000 (or less if empties dropped) |
| H2 | source file has 515k; DB does not | pass |
| H3 | "No Negative" dropped or flagged | no LLM call on empty text |
| H4 | theme list is hotel themes | clothing themes gone |
| H5 | label_sample 200 | 200 rows have label_a and label_b |
| H6 | disagreement | needs_review |
| H7 | short text | needs_review |
| H8 | /rows?hotel= | filter works |
| H9 | export includes hotel, text, labels | Excel opens |
| H10 | git status | no CSV, no sqlite |

---

## 9. Build order

1. Download Kaggle zip → `data/` (gitignored).  
2. Change ingest: read hotel columns, sample 50k, drop empty negatives, map themes in config.py.  
3. Update UI columns: hotel, rating, negative text.  
4. Re-run label_sample mock, then optional LLM on 200.  
5. Keep v2 gold + A/B on this schema.  
6. README: dataset URL, sample cap, 10-point scores.  
7. Stop.

---

## 10. Resume line

OpenEval2 — 515k hotel-review source, 50k warehouse-shaped sample, dual-LLM coding of complaint open-ends, review queue, optional gold + prompt A/B. github.com/pmkrafts/openeval2

---

## 11. Do not do

- Load 515k into the browser UI  
- Label more than 300 rows with a paid model  
- Add maps / lat-long viz  
- New repo  
- Spark
