from app.modules.admin.services.catalog import normalize_subcategory_names, slugify


def test_slugify_builds_stable_catalog_slug():
    assert slugify("Golgappa / Pani Puri") == "golgappa-pani-puri"


def test_subcategory_seed_names_are_case_insensitively_unique():
    assert normalize_subcategory_names(
        ["Snacks", "chinese", "Chinese", " snacks "]
    ) == ["Snacks", "chinese"]
