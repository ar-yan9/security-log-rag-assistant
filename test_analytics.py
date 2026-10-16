import json
import pytest
from analytics import metadata, summarize
from retrieval import read_records
from fastapi.testclient import TestClient
import app


@pytest.fixture
def rows():
    return [
        {
            "id": "a",
            "line": 1,
            "text": "one failure",
            "fields": metadata(
                {
                    "timestamp": "2026-01-01T01:00:00+01:00",
                    "service": "ssh",
                    "outcome": "failure",
                    "source_ip": "192.0.2.10",
                }
            ),
        },
        {
            "id": "b",
            "line": 2,
            "text": "five failures summarized in ONE record",
            "fields": metadata(
                {
                    "timestamp": "2026-01-01T00:01:00Z",
                    "service": "ssh",
                    "outcome": "failure",
                    "source_ip": "192.0.2.10",
                }
            ),
        },
        {"id": "c", "line": 3, "text": "untagged backup"},
    ]


def test_all_rows_not_top_k(rows):
    r = summarize(rows * 30)
    assert r["matching_records"] == 90 and len(r["timeline"]) == 90
    assert r["by_outcome"] == [
        {"value": "failure", "records": 60},
        {"value": "(unknown)", "records": 30},
    ]


def test_filters_citations_and_utc(rows):
    r = summarize(
        rows,
        service="ssh",
        outcome="failure",
        source_ip="192.0.2.10",
        start="2026-01-01T00:00:00Z",
        end="2026-01-01T00:01:00Z",
    )
    assert r["matching_records"] == 1 and r["timeline"][0]["event_id"] == "a"
    assert r["timeline"][0]["source_line"] == 1
    assert summarize(rows, source_ip="203.0.113.99")["matching_records"] == 0


@pytest.mark.parametrize(
    "value",
    [
        {"timestamp": "Jan 1"},
        {"timestamp": "2026-01-01T00:00:00"},
        {"source_ip": "not ip"},
        {"madeup": "x"},
        {"service": 1},
    ],
)
def test_bad_fields(value):
    with pytest.raises(ValueError):
        metadata(value)


def test_structured_ingestion(tmp_path, rows):
    p = tmp_path / "events.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in rows), encoding="utf-8")
    loaded = read_records(p)
    assert loaded[0]["fields"]["timestamp"] == "2026-01-01T00:00:00+00:00"
    assert "fields" not in loaded[2]


def test_analytics_api_without_model(tmp_path, rows, monkeypatch):
    p = tmp_path / "events.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in rows), encoding="utf-8")
    monkeypatch.setenv("SECURITY_LOG_FILE", str(p))
    monkeypatch.setenv("RETRIEVAL_MODE", "semantic")
    monkeypatch.setattr(app, "get_index", lambda: pytest.fail("no embedding required"))
    with TestClient(app.app) as client:
        r = client.post("/api/analytics", json={"outcome": "failure"})
        assert r.status_code == 200 and r.json()["matching_records"] == 2
        assert (
            client.post("/api/analytics", json={"start": "yesterday"}).status_code
            == 400
        )
        assert (
            client.post(
                "/api/search",
                json={"question": "ssh"},
                headers={"Origin": "https://outside.invalid"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/analytics", content="{}", headers={"Content-Type": "text/plain"}
            ).status_code
            == 415
        )


def test_time_bounds(rows):
    with pytest.raises(ValueError):
        summarize(rows, start="2026-01-02T00:00:00Z", end="2026-01-01T00:00:00Z")


def test_latest_valid_year_still_before_undated():
    dated = {
        "id": "last",
        "line": 2,
        "text": "far future fixture",
        "fields": metadata({"timestamp": "9999-01-01T00:00:00Z"}),
    }
    undated = {"id": "unknown", "line": 1, "text": "no date"}
    assert [x["event_id"] for x in summarize([undated, dated])["timeline"]] == [
        "last",
        "unknown",
    ]


UTC_OVERFLOWS = [
    "0001-01-01T00:00:00+01:00",
    "9999-12-31T23:59:59-01:00",
]


@pytest.mark.parametrize("stamp", UTC_OVERFLOWS)
def test_utc_normalization_overflow_is_invalid_input(stamp):
    with pytest.raises(ValueError, match="Timestamp"):
        metadata({"timestamp": stamp})


@pytest.mark.parametrize("field", ["start", "end"])
@pytest.mark.parametrize("stamp", UTC_OVERFLOWS)
def test_utc_overflow_filter_returns_400(field, stamp):
    with TestClient(app.app) as client:
        response = client.post("/api/analytics", json={field: stamp})
        assert response.status_code == 400
        assert "offset" in response.json()["detail"]


@pytest.mark.parametrize("stamp", UTC_OVERFLOWS)
def test_utc_overflow_corpus_returns_400(tmp_path, monkeypatch, stamp):
    path = tmp_path / "overflow.jsonl"
    path.write_text(json.dumps({"id": "boundary", "text": "synthetic event",
                               "fields": {"timestamp": stamp}}), encoding="utf-8")
    monkeypatch.setenv("SECURITY_LOG_FILE", str(path))
    with TestClient(app.app) as client:
        assert client.post("/api/analytics", json={}).status_code == 400


@pytest.mark.parametrize("stamp,expected", [
    ("0001-01-01T01:00:00+01:00", "0001-01-01T00:00:00+00:00"),
    ("9999-12-31T22:59:59-01:00", "9999-12-31T23:59:59+00:00"),
])
def test_representable_utc_boundaries_still_accepted(stamp, expected):
    assert metadata({"timestamp": stamp})["timestamp"] == expected
