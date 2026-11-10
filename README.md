# Grocery Flyer Scraper

[![Tests](https://github.com/aventurina/grocery-flyer-scraper/actions/workflows/tests.yml/badge.svg)](https://github.com/aventurina/grocery-flyer-scraper/actions/workflows/tests.yml)

A web scraper built with Python and Playwright, with a command-line tool and a Flask web app. It loads a grocery flyer page in a headless browser, extracts every item on sale, and serves the results through a REST API and a searchable web page. It runs against a bundled sample flyer, and the command-line tool can be pointed at other flyer pages with custom CSS selectors.

![Grocery Flyer Scraper screenshot](docs/screenshot-grocery-flyer-scraper.png)

**[Live Demo](#)** *(add link when ready)*

## Features

- Scrapes JavaScript-rendered pages that a plain HTTP request can't read
- Handles infinite scroll: scrolls until the item count stops growing
- Parses deal prices into per-item prices (`2 for $5`, `3/$10`, `99¢`, `$3.99`)
- Checks `robots.txt` before scraping a website and refuses disallowed pages
- Saves results to CSV and JSON, with optional SQLite storage
- Prints a table of every item on sale, sorted by category
- Configurable CSS selectors, so the same scraper can work with other flyer layouts
- Does not try to get around sites that block automated browsers
- Flask REST API with filtering by category, maximum price, and search text
- Web page with a scrape button, sortable table, and live filters
- Demo safeguards: it only scrapes the sample flyer, caches results, and limits fresh scrapes per day

## Tech stack

- Python 3
- [Playwright](https://playwright.dev/python/) for headless browser automation
- [Flask](https://flask.palletsprojects.com/) and [gunicorn](https://gunicorn.org/) for the API and web page
- Vanilla JavaScript and hand-written CSS for the front end
- SQLite (`sqlite3`) for optional storage
- [pytest](https://pytest.org/) for testing, with GitHub Actions running the tests on every push
- Docker for deployment on [Render](https://render.com/)

## How it works

The sample flyer renders its items with JavaScript after the page loads, and only shows eight at first. The scraper waits for the first items to appear, then scrolls the page repeatedly until no new items load. It reads each item's name, category, price, and details using CSS selectors, converts the price text to a number, and writes the results out. A bad selector raises a clear error instead of returning an empty list.

## Getting started

**Prerequisites:** Python 3.9 or newer.

```bash
git clone https://github.com/aventurina/grocery-flyer-scraper.git
cd grocery-flyer-scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Start the web app at `http://localhost:5000`:

```bash
python app.py
```

Or run the command-line scraper on the bundled sample flyer:

```bash
python scraper.py
```

Command-line options:

```bash
python scraper.py --db flyer.db      # also save to SQLite
python scraper.py --show-browser     # watch the browser work
python scraper.py --url <flyer-url> --config my_store.json
```

Results are written to `output/flyer_items.csv` and `output/flyer_items.json`.

## API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/scrape` | Scrape the sample flyer, or return a cached result from the last few minutes |
| `GET` | `/api/items` | Latest results. Optional filters: `category`, `max_price`, `q` |
| `GET` | `/api/health` | Health check |
| `GET` | `/sample-flyer` | The sample flyer page that gets scraped |

Example: `GET /api/items?category=dairy&max_price=3` returns the dairy items at $3 or less.

Fresh scrapes are limited by `DAILY_SCRAPE_LIMIT` (default 30), and results are cached for `CACHE_SECONDS` (default 300). The limit returns a `429` response.

## Using it on a real flyer

1. Read the store's Terms of Service and `robots.txt`. Only scrape pages you are allowed to, at a low rate, for personal use.
2. Open the flyer page, right-click an item, and choose Inspect to find its CSS selectors.
3. Put them in a JSON file, for example `my_store.json`:

```json
{
  "item": ".product-card",
  "name": ".title",
  "price": ".price",
  "details": ".description",
  "category": ".dept"
}
```

4. Run `python scraper.py --url https://store.example/flyer --config my_store.json`.

## Testing

```bash
python -m pytest
```

The tests cover the price parser, an end-to-end scrape of the sample flyer including the lazy-loaded items, error handling for bad selectors, SQLite storage, and the API (filters, caching, the daily limit, and failure handling). They run offline against the local sample page. GitHub Actions runs them on every push.

## Deployment

The app is set up to deploy on Render as a Docker web service. `render.yaml` defines the service, and the `Dockerfile` installs Chromium for Playwright. Gunicorn runs one worker with one thread to keep memory use low, since each scrape launches a real browser.

Vercel is not a good fit, because serverless functions are too small for a Playwright browser.

## Project structure

```
app.py                   Flask app: web page and REST API
scraper.py               Scraper, price parser, output writers, and command-line tool
templates/index.html     Web page (table, sorting, and filters)
sample_site/flyer.html   Fictional JavaScript-rendered flyer used for the demo and tests
tests/test_scraper.py    Tests for the scraper
tests/test_app.py        Tests for the API
Dockerfile               Container image for deployment
render.yaml              Render service configuration
.github/workflows/       GitHub Actions workflow that runs the tests
requirements.txt         Python dependencies
output/                  Generated CSV and JSON results
```

## Author

**Aimee Venturina**
[LinkedIn](https://www.linkedin.com/in/aimee-venturina) · [GitHub](https://github.com/aventurina) · [Portfolio](https://aimeeventurina.pythonanywhere.com/)
