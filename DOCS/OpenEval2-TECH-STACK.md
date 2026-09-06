# OpenEval2 — Tech stack & used libraries

What the system actually runs on. **Everything below is implemented and verified
in this repo** (working tree at `Prjct2_V2`, github.com/pmkrafts/openeval2_V2) as
of 2026-09-06 — not a shopping list.

## 0. Implementation status (verified 2026-09-06)

| Component | Used version | State |
|---|---|---|
| Python | 3.13.13 (venv `.venv`) | running; floor stays ≥ 3.11 |
| fastapi + uvicorn | 0.141.1 · 0.52.4 | API on :8000 — all endpoints live |
| pandas | 3.0.5 | ingest 50k sample (seed 42) → 37,496 complaints |
| httpx | 0.28.1 | LLM calls + Streamlit's server-side API client |
| streamlit | 1.63.0 | dashboard on :8501 — theme per design.md |
| pytest | 9.1.1 | **39 tests pass**, offline, ~1 s, no key |
| sqlite3 (stdlib) | — | `data/openeval2.sqlite3` — reviews/labels/ab_runs/ab_labels |
| Node / npm | none | confirmed unnecessary — whole stack is Python |

Deliberate deviations from the original plan, all logged in
`OpenEval2-CHANGES.md`:
- rating stored **REAL** (Booking scores are decimals like 9.6); `/rows` gained
  additive `rating_min` / `rating_max` band params (UI uses them);
- gold-only labels rows never count as "labeled" (status stays `unlabeled`);
- prompt templates interpolate via `build_prompt()` (`.replace`) — the
  `str.format` variant raised `KeyError: '"label"'` on every LLM call (Step 12);
- mock A/B agreement is 1.0 by design; real variation comes from `--provider llm`.

Provenance: `DOCS/design.md` is byte-identical to the design doc the v1 app
(Prjct1/Prjct2) styled its dashboard from. The backend inherits the working v1
stack; the UI is a deliberate new choice — **Streamlit (≥1.57) instead of v1's
React** (user direction, 2026-09-06). Widget/theme claims were checked against
Streamlit 1.63's bundled reference docs (theme, data-display, layouts,
dashboards, performance).

---

## 1. Stack at a glance

| Layer | Tech (required) | Notes |
|---|---|---|
| UI design source | `DOCS/design.md` (brand token system) | byte-identical to v1's doc (Prjct1/Prjct2); tokens only — no Vodafone assets |
| Data source | Kaggle "515K Hotel Reviews" CSV (~45–50 MB zip, 227 MB unpacked) | CC0; never committed to git |
| Warehouse stand-in | **SQLite** | SPEC §3: "SQLite is the warehouse stand-in. No Snowflake required." |
| Ingest + labeling scripts | Python | `scripts/ingest.py`, `scripts/label_sample.py`, `scripts/run_ab.py` |
| Backend API | **FastAPI** | `/health /stats /rows /export.csv /metrics /hotels`, `POST /rows/{id}/gold` |
| UI app | **Streamlit (Python, ≥1.57)** — not React | replaces the v1 React dashboard (user decision); `st.dataframe` virtualized grid + sidebar filters; design.md tokens via `.streamlit/config.toml` theme; smooth on 50k rows |
| LLM labelers | Two independent model calls per row | Mock labeler is the default path (CI needs no key) |
| Tests | pytest | **39 passed**, offline, no key (2026-09-06) |
| Runtime floors | Python ≥ 3.11 only — API and Streamlit UI are both Python; **no Node/npm** | verified on Python 3.13.13; v1-proven backend + new Streamlit choice |
| Public demo | Hosted URL, synthetic hotel-shaped CSV | No Kaggle file, no key required to view |

---

## 2. Backend — Python

### Required by the docs
| Component | Why |
|---|---|
| Python 3 (any recent 3.x) | Scripts + FastAPI host |
| FastAPI | API surface in SPEC §6 / §3 |
| SQLite (Python `sqlite3` stdlib is enough) | 50k-row store, one file, zero ops |
| pandas | 50k deterministic sampling (`--sample 50000 --seed 42`), CSV column mapping, empty-negative drop |
| An ASGI server | uvicorn is the standard choice |
| pytest | Test scenarios TS20–TS44 "all green with no key" |
| Pydantic (ships with FastAPI) | Request/response models; gold-value validation → 400 on `"cheap!!!"` (TS41) |

### Recommended libraries (choices, not forced)
| Library | Job |
|---|---|
| `httpx` | Async LLM client if labeling in parallel (2 labelers × 200 rows) |
| `python-multipart`/none | Not needed — no file uploads in the API |

### Library choices that are forced by test expectations
| Detail | Implementation note |
|---|---|
| Export CSV with BOM, opens in Excel | Write with `utf-8-sig` encoding (TS26, H9: "Excel + BOM + header") |
| Exact CSV header | `id,hotel,rating,text,label_a,label_b,agree,status,gold_label` (Flow 7) |
| Deterministic re-runs | `random.Random(42)` / `pandas.sample(random_state=42)` → same ids twice (TS02) |
| Theme list in one place | `config.py` holds the 7 themes (SPEC §9: "map themes in config.py") |

### The scripts (SPEC §3)
| File | Responsibility | Flags/notes |
|---|---|---|
| `scripts/ingest.py` | CSV → SQLite sample | `--sample 50000 --seed 42`; drop rows with empty/"No Negative" negative |
| `scripts/label_sample.py` | 200 rows, two labelers on `text` | mock first, LLM optional |
| `scripts/run_ab.py` | v2 prompt A/B on same ids | same ids for both prompt runs |

---

## 3. LLM layer

| Requirement (from docs) | Consequence |
|---|---|
| Two labelers per row, both read the **negative** text only | Two independent model calls per labeled row (or one call per model) |
| Mock is default; LLM optional; CI has no key (TS44, L6) | Labeler behind an interface with `mock` and `llm` implementations |
| Paid-model budget: never label >300 rows (SPEC §11) | Keep 200-row cap in config; no background re-labeling |
| LLM failure on one row must not crash API/UI (Flow 6) | Per-row try/except → `needs_review` + `error` field |
| Invalid label out of the theme list (e.g. `"dirty!!!"`) → stored `Other`, `needs_review` (TS13) | Sanitize step after model output |
| A/B compares cost, p50 latency, agreement (Flow 9, V3) | Run must record per-call cost + duration |
| LLM provider / model | **Choice** — docs never name one. Pick one provider, keep it behind the labeler interface. v1 + v2 "product behavior stays" implies any provider switch is confined to that interface. |

No API key is required to run anything except the real-LLM path. Public demo view needs no key at all (P1).

---

## 4. UI — Streamlit app (not React)

**Decision (2026-09-06):** presentation layer is a **Streamlit** app (Python, ≥1.57),
replacing v1's React/TS/Vite dashboard. The FastAPI REST layer from SPEC §3/§6 stays —
the Streamlit app is its client, exactly as the React app was. Widget/theme claims
below are grounded in Streamlit 1.63's bundled reference docs (see §4.6).

### 4.1 Architecture

Two Python processes in dev: FastAPI on `:8000`, `streamlit run app.py` on `:8501`.
The app fetches rows/stats/export with **httpx running server-side** (inside
Streamlit's Python process) — the browser never calls the API, so **no CORS config**
is needed (v1 needed a Vite proxy for the same reason). API surface unchanged:
`/health /stats /rows /export.csv /metrics /hotels` + `POST /rows/{id}/gold`.

Alternative considered and rejected: Streamlit reading SQLite directly — the SPEC
mandates the REST layer and TS20–27 exercise it, so the API stays the data contract.

### 4.2 Widget map (requirement → Streamlit element)

| Requirement (flow/test) | Streamlit implementation |
|---|---|
| Stats bar: Total / OK / Needs review / Unlabeled (TS32) | 4× `st.metric(border=True)` in `st.container(horizontal=True)`; data from GET /stats via `@st.cache_data(ttl="15s")` |
| Filters: hotel (top-50 `/hotels`), rating, status (TS24/25/32) | sidebar: `st.selectbox` (hotel, status) + `st.multiselect`/`st.slider` (rating); counts/table refetch on change |
| Virtualized table, smooth on 50k rows (TS30, U1) | `st.dataframe` — built-in virtualization, no extra library; one page at a time per SPEC: query /rows with limit/offset and page via `st.pagination(n_pages, key=…)` into an `st.empty()` slot (the layouts-reference pagination pattern) |
| `needs_review` visibly marked (TS31, U3/U16) | status column as colored badges (`st.column_config.MultiselectColumn`) or badge markdown; `needs_review` = red `#e60000` treatment (red doubles as the validation signal); row tint via pandas Styler **coloring only** |
| Long review text wraps, layout holds (TS33) | `st.dataframe` with configured columns; full complaint readable in an expander/detail row (Flow 3 "read it aloud" path) |
| Zero rows after filter (TS34) | empty page → `st.info` empty-state message |
| API down → error state (TS27) | every httpx call in try/except → `st.error` banner; the app never raises to a blank screen |
| Export CSV, Excel+BOM, filtered only (TS26, H9, A5–A6) | button fetches GET /export.csv bytes → `st.download_button(file_name="export.csv", mime="text/csv")` (utf-8-sig BOM preserved). Note: `st.download_button` is not allowed inside `st.form` |
| Gold save (TS40/41, V1) | pick a `needs_review` row → `@st.dialog` (or inline `st.form`): `st.selectbox` of the 7 themes + `st.form_submit_button("Save gold")` → POST /rows/{id}/gold; API 400 (invalid theme) rendered as `st.error`; success → `st.toast` + rerun |
| Counts match /stats (TS32) | stats and table fetched in the same rerun from the same filter state |

### 4.3 Required by the docs

| Component | Why |
|---|---|
| Streamlit ≥ 1.57 | the UI runtime (replaces React); bundled skill docs ship inside the wheel at `streamlit/.agents/skills/developing-with-streamlit/` |
| httpx | server-side API client (rows/stats/export/gold) — no browser CORS |
| `st.dataframe` | virtualized data grid (TS30); no separate virtualization dependency |
| `.streamlit/config.toml` theme | carries the `DOCS/design.md` tokens (U8–U17) — see §4.5 |
| Inter (weights 300–800) | design.md substitute face, loaded through the theme `font` setting |

### 4.4 Required UI behavior (unchanged contract)

- Stats bar: Total / OK / Needs review / Unlabeled, matching `/stats` (TS32)
- Filters: hotel (dropdown from `/hotels`, top 50) or rating + status; counts update
- `needs_review` rows visibly marked (color/badge) (TS31)
- Long text wraps, layout holds (TS33); empty state on zero rows (TS34)
- API-down → error message, not a blank crash (TS27)

### 4.5 Design-system implementation — design.md → `.streamlit/config.toml`

design.md is a brand analysis turned token spec. OpenEval2 reuses **metrics only**;
Vodafone logo/photography/speechmark assets are never shipped (U17). Streamlit 1.63
theme keys (from the bundled `theme.md`):

```toml
# .streamlit/config.toml
[theme]
base = "light"                        # single [theme] → app locked to light mode (canvas brand)
primaryColor = "#e60000"              # colors.primary — CTAs/validation; white on it ≈ 4.8:1 (WCAG AA text, AAA display)
backgroundColor = "#ffffff"           # colors.canvas
secondaryBackgroundColor = "#f2f2f2"  # colors.canvas-soft (widgets, chips, metric bands)
textColor = "#25282b"                 # colors.ink
borderColor = "#25282b"               # Level-1 hairline (design.md: 1px ink borders)
font = "Inter:https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap"  # substitute face
baseRadius = "6px"                    # rounded.card / rounded.sm (cards, inputs)
buttonRadius = "full"                 # pill CTAs — design.md pill-lg intent; "full" is Streamlit's pill keyword
showWidgetBorder = true               # hairline outlines
# Optional semantic status colors for badges/indicators:
redColor = "#e60000"                  # needs_review marker (red doubles as validation signal)
```

Notes grounded in the reference docs:
- **Elevation (U13) is free**: Streamlit surfaces are flat by default — no drop
  shadows to suppress; hairlines come from `showWidgetBorder`/`borderColor`.
- **Typography (U10)**: full theme font-family via the Google-Fonts URL form, plus
  `headingFont` if heading weights must differ; weights 300/400/600/700/800 available.
  design.md's display-hero scale (up to 144 px) does not fit a data dashboard — use
  the lower end of the scale, and apply the brand's UPPERCASE weight-800 `-1px`
  tracking "hero voice" to section headings via injected CSS
  (`st.markdown` `<style>`), not to body/table text. No mono companion needed.
- **Radius keywords** in 1.63: `none`/`small`(4 px)/`medium`(8 px)/`large`(12 px)/
  `full` (pill), or explicit px/rem — `6px` and `"full"` above are exact.
- **Row-level coloring**: pandas Styler for **coloring only** (e.g. red-tint
  `needs_review`); never Styler for value formatting — use `column_config` for that.
- **Contrast honesty**: design.md claims AAA for its buttons; measured
  white-on-`#e60000` ≈ 4.8:1 is WCAG AA for normal text and AAA for large/display
  text. Do not restate the blanket AAA claim for small labels.

**Not applied** (marketing-only chrome with no dashboard role, or Vodafone brand
assets): editorial hero photography, the speechmark logo orb, nav/footer link farms,
pricing-tier / cart-drawer / auth-form / media-button surfaces.

### 4.6 Reference docs to consult while building

Streamlit ≥ 1.57 ships version-matched skill docs inside the installed package at
`streamlit/.agents/skills/developing-with-streamlit/references/` — read these before
writing app code (checked against 1.63 for this doc):

| File | Covers |
|---|---|
| `theme.md` | `.streamlit/config.toml` keys used above |
| `data-display.md` | `st.dataframe`, `column_config`, badges, Styler-vs-format rules |
| `layouts.md` | containers, sidebar, `st.pagination` + `st.empty` slot pattern, `@st.dialog`, forms |
| `dashboards.md` | KPI metric rows, border cards, skeleton/fragment loading |
| `performance.md` | `@st.cache_data(ttl=…)` for API fetches, `@st.fragment` |
| `testing.md` | AppTest-based tests to mirror TS30–34 in CI |

---

## 5. Repo hygiene & deployment

| Concern | Requirement | Tool |
|---|---|---|
| No CSV, no sqlite in git (H10, TS01) | Hard | `.gitignore`: `Dataset/*.csv`, `*.sqlite`, `data/` |
| README requirements | Hard | README names Kaggle dataset, caps, 10-pt scale, "not employer data" (TS50–51) |
| Public demo | Hard | Host serves **synthetic hotel-shaped CSV** only; no Kaggle file; no key to view (TS52, P1) |
| No Vodafone brand assets shipped | Hard | design.md tokens only — no speechmark orb, wordmark, or Vodafone photography; fonts = Inter substitute (design.md font note, U17). No `ui/dist` exists anymore (no build step) — audit the Streamlit app + static files before deploy |
| CI | Planned (not yet added) | GitHub Actions: `pip install -r requirements.txt && pytest` (39 tests) + optional Streamlit AppTest smoke — green with mock labeler (TS44) |

Deployment shape: one small VPS or free-tier host running two Python processes —
`uvicorn api.app:app` (FastAPI on :8000) and `streamlit run app.py` (UI on :8501,
behind the host's proxy for production). SQLite is a single file, so there is no
database server to provision.

---

## 6. Dependency manifests (implemented — this is what `requirements.txt` pins)

### `requirements.txt`
Python floor: **3.11+** (v1-proven). One file for API + Streamlit app + scripts — the whole stack is Python.
```
fastapi
uvicorn[standard]   # API host (v1-proven)
pandas              # ingest, seed-42 sampling, dataframe display
httpx               # LLM calls + Streamlit's server-side API client
streamlit>=1.57     # the UI (checked against 1.63 for this doc; keep >=1.57 floor)
pytest
```
(`sqlite3`, `csv`, `random` come from the Python standard library — no package needed.)

### No `package.json`
The UI is Python (Streamlit) — **no Node/npm, no package.json, no build step, no
`ui/dist`**. Theme lives in `.streamlit/config.toml` (repo root, next to the app);
Inter is loaded through the theme `font` setting, not an npm font package.

---

## 7. Hard caps enforced in code

From SPEC §2 + §11 — put these in `config.py`, not scattered:
| Cap | Value |
|---|---|
| Ingest sample | 50,000 (seed 42) |
| Labeled rows (paid model) | ≤ 200 (v1), 100–200 per prompt (v2) |
| Paid-model absolute budget | ≤ 300 rows |
| `/hotels` list | top 50 most frequent |
| Browser rows | one page only (limit/offset) |

---

## 8. Where each doc's tooling claims land

| Doc claim | Stack item |
|---|---|
| "scripts/ingest.py --sample 50000 --seed 42" | pandas + sqlite3 |
| "SQLite is the warehouse stand-in" | sqlite3 |
| FastAPI endpoints | fastapi + uvicorn |
| "virtualized table" (SPEC UI; TS30) | `st.dataframe` — built-in virtualization |
| "UI = Streamlit" (user decision 2026-09-06) | `streamlit>=1.57`; widget map in §4 |
| "two labelers" | LLM provider(s) behind mock/llm interface |
| "Excel + BOM + header" | `csv` module, `utf-8-sig` output |
| "pytest with no key — all green" | mock labeler default + pytest |
| "Styled from `DOCS/design.md` tokens" (U8–U17, via Streamlit) | `.streamlit/config.toml`: `#e60000` primary / ink text / canvas surfaces, Inter via `font`, `buttonRadius="full"`, flat by default (no shadows) |
