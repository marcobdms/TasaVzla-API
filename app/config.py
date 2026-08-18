from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://tasavzla:secret@localhost:5432/tasavzla"
    bcv_retries: int = 3
    bcv_timeout: float = 15.0
    log_level: str = "INFO"

    # VET = UTC-4. Scheduler fires at 15:00, 17:00, 19:00 VET (Mon-Fri).
    # In UTC that's 19:00, 21:00, 23:00.
    scheduler_hours_utc: list[int] = [19, 21, 23]


settings = Settings()
