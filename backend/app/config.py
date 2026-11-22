from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://gate:gate@localhost:5432/gate"
    redis_url: str = "redis://localhost:6379/0"
    enrollment_shared_secret: str = "dev-only-change-me"
    credential_pepper: str = "dev-only-change-me"
    jwt_secret: str = "dev-only-change-me"
    enrollment_max_skew_seconds: int = 300
    cors_origins: str = "http://localhost:5500"  # comma-separated browser origins allowed to call the API


settings = Settings()
