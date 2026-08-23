# backend/app/modules/seo/router.py
from __future__ import annotations

from datetime import datetime, timezone
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.modules.restaurants.models import Restaurant

router = APIRouter(tags=["SEO"])

STATIC_PATHS: tuple[tuple[str, str, str], ...] = (
    # path, changefreq, priority
    ("/home", "daily", "1.0"),
    ("/restaurants", "daily", "0.9"),
    ("/offers", "daily", "0.8"),
    ("/legal/terms", "monthly", "0.4"),
    ("/legal/privacy", "monthly", "0.4"),
    ("/legal/refund", "monthly", "0.4"),
)


def _site_origin() -> str:
    return (settings.FRONTEND_URL or "https://lalganjeats.com").rstrip("/")


def _url_entry(
    loc: str,
    *,
    changefreq: str,
    priority: str,
    lastmod: str | None = None,
) -> str:
    parts = [
        "  <url>",
        f"    <loc>{escape(loc)}</loc>",
    ]
    if lastmod:
        parts.append(f"    <lastmod>{escape(lastmod)}</lastmod>")
    parts.extend(
        [
            f"    <changefreq>{escape(changefreq)}</changefreq>",
            f"    <priority>{escape(priority)}</priority>",
            "  </url>",
        ]
    )
    return "\n".join(parts)


def build_sitemap_xml(db: Session) -> str:
    origin = _site_origin()
    today = datetime.now(timezone.utc).date().isoformat()
    entries: list[str] = []

    for path, changefreq, priority in STATIC_PATHS:
        entries.append(
            _url_entry(
                f"{origin}{path}",
                changefreq=changefreq,
                priority=priority,
                lastmod=today,
            )
        )

    restaurants = (
        db.query(
            Restaurant.id,
            Restaurant.slug,
            Restaurant.updated_at,
            Restaurant.created_at,
        )
        .filter(
            Restaurant.is_active == True,  # noqa: E712
            Restaurant.is_approved == True,  # noqa: E712
            Restaurant.slug.isnot(None),
        )
        .order_by(Restaurant.id.asc())
        .all()
    )

    for restaurant_id, slug, updated_at, created_at in restaurants:
        stamp = updated_at or created_at
        lastmod = stamp.date().isoformat() if stamp is not None else today
        path_key = slug or str(restaurant_id)
        entries.append(
            _url_entry(
                f"{origin}/restaurants/{path_key}",
                changefreq="daily",
                priority="0.7",
                lastmod=lastmod,
            )
        )

    body = "\n".join(entries)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n"
        "</urlset>\n"
    )


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap(db: Session = Depends(get_db)) -> Response:
    """Dynamic public sitemap for crawlers (static pages + live restaurants)."""
    xml = build_sitemap_xml(db)
    return Response(
        content=xml,
        media_type="application/xml; charset=utf-8",
        headers={
            "Cache-Control": "public, max-age=300",
        },
    )
