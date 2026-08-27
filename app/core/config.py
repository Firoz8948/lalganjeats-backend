# backend/app/core/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days
    # Hotel / delivery partner sessions (password + OTP)
    PARTNER_ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days
    ENVIRONMENT: str = "development"

    # Comma-separated list, e.g. https://lalganjeats.com,https://www.lalganjeats.com
    CORS_ORIGINS: str = "http://localhost:4200"
    FRONTEND_URL: str = "http://localhost:4200"

    # local | bunny
    STORAGE_BACKEND: str = "local"
    BUNNY_STORAGE_ZONE: str = ""
    BUNNY_STORAGE_PASSWORD: str = ""
    BUNNY_STORAGE_HOST: str = "sg.storage.bunnycdn.com"
    BUNNY_CDN_URL: str = ""

    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    RAZORPAY_ACCOUNT_NUMBER: str = ""

    # PayU India (prepaid checkout). Salt must never be exposed to the frontend.
    # Merchant Key + Salt v1 power hosted/_payment. Client ID/Secret are optional
    # (PayU Biz / OAuth APIs) — store if your dashboard shows them.
    PAYU_MERCHANT_KEY: str = ""
    PAYU_MERCHANT_SALT: str = ""
    PAYU_CLIENT_ID: str = ""
    PAYU_CLIENT_SECRET: str = ""
    PAYU_MODE: str = "test"  # test | live
    # Public API origin for PayU surl/furl callbacks (no trailing slash)
    API_PUBLIC_URL: str = "http://localhost:8000"

    RENFLAIR_API_KEY: str = ""
    GOOGLE_MAPS_API_KEY: str = ""
    SMS_BRAND_NAME: str = "LalganjEats"
    DELIVERY_OFFER_WAIT_SECONDS: int = 10

    # Partner report delivery
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_USE_TLS: bool = True
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_GRAPH_VERSION: str = "v22.0"

    class Config:
        env_file = ".env"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
