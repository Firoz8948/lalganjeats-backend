# backend/app/core/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days
    ENVIRONMENT: str = "development"

    # Comma-separated list, e.g. https://lalganjeats.com,https://www.lalganjeats.com
    CORS_ORIGINS: str = "http://localhost:4200"
    FRONTEND_URL: str = "http://localhost:4200"

    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    RAZORPAY_ACCOUNT_NUMBER: str = ""

    RENFLAIR_API_KEY: str = ""
    GOOGLE_MAPS_API_KEY: str = ""
    SMS_BRAND_NAME: str = "LalganjEats"
    DELIVERY_OFFER_WAIT_SECONDS: int = 10

    class Config:
        env_file = ".env"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
