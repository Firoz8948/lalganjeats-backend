from pydantic import BaseModel, Field


class CatalogNameCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)


class HomeBannerSlideUpdate(BaseModel):
    id: int | None = None
    slide_number: int | None = None
    desktop_image_url: str | None = None
    mobile_image_url: str | None = None
    is_active: bool | None = None


class HomeBannersSaveRequest(BaseModel):
    slides: list[HomeBannerSlideUpdate]


class HomeBannerPatchRequest(BaseModel):
    desktop_image_url: str | None = None
    mobile_image_url: str | None = None
    is_active: bool | None = None


class AdminMenuVariantCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=40)
    actual_price: float = Field(gt=0)
    original_price: float | None = Field(default=None, gt=0)


class AdminMenuItemCreate(BaseModel):
    name: str
    description: str | None = None
    # Ignored when supplied: backend derives display price from transfer price.
    price: float | None = Field(default=None, gt=0)
    actual_price: float | None = Field(default=None, gt=0)
    original_price: float | None = Field(default=None, gt=0)
    category_name: str = "Other"
    subcategory_id: int | None = None
    is_veg: bool = True
    is_bestseller: bool = False
    # Optional: Half / Full / custom. If empty, one Regular variant is created
    # from actual_price / original_price.
    variants: list[AdminMenuVariantCreate] | None = None
