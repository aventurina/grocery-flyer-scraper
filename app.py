"""Flask API and web page for the grocery flyer scraper.

The public demo only ever scrapes the bundled sample flyer. It never accepts a
URL from a visitor, so it can't be used to scrape other sites or reach internal
addresses. Scrapes are cached and limited per day to protect the server.

Endpoints:
    GET  /                 web page
    POST /api/scrape       run (or reuse a recent) scrape of the sample flyer
    GET  /api/items        latest results; filters: category, max_price, q
    GET  /api/health       health check
    GET  /sample-flyer     the sample flyer page that gets scraped
"""
import os
import threading
import time
from datetime import date, datetime, timezone

from flask import Flask, jsonify, render_template, request, send_from_directory

from scraper import BASE_DIR, SAMPLE_URL, scrape_flyer

app = Flask(__name__)

DAILY_LIMIT = int(os.environ.get("DAILY_SCRAPE_LIMIT", "30"))
CACHE_SECONDS = int(os.environ.get("CACHE_SECONDS", "300"))

_lock = threading.Lock()
_state = {}


def reset_state():
    _state.update(
        items=[], scraped_at=None, fetched_monotonic=0.0, day=date.today(), scrapes_today=0
    )


reset_state()


def filter_items(items, category=None, max_price=None, q=None):
    result = items
    if category:
        result = [i for i in result if i["category"].lower() == category.lower()]
    if max_price is not None:
        result = [i for i in result if i["price"] is not None and i["price"] <= max_price]
    if q:
        result = [i for i in result if q.lower() in i["name"].lower()]
    return result


def payload(items, **extra):
    return {
        "count": len(items),
        "scraped_at": _state["scraped_at"],
        "items": items,
        **extra,
    }


@app.get("/")
def index():
    return render_template("index.html", daily_limit=DAILY_LIMIT)


@app.get("/sample-flyer")
def sample_flyer():
    return send_from_directory(BASE_DIR / "sample_site", "flyer.html")


@app.get("/api/health")
def health():
    return jsonify(status="ok")


@app.get("/api/items")
def get_items():
    max_price = request.args.get("max_price", type=float)
    items = filter_items(
        _state["items"],
        category=request.args.get("category"),
        max_price=max_price,
        q=request.args.get("q"),
    )
    return jsonify(payload(items, categories=sorted({i["category"] for i in _state["items"]})))


@app.post("/api/scrape")
def scrape():
    with _lock:  # one browser at a time keeps memory use low on a small server
        if _state["day"] != date.today():
            _state.update(day=date.today(), scrapes_today=0)

        fresh = time.monotonic() - _state["fetched_monotonic"] < CACHE_SECONDS
        if _state["scraped_at"] and fresh:
            return jsonify(payload(_state["items"], cached=True))

        if _state["scrapes_today"] >= DAILY_LIMIT:
            return (
                jsonify(error="Daily scrape limit reached. Please try again tomorrow."),
                429,
            )

        try:
            items = scrape_flyer(SAMPLE_URL)
        except Exception:
            app.logger.exception("Scrape failed")
            return jsonify(error="The scrape failed. Please try again later."), 502

        _state.update(
            items=items,
            scraped_at=datetime.now(timezone.utc).isoformat(),
            fetched_monotonic=time.monotonic(),
            scrapes_today=_state["scrapes_today"] + 1,
        )
        return jsonify(payload(items, cached=False))


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", "5000")))
