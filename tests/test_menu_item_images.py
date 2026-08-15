import asyncio
from types import SimpleNamespace

from app.modules.admin.schemas import AdminMenuItemCreate
from app.modules.admin.services import restaurants as restaurant_service


def test_menu_item_create_preserves_image_url():
    payload = AdminMenuItemCreate(
        name="Paneer Tikka",
        actual_price=120,
        image_url="https://cdn.example.com/menu/paneer.webp",
    )

    assert payload.image_url == "https://cdn.example.com/menu/paneer.webp"


def test_menu_item_upload_uses_dedicated_folder(monkeypatch):
    captured = {}

    async def fake_save_upload(file, folder, max_bytes):
        captured.update(folder=folder, max_bytes=max_bytes)
        return "/uploads/menu/paneer.webp"

    monkeypatch.setattr(restaurant_service, "save_upload", fake_save_upload)
    request = SimpleNamespace(base_url="https://api.example.com/")

    result = asyncio.run(
        restaurant_service.upload_restaurant_image(
            request=request,
            file=object(),
            purpose="menu_item",
        )
    )

    assert captured == {
        "folder": "restaurants/menu_items",
        "max_bytes": 2 * 1024 * 1024,
    }
    assert result["url"] == "https://api.example.com/uploads/menu/paneer.webp"
