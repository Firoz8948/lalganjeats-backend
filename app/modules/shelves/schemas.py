# backend/app/modules/shelves/schemas.py
from pydantic import BaseModel, Field

from app.modules.shelves.models import DEFAULT_CARD_BG, DEFAULT_IMAGE_BG, DEFAULT_SECTION_BG

HEX_COLOR = r"^#[0-9a-fA-F]{6}$"


class ShelfSave(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    sort_order: int = Field(0, ge=0, le=9999)
    section_bg_color: str = Field(DEFAULT_SECTION_BG, pattern=HEX_COLOR)
    image_bg_color: str = Field(DEFAULT_IMAGE_BG, pattern=HEX_COLOR)
    card_bg_color: str = Field(DEFAULT_CARD_BG, pattern=HEX_COLOR)
    view_all_subcategory_id: int | None = None
    is_active: bool = True
    # Display order of the row = order of this list.
    product_ids: list[int] = Field(default_factory=list, max_length=60)
