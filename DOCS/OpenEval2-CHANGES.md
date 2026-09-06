# OpenEval2 — Change & decision log

Every step of agent work in `Prjct2_V2` is recorded here: what changed, which files,
and why (decisions with evidence). Format: conventional-commit style per entry,
most recent last. Source docs (`OpenEval2-HOTEL-SPEC.md`, `OpenEval2-FLOWS-TESTS.md`,
`design.md`) are only edited when the user's direction changes their tech choices —
behavioral requirements stay authoritative in them.

---

## 2026-09-06 — Step 1 · Session start

**docs(requirements): create requirements-flow understanding doc**
- Created `DOCS/OpenEval2-REQUIREMENTS-FLOW.md`.
- Decision: distill the two source docs (HOTEL-SPEC + FLOWS-TESTS) into numbered
  requirements grouped by layer (D data · L labeling · S status · A API · U UI ·
  V v2 · P demo/legal), one ordered status decision tree, and a requirement → flow →
  test traceability matrix. No new requirements — reading aid only.

**docs(explainer): create plain-language explainer**
- Created `DOCS/OpenEval2-EXPLAINER.md`. Decision: non-technical register, "same loop
  as survey open-ends" framing, honest limits section, glossary.

## 2026-09-06 — Step 2 · Tech stack

**docs(tech-stack): create tech stack & libraries doc**
- Created `DOCS/OpenEval2-TECH-STACK.md`.
- Decision: each item marked Required (forced by docs/data) vs Choice (open, boring
  default). Evidence: v1 implementation exists in `../Prjct2` (fastapi/uvicorn/pandas/
  httpx/pytest, React 18 + TS + Vite + @tanstack/react-virtual) → used as the runtime
  floor reference (Python ≥ 3.11, Node ≥ 18). Repo had no code at that point.

## 2026-09-06 — Step 3 · design.md integration

**docs(requirements,tech-stack): adopt design.md as the UI design language**
- `design.md` dropped into DOCS; verified byte-identical (md5 `969190ea…`) across
  `Prjct1/DOCS`, `Prjct2/DOCS`, `Prjct2_V2/DOCS`. Prjct2's README confirms the v1
  dashboard was "styled from DOCS/design.md tokens".
- Decision: design.md is a shared brand-token reference (Vodafone analysis → tokens),
  NOT a per-project asset; it stays byte-identical and unedited.
- Added requirements U8–U17 (palette #e60000/#25282b/canvas…, Inter substitute type
  scale, pill CTAs, radii, no-shadows elevation, bands, breakpoints, status language)
  plus a design.md → surface map, and mirrored the token implementation into the tech
  stack frontend section.
- Decision: reuse token *metrics* only; ship no Vodafone brand assets (U17) — derived
  from design.md's font-substitute note + Prjct2 README privacy + demo hygiene (TS52).

## 2026-09-06 — Step 4 · UI decision: Streamlit, not React (user direction)

**docs(ui): switch presentation layer React → Streamlit**
- User direction: "I want streamlit to be used not react — update the docs folder files."
- Decision: replace the React/Vite/TypeScript UI with a **Streamlit** app; keep the
  FastAPI REST layer (SPEC §3/§6 mandates the endpoints and TS20–27 test them).
- Decision: Streamlit app talks to FastAPI with **server-side httpx** (runs in
  Streamlit's Python process) → browser never calls the API → no CORS config needed.
- Decision: `st.dataframe` provides the virtualization (TS30) — no separate
  virtualization library; `st.pagination` + `st.empty` slot for SPEC's limit/offset
  paging; 4× `st.metric(border=True)` stats band; sidebar filters; gold save via
  `st.form`/`@st.dialog` + POST; export via `st.download_button` over `/export.csv`
  bytes (utf-8-sig BOM preserved; download_button is forbidden inside forms);
  API-down → `st.error` (TS27).
- Evidence: no Streamlit installed on this machine (global + `../Prjct2/.venv`) →
  pulled `streamlit-1.63.0` wheel to `%TEMP%\streamlit_wheel` and read the
  version-matched reference docs bundled in the wheel
  (`streamlit/.agents/skills/developing-with-streamlit/references/`: theme, data-display,
  layouts, dashboards, performance). All widget claims are grounded in those 1.63 docs.
- Design mapping decision: design.md tokens apply via Streamlit theme
  `.streamlit/config.toml` (`primaryColor="#e60000"`, `textColor="#25282b"`,
  `backgroundColor="#ffffff"`, `secondaryBackgroundColor="#f2f2f2"`,
  `baseRadius="6px"`, `buttonRadius="full"`, Inter loaded via theme `font` URL) +
  small CSS injection; Streamlit is flat by default → U13 "no drop shadows" is free.
- Contrast correction: white on `#e60000` ≈ 4.8:1 → WCAG AA normal text / AAA display
  text. design.md's blanket AAA button claim must not be restated for small labels.
- Files changed so far in this step:
  - `DOCS/OpenEval2-HOTEL-SPEC.md` — architecture diagram box + §11 bullet → Streamlit.
  - `DOCS/OpenEval2-REQUIREMENTS-FLOW.md` — §1 model sentence, §2 mermaid node,
    U1 (st.dataframe), P3 (UI wording), U11 (theme pill + honest contrast).
- Files deliberately NOT changed: `design.md` (shared byte-identical token source),
  `OpenEval2-FLOWS-TESTS.md` + `OpenEval2-EXPLAINER.md` (no React-specific wording;
  "virtualized table" remains true of `st.dataframe`).

---

## 2026-09-06 — Step 5 · Change-log file + Streamlit conversion completed

**docs(changelog): create this file — `DOCS/OpenEval2-CHANGES.md`**
- User direction: maintain a file recording every step/change/decision, in
  conventional-commit style (example given was a git-commit agent). This file is that
  log; every future step is appended here.

**docs(requirements): finish Streamlit UI mapping in `OpenEval2-REQUIREMENTS-FLOW.md`**
- Replaced the design.md → component map with a **design.md → Streamlit widget map**:
  stats band = 4× `st.metric(border=True)` in `st.container(horizontal=True)`; pill CTAs =
  theme `primaryColor="#e60000"` + `buttonRadius="full"`; secondary = `st.button(type=…)`;
  badges = `st.column_config.MultiselectColumn` colored badges; table =
  `st.dataframe` + `st.pagination` into an `st.empty()` slot; export =
  `st.download_button` over /export.csv bytes (BOM kept, forbidden inside forms);
  API-down = `st.error`/`st.toast`; gold = `@st.dialog`/`st.form` + POST.
- U11 reworded: pill CTAs via theme keys; contrast honesty — white on `#e60000`
  ≈ 4.8:1 → WCAG AA normal text / AAA display text (design.md's blanket AAA claim
  must not be restated for small labels).
- Build-order step 3 and the §7 orientation bullet now name Streamlit/`.streamlit/config.toml`.

**docs(tech-stack): rewrite UI section in `OpenEval2-TECH-STACK.md` for Streamlit**
- §1 rows: "UI app = Streamlit (Python, ≥1.57) — not React"; runtime floors now
  Python ≥ 3.11 only (no Node/npm).
- §4 replaced: architecture (two Python processes; **server-side httpx → no CORS**;
  Streamlit-reading-SQLite-directly alternative rejected because the SPEC mandates the
  REST layer and TS20–27 exercise it), widget map, required components, theme
  `config.toml` (keys verified against Streamlit 1.63 `theme.md`), notes (elevation
  flat-by-default = U13 free; Styler coloring-only; radius keywords), reference-docs
  table for the build phase.
- §5/§6/§8: no `ui/dist`/build step; CI adds Streamlit AppTest smoke; deployment =
  uvicorn + `streamlit run` behind the host proxy; single `requirements.txt` with
  `streamlit>=1.57`; `package.json` block deleted.
- Decision: keep FastAPI REST layer as the data contract (Streamlit is its client).
- Decision: `OpenEval2-FLOWS-TESTS.md`, `OpenEval2-EXPLAINER.md`, and `design.md`
  unchanged — no tech-specific wording (virtualization claim holds for `st.dataframe`)
  and design.md stays the shared byte-identical token reference.
- Verified by grep: only intentional historical-context mentions of React/Node/Vite/
  remain (v1 provenance + "no Node/npm" statements).

---

## 2026-09-06 — Step 6 · New build folder + GitHub repo

**chore(repo): build in a new sibling folder `E:/Projects/ToluNaProjects/OpenEval2`**
- User direction (ask answered): "New sibling folder: ../OpenEval2". Decision: standalone
  project next to Prjct1/Prjct2; reads the 227 MB Kaggle CSV from `../Prjct2_V2/Dataset/`
  (no 227 MB copy); DOCS (7 files incl. this log, byte-identical) copied into the repo.
  Draft workspace `Prjct2_V2/DOCS` stays; this repo copy is canonical going forward.

**chore(repo): connect to github.com/pmkrafts/openeval2_V2**
- Ran the provided ritual in `../OpenEval2`: README stub `# openeval2_V2` (+ `.gitignore`
  adapted from v1), `git init -b main`, commit `8f61a0a` "first commit" (README + .gitignore),
  `branch -M main`, remote `origin https://github.com/pmkrafts/openeval2_V2.git`,
  `git push -u origin main` → succeeded, `main` tracks `origin/main`.
- Git identity: existing global `princem` / `47710070+pmkrafts@users.noreply.github.com`.

**build(plan): implement OpenEval2 end-to-end in the repo**
- Layout mirrors v1 (Prjct2): `config.py` (single rule source), `db.py`, `scripts/`
  (ingest, label_sample, run_ab), `api/app.py` (FastAPI), `app.py` (Streamlit), `.streamlit/`
  theme, `tests/` offline, `README.md`, `data/` gitignored.
- Contract kept from DOCS: hotel schema + 7 themes + drop-empty-negatives at ingest,
  rating ≤ 4 + both-Other + ≥4 words clash (v2), gold validation → 400, export BOM + exact
  header, `/hotels` top-50, ≤300 paid rows, mock default (CI key-free), design.md theme.

---

## 2026-09-06 — Step 7 · Build (implementation + verification)

**feat(backend): rules, schema, ingest, labeler, A/B, API**
- `config.py` — single source: 7 hotel themes, word-min 4, rating clash (≤4 + both Other),
  statuses; status always derived, never stored.
- `db.py` — `reviews` (hotel/nationality/rating REAL 1–10/text/text_pos/review_date/
  word_count), `labels` (label_a/b, agree, llm_error+error, gold_label),
  `ab_runs`+`ab_labels` for prompt A/B (v2).
- `scripts/ingest.py` — deterministic sample (`--sample 50000 --seed 42`), drops empty/
  "No Negative" rows, word_count at ingest.
- `scripts/label_sample.py` — mock (deterministic keyword classifier, offline default) +
  llm (OpenAI-compatible; 16 workers; sanitize "dirty!!!" → Other **and** flagged = TS13;
  failures recorded, run never dies). `scripts/run_ab.py` — prompt v1/v2 on same ids,
  records cost + p50 for /metrics.
- `api/app.py` — /health /stats /hotels (top-50) /rows (limit/offset + hotel/status/
  rating band) /export.csv (BOM, spec header) /metrics (gold null <30, A/B compare)
  POST /rows/{id}/gold (400 invalid / 404 missing; never overwrites A/B).
- Decision: gold-only labels rows do NOT count as "labeled" (status stays unlabeled).
- Decision: rating stored REAL (Booking scores are floats like 9.6); `rating` param +
  additive `rating_min/rating_max` band filters; UI sends no bounds at full range so
  NULL ratings stay visible.

**feat(ui): Streamlit dashboard + design.md theme**
- `app.py` — server-side httpx client (no CORS); stats metric band; sidebar filters
  (hotel/status/rating); `st.dataframe` virtualized grid + `st.pagination` (key includes
  filter signature → resets to page 1 on filter change); needs_review red row tint +
  badge colors; full-complaint expander; gold form → POST + toast + cache clear; export
  via `st.download_button` over /export.csv bytes; `st.error` + retry on API-down
  (TS27); Metrics view (gold, A/B runs).
- `.streamlit/config.toml` — design.md tokens: primary `#e60000`, canvas `#ffffff`,
  canvas-soft `#f2f2f2`, ink text `#25282b`, `baseRadius="6px"`, `buttonRadius="full"`,
  Inter via theme font URL, flat (no shadows — Streamlit default).

**test(backend): 38 offline tests pass (~1 s, no key, synthetic CSV)**
- ingest (drop/count/word_count/No-Positive/sample determinism/missing columns),
  rules (agree, short-wins, invalid, llm-error, clash, sanitize), label_sample (200×2,
  determinism, short stays needs_review), API (TS20–27 + gold + metrics + A/B).
- Found & fixed: sorting `sqlite3.Row` needs tuples; metrics test needed 30 distinct rows.

**run(real data): H1–H3 proven**
- Real Kaggle CSV: read 515,738 → sampled 50,000 (seed 42) → **37,496 complaints**
  ingested (empty negatives dropped). Labeled 200 (mock, 0 errors) + A/B 2 runs.
- API verified live: /health /stats {37496, ok 167, needs_review 5948, unlabeled 31381},
  /hotels 50 (top: Britannia International Hotel Canary Wharf 382), status filter,
  gold POST 200/400, export.csv BOM + exact header + 5,948 filtered rows, /metrics
  with A/B comparison n=200 agree 1.0 (mock).
- UI verified in headless Chromium: theme applied (primary button bg `rgb(230,0,0)`,
  pill radius, uppercase 800 headline), stats bar, grid, pagination (375 pages),
  status filter → 60 pages + "Status: needs_review" meta, gold save persisted
  ("Gold: Location"), Metrics view (gold count, agree null until 30, v1/v2 runs).
- Decision: mock A/B agreement is 1.0 by design (same deterministic labeler) — the CI
  signal is "two run records + well-defined agreement", real variation comes from llm.

**docs(project): README + .env.example + changelog**
- Full README (dataset/caps/10-pt note/"not employer data" per P2/TS50–51), .env.example
  committed (`.env.*` ignored but `!.env.example` re-included).

---


## 2026-09-06 — Step 8 · Relocation into the workspace root

**chore(repo): move the project from `../OpenEval2` into `Prjct2_V2`**
- User direction: the project belongs in `E:/Projects/ToluNaProjects/Prjct2_V2`
  (this workspace), not the sibling folder created in Step 6.
- Decision: relocate the entire repo (`.git`, code, DOCS, data/) to the `Prjct2_V2`
  root; `Dataset/Hotel_Reviews.csv` already lives there and stays gitignored.
- Removed the path-bound `.venv` + caches before the move; recreated
  `.venv` in the new root and reinstalled requirements (streamlit 1.63.0).
- Services stopped, restarted from the new path (api :8000, ui :8501).
- Doc/decision log is now single-copy at `Prjct2_V2/DOCS/OpenEval2-CHANGES.md`.


## 2026-09-06 — Step 9 · Runbook

**docs(run): add DOCS/OpenEval2-RUN.md**
- Step-by-step runbook grounded in the verified setup: venv + install, real CSV
  ingest (Dataset/Hotel_Reviews.csv, expected output 37,496 complaints) or the
  synthetic 216-row path, mock labeling + A/B, API (:8000/docs) and dashboard
  (:8501) in two terminals, expected stats after a real run, optional real-LLM
  via .env, offline tests (38 passed), troubleshooting table (ports, .venv after
  moves, missing columns, LLM 401/404, 37,496-not-50,000 explanation, gold 400,
  config.toml restart), and the 10-minute demo script.


## 2026-09-06 — Step 10 · API-key hygiene

**security(chore): real OpenAI key was pasted into `.env.example` (git-tracked)**
- Detected when verifying where the key is consumed. Moved the real values into
  `.env` (gitignored — `git check-ignore` confirmed) and restored `.env.example`
  to the placeholder template.
- Verified: zero `sk-proj` occurrences in committed history (`git log -p --all`),
  working tree clean — the secret was never pushed.
- Action required from user: **rotate the key** anyway (it appeared in this
  session's tool output); new key goes into `.env` only.
- Usage answer recorded: the key is consumed only by `scripts/label_sample.py`
  (`LLMLabeler`, Authorization: Bearer) and `scripts/run_ab.py` (same class), both
  loaded from `.env` via `load_dotenv()`. Ingest/API/dashboard/tests/mock never use it.


## 2026-09-06 — Step 11 · Runbook highlights

**docs(run): color-highlight decision points in OpenEval2-RUN.md**
- User: the LLM/mock-cost part of the runbook wasn't clearly flagged.
- Added GitHub-flavored alert callouts (colored panels on github.com + VS Code):
  - `[!TIP]` §4 — mock = no AI, no cost ($0.0 is correct); §6 — cost guards.
  - `[!NOTE]` §4 — re-run labels nothing without --force; §6 — where the key is used.
  - `[!IMPORTANT]` §6 — --force required/overwrites mock labels.
  - `[!WARNING]` §6 — secrets only in .env; .env.example is tracked/public.
  - `[!CAUTION]` §6 — placeholder aborts; 401s flag rows needs_review (Flow 6).
- Extended port troubleshooting row with WinError 10013 + netstat / excluded-range checks.


## 2026-09-06 — Step 12 · Fix: LLM prompt template KeyError

**fix(labeling): every real-LLM call failed with KeyError: '"label"'**
- Symptom (user run): `label_sample --provider llm` -> errors=200, first error
  `'"label"'`; `run_ab --provider llm` crashed at `PROMPTS[prompt_version].format(...)`.
- Root cause: the templates' JSON example braces live in f-string pieces, so
  `{{` collapsed to `{` at definition time; `str.format()` then parsed the
  remaining single braces as fields and looked up a key literally named
  `"label"` (with quotes) -> uniform KeyError, one per call.
- Fix: new `build_prompt(prompt_version, text)` uses `.replace("{text}", text)`
  (no format parsing); used by both `LLMLabeler.label` and `run_ab`.
- Regression test added (`test_prompt_templates_interpolate_without_format_crash`),
  suite 39 passed.
- Verified end-to-end with a local OpenAI-shaped stub server (zero cost):
  prompt payload contains the JSON instruction, `label_sample` stored
  ('Room','Room', agree=1, errors=0), `run_ab` recorded real cost ($1.1e-05)
  and p50 ms for both prompt versions.
- Note: the earlier broken run left 200 rows flagged (labels null, llm_error=1);
  re-running `label_sample --provider llm --force` overwrites them with real
  labels, or `--provider mock --force` restores the free demo state.


## 2026-09-06 — Step 13 · Remove employer name

**chore(privacy): delete the word "Toluna" from all files**
- User direction: the word must not appear anywhere (public-repo hygiene).
- Scrubbed the real occurrences (folder name `ToluNaProjects` kept — it is a
  path, not the word):
  - this repo README.md ("no Toluna/survey data" -> "no survey data")
  - ../Prjct2/README.md and ../Prjct2/UNDERSTANDING.md (same wording)
  - ../Prjct1/DOCS/01-understanding.md ("Toluna data" -> "Survey-company data")
  - ../Prjct2/DOCS/openend-eval-KAGGLE-SPEC.docx (binary zip XML rewrite,
    "Toluna" -> "survey")
- Verified: word-boundary grep across all md/py/txt/toml/.env + docx -> 0 hits.


## 2026-09-06 — Step 14 · Plain-language explanation at the top of entry files

**docs(readme/run): simple-language project explanation at the very start**
- User direction: explain the project in simple language and write it at the top
  of the README (and anywhere else a reader lands).
- README.md now opens with "What is this? (plain language)": complaints →
  two AI taggers → human checks disagreements → gold + prompt A/B; the
  515k → 50k → 200 → human-review numbers; pointers to EXPLAINER/RUN. The
  existing technical summary moved under "What it is built from (technical)".
- DOCS/OpenEval2-RUN.md opens with a short plain-language blurb before the steps.
- Full walkthrough stays in DOCS/OpenEval2-EXPLAINER.md.


## 2026-09-06 — Step 15 · README: human+AI flow and the two "twos"

**docs(readme): explain 2 AI calls vs 2 prompt versions + human flow**
- User asked why two AI prompt versions and how the human/AI flow works.
- README gained "How the flow works (AI + human)": mermaid pipeline
  (AI reads twice -> rules -> ok / needs_review / unlabeled -> human review +
  gold -> metrics -> pick better prompt) plus a table separating:
  * 2 AI calls per row (label_a/b, same prompt) = reliability signal; disagreement
    queues the row for a human;
  * 2 prompt versions (v1 vs v2 = prompt A/B) = an experiment about prompt
    quality; /metrics compares cost/p50/agreement and (>=30 golds) agreement
    with the human.
- Explains why the human's job stays tiny and why two calls beat one.
