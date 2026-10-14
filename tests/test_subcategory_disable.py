from sqlalchemy.dialects import postgresql

from app.modules.restaurants.product_search import sellable_product_filters
from app.modules.restaurants.service import subcategory_enabled_filter


def _sql(clause) -> str:
    return str(clause.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def test_filter_keeps_uncategorised_items_and_enabled_subcategories():
    sql = _sql(subcategory_enabled_filter())
    assert "menu_items.business_subcategory_id IS NULL" in sql
    assert "EXISTS" in sql
    assert "catalog_subcategories.is_active = true" in sql


def test_sellable_products_exclude_disabled_subcategories():
    sql = " ".join(_sql(clause) for clause in sellable_product_filters())
    assert "catalog_subcategories.is_active = true" in sql
