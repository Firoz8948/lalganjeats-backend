# backend/tests/test_sitemap.py
from datetime import datetime, timezone

from app.modules.seo.router import STATIC_PATHS, build_sitemap_xml


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows

    def query(self, *args, **kwargs):
        return _FakeQuery(self._rows)


def test_build_sitemap_includes_static_and_restaurant_urls(monkeypatch):
    monkeypatch.setattr(
        "app.modules.seo.router.settings.FRONTEND_URL",
        "https://lalganjeats.com",
    )
    stamp = datetime(2026, 8, 20, tzinfo=timezone.utc)
    db = _FakeSession(
        [
            (11, "hotel-rp-grand-restaurants", stamp, stamp),
            (42, "lalganj-town-restaurant", None, stamp),
        ]
    )

    xml = build_sitemap_xml(db)

    assert 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"' in xml
    for path, _, _ in STATIC_PATHS:
        assert f"<loc>https://lalganjeats.com{path}</loc>" in xml

    assert (
        "<loc>https://lalganjeats.com/restaurants/hotel-rp-grand-restaurants</loc>"
        in xml
    )
    assert (
        "<loc>https://lalganjeats.com/restaurants/lalganj-town-restaurant</loc>"
        in xml
    )
    assert "<lastmod>2026-08-20</lastmod>" in xml
    assert "/admin" not in xml
    assert "/checkout" not in xml
    assert "/restaurants/11" not in xml
