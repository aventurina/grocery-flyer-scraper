import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as app_module  # noqa: E402

FAKE_ITEMS = [
    {"name": "Whole Milk", "category": "Dairy", "price_text": "$3.29", "price": 3.29, "details": "1 gallon"},
    {"name": "Large Eggs", "category": "Dairy", "price_text": "$2.49", "price": 2.49, "details": "dozen"},
    {"name": "Gala Apples", "category": "Produce", "price_text": "$1.49", "price": 1.49, "details": "per lb"},
]


@pytest.fixture
def client(monkeypatch):
    app_module.reset_state()
    calls = {"count": 0}

    def fake_scrape(url):
        calls["count"] += 1
        return list(FAKE_ITEMS)

    monkeypatch.setattr(app_module, "scrape_flyer", fake_scrape)
    app_module.app.config["TESTING"] = True
    client = app_module.app.test_client()
    client.calls = calls
    yield client
    app_module.reset_state()


def test_health(client):
    assert client.get("/api/health").get_json() == {"status": "ok"}


def test_index_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Grocery Flyer Scraper" in response.data


def test_items_empty_before_scrape(client):
    data = client.get("/api/items").get_json()
    assert data["count"] == 0
    assert data["scraped_at"] is None


def test_scrape_returns_items(client):
    response = client.post("/api/scrape")
    data = response.get_json()
    assert response.status_code == 200
    assert data["count"] == 3
    assert data["cached"] is False


def test_second_scrape_uses_cache(client):
    client.post("/api/scrape")
    data = client.post("/api/scrape").get_json()
    assert data["cached"] is True
    assert client.calls["count"] == 1


def test_filter_by_category(client):
    client.post("/api/scrape")
    data = client.get("/api/items?category=dairy").get_json()
    assert [i["name"] for i in data["items"]] == ["Whole Milk", "Large Eggs"]
    assert data["categories"] == ["Dairy", "Produce"]


def test_filter_by_max_price_and_search(client):
    client.post("/api/scrape")
    assert client.get("/api/items?max_price=2.5").get_json()["count"] == 2
    assert client.get("/api/items?q=apple").get_json()["count"] == 1


def test_daily_limit_returns_429(client, monkeypatch):
    monkeypatch.setattr(app_module, "DAILY_LIMIT", 1)
    monkeypatch.setattr(app_module, "CACHE_SECONDS", 0)  # force a fresh scrape each time
    assert client.post("/api/scrape").status_code == 200
    assert client.post("/api/scrape").status_code == 429


def test_scrape_failure_returns_502(client, monkeypatch):
    def boom(url):
        raise RuntimeError("browser crashed")

    monkeypatch.setattr(app_module, "scrape_flyer", boom)
    response = client.post("/api/scrape")
    assert response.status_code == 502
    assert "browser crashed" not in response.get_data(as_text=True)


def test_sample_flyer_is_served(client):
    response = client.get("/sample-flyer")
    assert response.status_code == 200
    assert b"Sample Market" in response.data
    response.close()
