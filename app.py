"""OpenEval2 review dashboard (Streamlit) — client of the FastAPI REST layer.

Two Python processes (see DOCS/OpenEval2-TECH-STACK.md §4):
    uvicorn api.app:app            # terminal 1 — API on :8000
    streamlit run app.py           # terminal 2 — UI on :8501

API base is overridable via OPENEND_API_URL (default http://127.0.0.1:8000).
Widget map vs requirements: DOCS/OpenEval2-REQUIREMENTS-FLOW.md §U-design.
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx
import pandas as pd
import streamlit as st

import config  # single source of themes/statuses/rating bounds

API = os.environ.get("OPENEND_API_URL", "http://127.0.0.1:8000")
PAGE_SIZE = 100
STATUS_ORDER = ["needs_review", "ok", "unlabeled"]  # red first — the queue is the story
STATUS_COLORS = {"needs_review": "#e60000", "ok": "#7e7e7e", "unlabeled": "#bebebe"}
STATUS_LABELS = {"all": "All statuses", **{s: s for s in STATUS_ORDER}}
NEEDS_RED_TINT = "rgba(230, 0, 0, 0.07)"


class ApiError(RuntimeError):
    pass


def _request(method: str, path: str, **kwargs):
    try:
        with httpx.Client(base_url=API, timeout=25.0) as client:
            resp = client.request(method, path, **kwargs)
            resp.raise_for_status()
            return resp
    except httpx.RequestError as exc:
        raise ApiError(f"cannot reach API at {API}: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = exc.response.json().get("detail", "")
        except Exception:
            pass
        raise ApiError(f"API {exc.response.status_code}: {detail}") from exc


def api_get(path: str, params: dict | None = None):
    return _request("GET", path, params=params).json()


def api_post(path: str, json_body: dict):
    _request("POST", path, json=json_body)


def _bounds_params(rmin: int, rmax: int) -> dict:
    # full 1–10 range => send no bounds so rows with a NULL rating stay visible
    return {} if (rmin, rmax) == (1, config.RATING_MAX) else {
        "rating_min": rmin, "rating_max": rmax}


@st.cache_data(ttl=10, show_spinner=False)
def fetch_stats() -> dict:
    return api_get("/stats")


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_hotels() -> list[str]:
    return [h["name"] for h in api_get("/hotels")["hotels"]]


@st.cache_data(ttl=15, show_spinner=False)
def fetch_metrics() -> dict:
    return api_get("/metrics")


def fetch_page(hotel: str, status: str, rmin: int, rmax: int, offset: int) -> dict:
    params = {"limit": PAGE_SIZE, "offset": offset}
    if hotel != "All hotels":
        params["hotel"] = hotel
    if status != "all":
        params["status"] = status
    params.update(_bounds_params(rmin, rmax))
    return api_get("/rows", params=params)


def export_bytes(hotel: str, status: str, rmin: int, rmax: int) -> bytes:
    params = {}
    if hotel != "All hotels":
        params["hotel"] = hotel
    if status != "all":
        params["status"] = status
    params.update(_bounds_params(rmin, rmax))
    resp = _request("GET", "/export.csv", params=params)
    return resp.content  # utf-8-sig BOM preserved (Excel, TS26)


def _needs_review_tint(row: pd.Series):
    if row.get("status") == "needs_review":
        return [f"background-color: {NEEDS_RED_TINT}"] * len(row)
    return [""] * len(row)


def _pct(value) -> str:
    return "—" if value is None else f"{value:.1%}"


st.set_page_config(page_title="OpenEval2 — review queue", layout="wide",
                   page_icon=":material/reviews:")
st.markdown(
    """
    <style>
      /* design.md hero voice (U10): uppercase, weight 800, tight tracking */
      h1, h2 { text-transform: uppercase; letter-spacing: -0.5px; font-weight: 800 !important; }
      .block-container { max-width: 1400px; }
      .stApp { background-color: #ffffff; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Review queue")
st.caption("Booking.com hotel complaints · dual-LLM coded · humans review the disagreements")

view = st.sidebar.radio("View", ["Reviews", "Metrics"], label_visibility="collapsed")

try:
    if view == "Metrics":
        m = fetch_metrics()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total reviews", m["total"], border=True)
        c2.metric("OK", m["ok"], border=True)
        c3.metric("Needs review", m["needs_review"], border=True)
        c4.metric("Unlabeled", m["unlabeled"], border=True)

        st.subheader("v2 — gold")
        gc = m["gold_count"]
        g1, g2 = st.columns(2)
        g1.metric("Gold labels saved", gc, border=True)
        g2.metric("Agree with gold", _pct(m["agree_with_gold"]), border=True)
        if m["agree_with_gold"] is None:
            need = config.GOLD_MIN_FOR_AGREEMENT - gc
            st.caption(f"agree_with_gold is null until {config.GOLD_MIN_FOR_AGREEMENT} "
                       f"golds — save {max(need, 0)} more.")

        st.subheader("v2 — prompt A/B")
        ab = m["ab"]
        if ab and ab["runs"]:
            runs_df = pd.DataFrame(ab["runs"]).rename(
                columns={"run_id": "run", "prompt_version": "prompt", "n": "rows",
                         "cost": "cost ($)", "p50_ms": "p50 (ms)",
                         "created_at": "created"})
            st.dataframe(runs_df, hide_index=True)
            cmp = ab["comparison"]
            if cmp and cmp["n"]:
                st.write(f"**{cmp['runs'][0]} vs {cmp['runs'][1]}** — "
                         f"{cmp['n']} shared rows, agreement {_pct(cmp['agree'])}")
        else:
            st.info("No A/B runs yet — run `python scripts/run_ab.py` (mock is free).")
        st.stop()

    # ---- Reviews view -------------------------------------------------------
    hotels = ["All hotels"] + fetch_hotels()
    with st.sidebar:
        st.markdown("**Filters**")
        hotel = st.selectbox("Hotel", hotels, key="hotel")
        status = st.selectbox("Status", list(STATUS_LABELS), key="status",
                              format_func=STATUS_LABELS.__getitem__)
        rating_lo, rating_hi = st.slider(
            "Rating (Booking 1–10)", 1, config.RATING_MAX, (1, config.RATING_MAX),
            key="rating")

    stats = fetch_stats()
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total", stats["total"], border=True)
    s2.metric("OK", stats["ok"], border=True)
    s3.metric("Needs review", stats["needs_review"], border=True)
    s4.metric("Unlabeled", stats["unlabeled"], border=True)

    # Pagination key includes the filter signature so a filter change resets the
    # page to 1; the widget owns its session state (never set it manually).
    page_key = f"page_{hotel}_{status}_{rating_lo}_{rating_hi}"

    first = fetch_page(hotel, status, rating_lo, rating_hi, offset=0)
    total = first["total"]
    n_pages = max(1, math.ceil(total / PAGE_SIZE))

    if total == 0:
        st.info("No reviews match these filters — widen the hotel / rating / status selection.")
        st.stop()

    page_slot = st.empty()
    with st.container(horizontal=True, horizontal_alignment="left"):
        page = st.pagination(n_pages, key=page_key)
    st.caption(f"{total} reviews · {PAGE_SIZE} per page · showing page {page} of {n_pages}")

    page_data = first if page == 1 else fetch_page(
        hotel, status, rating_lo, rating_hi, offset=(page - 1) * PAGE_SIZE)

    df = pd.DataFrame(page_data["rows"])
    display_cols = ["id", "hotel", "rating", "text", "label_a", "label_b",
                    "agree", "status", "gold_label"]
    df = df[[c for c in display_cols if c in df.columns]].copy()
    df["agree"] = df["agree"].fillna(False).astype(bool)
    if "error" in page_data["rows"][0]:
        df["error"] = [r.get("error") for r in page_data["rows"]]

    page_slot.dataframe(
        df.style.apply(_needs_review_tint, axis=1),
        hide_index=True,
        height=520,
        column_config={
            "id": st.column_config.NumberColumn("ID", format="%d"),
            "hotel": st.column_config.TextColumn("Hotel"),
            "rating": st.column_config.NumberColumn("Rating", format="%.1f"),
            "text": st.column_config.TextColumn("Complaint (negative)", width="large"),
            "label_a": st.column_config.TextColumn("Label A"),
            "label_b": st.column_config.TextColumn("Label B"),
            "agree": st.column_config.CheckboxColumn("Agree", disabled=True),
            "status": st.column_config.MultiselectColumn(
                "Status", options=STATUS_ORDER,
                color=[STATUS_COLORS[s] for s in STATUS_ORDER]),
            "gold_label": st.column_config.TextColumn("Gold"),
            "error": st.column_config.TextColumn("Labeler note"),
        },
    )

    st.divider()
    st.subheader("Row detail & gold")
    if len(df):
        row_id = st.selectbox("Review id", df["id"].tolist(),
                              format_func=lambda i: f"#{i}", key="detail")
        row = next(r for r in page_data["rows"] if r["id"] == row_id)
        with st.expander("Full complaint", expanded=False):
            st.write(row.get("text") or "_(no negative text)_")
            st.caption("Positive: " + (row.get("text_pos") or "—"))
        if row.get("error"):
            st.caption(f":red[Labeler note: {row['error']}]")
        meta = (f"Hotel: {row.get('hotel') or '—'} · Rating: {row.get('rating')} / 10 · "
                f"Labels: {row.get('label_a') or '—'} / {row.get('label_b') or '—'} · "
                f"Status: {row.get('status')} · Gold: {row.get('gold_label') or '—'}")
        st.write(meta)

        with st.form("gold_form", border=True):
            gold = st.selectbox("Save gold theme (v2)", config.THEMES, key="gold_choice")
            primary = row.get("status") == "needs_review"
            submitted = st.form_submit_button(
                "Save gold", type="primary" if primary else "secondary")
        if submitted:
            try:
                api_post(f"/rows/{row_id}/gold", {"gold_label": gold})
                st.toast(f"gold = {gold} saved on #{row_id}")
                st.cache_data.clear()
                st.rerun()
            except ApiError as exc:
                st.error(str(exc))

    try:
        data = export_bytes(hotel, status, rating_lo, rating_hi)
        st.download_button("Download export.csv", data=data, file_name="export.csv",
                           mime="text/csv", type="primary",
                           icon=":material/download:")
    except ApiError as exc:
        st.error(str(exc))

except ApiError as exc:
    st.error(f"API unreachable: {exc}")
    if st.button("Retry"):
        st.rerun()
except Exception as exc:  # never a blank crash (TS27)
    st.error(f"Unexpected error: {type(exc).__name__}: {exc}")
    if st.button("Retry (reload)"):
        st.rerun()
