import asyncio
from types import SimpleNamespace

from app.core.compressor import MAX_DIMENSION
from app.modules.admin.schemas import AdminMenuItemCreate
from app.modules.admin.services import restaurants as restaurant_service


def test_menu_item_create_preserves_image_url():
    payload = AdminMenuItemCreate(
        name="Paneer Tikka",
        actual_price=120,
        image_url="https://cdn.example.com/menu/paneer.webp",
    )

    assert payload.image_url == "https://cdn.example.com/menu/paneer.webp"


def _capture_upload(monkeypatch, purpose):
    captured = {}

    async def fake_save_upload(file, folder, max_dimension=None):
        captured.update(folder=folder, max_dimension=max_dimension)
        return "/uploads/menu/paneer.webp"

    monkeypatch.setattr(restaurant_service, "save_upload", fake_save_upload)
    request = SimpleNamespace(base_url="https://api.example.com/")
    result = asyncio.run(
        restaurant_service.upload_restaurant_image(
            request=request,
            file=object(),
            purpose=purpose,
        )
    )
    return captured, result


def test_menu_item_upload_uses_dedicated_folder(monkeypatch):
    captured, result = _capture_upload(monkeypatch, "menu_item")

    assert captured == {
        "folder": "restaurants/menu_items",
        "max_dimension": MAX_DIMENSION,
    }
    assert result["url"] == "https://api.example.com/uploads/menu/paneer.webp"


def test_subcategory_upload_is_downscaled_to_512(monkeypatch):
    captured, _ = _capture_upload(monkeypatch, "subcategory")

    assert captured["max_dimension"] == 512
