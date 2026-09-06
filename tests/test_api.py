"""API contract tests (TS20–TS27, TS40–TS42, H8–H9) + v2 gold/metrics/A-B."""
import io
import csv as csv_module

from conftest import FIRST_LONG_ID, TOTAL_ROWS


def test_health(api_client):
    body = api_client.get("/health").json()
    assert body["status"] == "ok"
    assert body["reviews"] == TOTAL_ROWS
    assert body["labels"] == 0


def test_stats_before_labeling(api_client):
    body = api_client.get("/stats").json()
    assert body["total"] == TOTAL_ROWS
    assert body["needs_review"] == 6      # the 6 short texts, zero LLM spend
    assert body["unlabeled"] == TOTAL_ROWS - 6


def test_rows_honors_limit_offset(api_client):
    first = api_client.get("/rows", params={"limit": 20, "offset": 0}).json()
    second = api_client.get("/rows", params={"limit": 20, "offset": 20}).json()
    assert first["total"] == TOTAL_ROWS
    assert len(first["rows"]) == 20 and len(second["rows"]) == 20
    ids_a = {r["id"] for r in first["rows"]}
    ids_b = {r["id"] for r in second["rows"]}
    assert not ids_a & ids_b  # TS23: no overlap between pages


def test_rows_has_spec_fields(api_client):
    row = api_client.get("/rows", params={"limit": 1}).json()["rows"][0]
    for field in ("id", "text", "text_pos", "rating", "hotel", "nationality",
                  "label_a", "label_b", "agree", "status", "gold_label"):
        assert field in row


def test_rows_status_filter(api_client):
    body = api_client.get("/rows", params={"status": "needs_review", "limit": 2000}).json()
    assert body["total"] == 6
    assert all(r["status"] == "needs_review" for r in body["rows"])


def test_rows_hotel_filter(api_client):
    """TS25/H8: /rows?hotel= returns only that hotel."""
    body = api_client.get("/rows", params={"hotel": "Hotel A", "limit": 2000}).json()
    assert body["total"] > 0
    assert all(r["hotel"] == "Hotel A" for r in body["rows"])


def test_rows_rating_band_filter(api_client):
    low = api_client.get("/rows", params={"rating_min": 1, "rating_max": 4,
                                          "limit": 2000}).json()
    assert low["total"] > 0
    assert all(r["rating"] <= 4 for r in low["rows"])
    high = api_client.get("/rows", params={"rating_min": 9, "rating_max": 10,
                                           "limit": 2000}).json()
    assert all(r["rating"] >= 9 for r in high["rows"])


def test_hotels_endpoint_top50_sorted(api_client):
    body = api_client.get("/hotels").json()
    hotels = body["hotels"]
    assert len(hotels) <= 50
    counts = [h["count"] for h in hotels]
    assert counts == sorted(counts, reverse=True)
    assert hotels[0]["name"] == "Hotel A"  # 14 hotels / 216 rows => A is most frequent


def test_invalid_status_rejected(api_client):
    assert api_client.get("/rows", params={"status": "wat"}).status_code == 422


def test_disagreement_is_needs_review_with_error_surface(api_client, insert_label,
                                                         db_connect):
    """TS11 + Flow 6: disagreement => needs_review; flagged rows carry error text."""
    insert_label(FIRST_LONG_ID, "Room", "Staff")
    insert_label(FIRST_LONG_ID + 1, "Other", "Other", llm_error=1,
                 error="sanitized from dirty!!!: not in theme list")
    body = api_client.get("/rows", params={"status": "needs_review",
                                           "limit": 2000}).json()
    ids = {r["id"]: r for r in body["rows"]}
    assert FIRST_LONG_ID in ids
    flagged = ids[FIRST_LONG_ID + 1]
    assert flagged["error"] == "sanitized from dirty!!!: not in theme list"
    assert flagged["status"] == "needs_review"


def test_agreeing_ok_and_clash_needs_review(api_client, insert_label):
    """TS10 + TS14 via the API (status is derived, never stored)."""
    insert_label(FIRST_LONG_ID, "Staff", "Staff")                 # long, ok
    insert_label(FIRST_LONG_ID + 1, "Other", "Other")             # id 8 rating 3 => clash
    body = api_client.get("/rows", params={"limit": 2000}).json()
    by_id = {r["id"]: r for r in body["rows"]}
    assert by_id[FIRST_LONG_ID]["status"] == "ok"
    assert by_id[FIRST_LONG_ID + 1]["status"] == "needs_review"   # rating <= 4 clash


def test_gold_save_does_not_overwrite_ab(api_client, insert_label):
    """S6/V1: gold persists, A/B labels unchanged."""
    insert_label(FIRST_LONG_ID, "Room", "Staff", gold="Cleanliness")
    resp = api_client.post(f"/rows/{FIRST_LONG_ID}/gold", json={"gold_label": "Staff"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["gold_label"] == "Staff"
    assert body["label_a"] == "Room" and body["label_b"] == "Staff"  # untouched


def test_gold_invalid_400(api_client):
    assert api_client.post("/rows/7/gold",
                           json={"gold_label": "cheap!!!"}).status_code == 400
    assert api_client.post("/rows/999999/gold",
                           json={"gold_label": "Staff"}).status_code == 404


def test_export_csv_excel_bom_and_header(api_client):
    resp = api_client.get("/export.csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    text = resp.content.decode("utf-8-sig")   # BOM present means it decodes cleanly
    assert text.startswith("id,hotel,rating,text,label_a,label_b,agree,status,gold_label")
    assert len(text.strip().splitlines()) == TOTAL_ROWS + 1


def test_export_csv_respects_filters(api_client):
    all_text = api_client.get("/export.csv").content.decode("utf-8-sig")
    all_rows = list(csv_module.reader(io.StringIO(all_text)))[1:]
    hotel_text = api_client.get("/export.csv",
                                params={"hotel": "Hotel A"}).content.decode("utf-8-sig")
    hotel_rows = list(csv_module.reader(io.StringIO(hotel_text)))[1:]
    assert 0 < len(hotel_rows) < len(all_rows)
    assert all(r[1] == "Hotel A" for r in hotel_rows)  # column 2 = hotel


def test_metrics_gold_null_below_threshold_then_visible(api_client, insert_label):
    from config import GOLD_MIN_FOR_AGREEMENT
    body = api_client.get("/metrics").json()
    assert body["gold_count"] == 0
    assert body["agree_with_gold"] is None
    for i in range(GOLD_MIN_FOR_AGREEMENT):
        insert_label(FIRST_LONG_ID + i, "Room", "Room", gold="Room")
    body = api_client.get("/metrics").json()
    assert body["gold_count"] == GOLD_MIN_FOR_AGREEMENT
    assert body["agree_with_gold"] == 1.0


def test_ab_runs_and_comparison(api_client, db_path, monkeypatch):
    from scripts.run_ab import run_ab
    monkeypatch.setenv("OPENEND_DB_PATH", str(db_path))
    result = run_ab(db_path=db_path, count=50, seed=7, provider="mock")
    assert len(result["runs"]) == 2
    body = api_client.get("/metrics").json()
    assert len(body["ab"]["runs"]) == 2
    cmp = body["ab"]["comparison"]
    assert cmp["runs"] == ["v1", "v2"]
    assert cmp["n"] == 50
    assert cmp["agree"] == 1.0      # mock: same deterministic labeler for both runs
