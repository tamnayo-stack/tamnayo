from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "review-automation"
    database_url: str = "postgresql+psycopg2://postgres:postgres@db:5432/review_app"
    redis_url: str = "redis://redis:6379/0"
    encryption_key: str = "change-me-with-fernet-key"
    scheduler_interval_seconds: int = 300

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
