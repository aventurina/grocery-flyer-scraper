import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper import SAMPLE_URL, parse_price, save_sqlite, scrape_flyer  # noqa: E402


@pytest.mark.parametrize(
    "text, expected",
    [
        ("$3.99", 3.99),
        ("$ 1.49", 1.49),
        ("2 for $5", 2.5),
        ("3/$10", 3.33),
        ("99¢", 0.99),
        ("59¢", 0.59),
        ("no price here", None),
        ("", None),
    ],
)
def test_parse_price(text, expected):
    assert parse_price(text) == expected


@pytest.fixture(scope="module")
def items():
    return scrape_flyer(SAMPLE_URL)


def test_scrapes_all_items_including_lazy_loaded(items):
    # The page only renders 8 items at first, the rest load on scroll.
    assert len(items) == 24


def test_item_fields_are_filled(items):
    for item in items:
        assert item["name"]
        assert item["category"]
        assert item["price"] is not None


def test_known_item(items):
    eggs = next(i for i in items if i["name"] == "Large Eggs")
    assert eggs["price"] == 2.49
    assert eggs["category"] == "Dairy"


def test_multi_buy_price(items):
    yogurt = next(i for i in items if i["name"] == "Greek Yogurt")
    assert yogurt["price_text"] == "3/$5"
    assert yogurt["price"] == 1.67


def test_bad_selector_raises():
    with pytest.raises(RuntimeError):
        scrape_flyer(SAMPLE_URL, {"item": ".does-not-exist"}, timeout_ms=1500)


def test_save_sqlite(items, tmp_path):
    import sqlite3

    db = tmp_path / "test.db"
    save_sqlite(items, db, SAMPLE_URL)
    count = sqlite3.connect(db).execute("SELECT COUNT(*) FROM flyer_items").fetchone()[0]
    assert count == 24
