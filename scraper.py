"""Grocery flyer scraper built with Playwright.

Loads a weekly-flyer web page in a headless browser, scrolls to trigger lazy
loading, extracts every item on sale, and saves the results to CSV, JSON and
(optionally) SQLite.

Usage:
    python scraper.py                      # scrape the bundled sample flyer
    python scraper.py --url https://...    # scrape another flyer page
    python scraper.py --config my.json     # custom CSS selectors for that site
    python scraper.py --db flyer.db        # also store results in SQLite
"""
import argparse
import csv
import json
import os
import re
import sqlite3
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).parent
SAMPLE_URL = (BASE_DIR / "sample_site" / "flyer.html").as_uri()

# CSS selectors for one flyer item. Change these to match another site.
DEFAULT_SELECTORS = {
    "item": ".flyer-item",
    "name": ".item-name",
    "price": ".item-price",
    "details": ".item-details",
    "category": ".item-category",
}

USER_AGENT = "grocery-flyer-scraper/1.0 (personal learning project)"


def parse_price(text):
    """Return the per-item price as a float, or None if no price is found.

    "$3.99"      -> 3.99
    "2 for $5"   -> 2.5
    "3/$10"      -> 3.33
    "99¢"        -> 0.99
    """
    if not text:
        return None
    text = text.replace(",", "")

    multi = re.search(r"(\d+)\s*(?:for|/)\s*\$?\s*(\d+(?:\.\d{1,2})?)", text, re.I)
    if multi:
        quantity, total = int(multi.group(1)), float(multi.group(2))
        return round(total / quantity, 2) if quantity else None

    cents = re.search(r"(\d+)\s*¢", text)
    if cents:
        return round(int(cents.group(1)) / 100, 2)

    dollars = re.search(r"\$\s*(\d+(?:\.\d{1,2})?)", text)
    if dollars:
        return float(dollars.group(1))
    return None


def allowed_by_robots(url):
    """Check robots.txt for http(s) URLs. Local files are always allowed."""
    parts = urlparse(url)
    if parts.scheme not in ("http", "https"):
        return True
    parser = RobotFileParser(f"{parts.scheme}://{parts.netloc}/robots.txt")
    try:
        parser.read()
    except OSError:
        return False  # cannot confirm it is allowed, so do not scrape
    return parser.can_fetch(USER_AGENT, url)


def scroll_until_loaded(page, item_selector, max_rounds=30, pause_ms=600):
    """Scroll to the bottom repeatedly until the item count stops growing."""
    previous = -1
    for _ in range(max_rounds):
        count = page.locator(item_selector).count()
        if count == previous:
            break
        previous = count
        page.mouse.wheel(0, 100000)
        page.wait_for_timeout(pause_ms)


def text_of(element, selector):
    found = element.query_selector(selector)
    # text_content ignores CSS (inner_text would apply text-transform: uppercase)
    return (found.text_content() or "").strip() if found else ""


def scrape_flyer(url, selectors=None, headless=True, timeout_ms=15000):
    """Return a list of dicts, one per item found on the flyer page."""
    selectors = {**DEFAULT_SELECTORS, **(selectors or {})}
    if not allowed_by_robots(url):
        raise PermissionError(f"robots.txt does not allow scraping {url}")

    with sync_playwright() as p:
        # Chromium cannot use its sandbox when running as root inside Docker.
        launch_args = ["--no-sandbox"] if os.environ.get("CHROMIUM_NO_SANDBOX") else []
        browser = p.chromium.launch(headless=headless, args=launch_args)
        page = browser.new_context(user_agent=USER_AGENT).new_page()
        page.goto(url, wait_until="domcontentloaded")
        try:
            page.wait_for_selector(selectors["item"], timeout=timeout_ms)
        except PlaywrightTimeout:
            browser.close()
            raise RuntimeError(
                f"No elements matched '{selectors['item']}'. Check your selectors."
            )

        scroll_until_loaded(page, selectors["item"])

        items = []
        for element in page.query_selector_all(selectors["item"]):
            price_text = text_of(element, selectors["price"])
            items.append(
                {
                    "name": text_of(element, selectors["name"]),
                    "category": text_of(element, selectors["category"]),
                    "price_text": price_text,
                    "price": parse_price(price_text),
                    "details": text_of(element, selectors["details"]),
                }
            )
        browser.close()
    return items


def save_csv(items, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["name", "category", "price_text", "price", "details"]
        )
        writer.writeheader()
        writer.writerows(items)


def save_json(items, path):
    Path(path).write_text(json.dumps(items, indent=2), encoding="utf-8")


def save_sqlite(items, db_path, source_url):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS flyer_items (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               scraped_on TEXT, source TEXT, name TEXT, category TEXT,
               price_text TEXT, price REAL, details TEXT)"""
    )
    conn.executemany(
        "INSERT INTO flyer_items (scraped_on, source, name, category, price_text, price, details)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (date.today().isoformat(), source_url, i["name"], i["category"],
             i["price_text"], i["price"], i["details"])
            for i in items
        ],
    )
    conn.commit()
    conn.close()


def print_table(items):
    if not items:
        print("No items found.")
        return
    width = max(len(i["name"]) for i in items)
    print(f"\n{'ITEM'.ljust(width)}  {'PRICE':<10}  CATEGORY")
    print("-" * (width + 30))
    for i in sorted(items, key=lambda x: (x["category"], x["name"])):
        print(f"{i['name'].ljust(width)}  {i['price_text']:<10}  {i['category']}")
    print(f"\n{len(items)} items on sale.")


def main():
    parser = argparse.ArgumentParser(description="Scrape a grocery flyer page.")
    parser.add_argument("--url", default=SAMPLE_URL, help="Flyer page URL")
    parser.add_argument("--config", help="JSON file with CSS selectors")
    parser.add_argument("--out", default=str(BASE_DIR / "output"), help="Output folder")
    parser.add_argument("--db", help="SQLite file to append results to")
    parser.add_argument("--show-browser", action="store_true", help="Run with a visible browser")
    args = parser.parse_args()

    selectors = json.loads(Path(args.config).read_text()) if args.config else None
    items = scrape_flyer(args.url, selectors, headless=not args.show_browser)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    save_csv(items, out / "flyer_items.csv")
    save_json(items, out / "flyer_items.json")
    if args.db:
        save_sqlite(items, args.db, args.url)

    print_table(items)
    print(f"Saved to {out}/flyer_items.csv and flyer_items.json")


if __name__ == "__main__":
    main()
