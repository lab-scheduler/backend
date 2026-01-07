# app/config.py
from pydantic_settings import BaseSettings
from typing import Dict, Any
import os

class Settings(BaseSettings):
    # DB
    DATABASE_URL: str = "sqlite:///./dev.db"

    # Scheduler defaults
    DEFAULT_HOURS_PER_SHIFT: float = 8.0
    MAX_CONSECUTIVE_SHIFTS: int = 5
    MIN_REST_HOURS: int = 12
    DEFAULT_MAX_HOURS_PER_WEEK: float = 40.0
    PART_TIME_MAX_HOURS_PER_WEEK: int = 32

    # CP-SAT / OR-Tools toggle
    ORTOOLS_ENABLED: bool = False
    ORTOOLS_TIME_LIMIT_SECONDS: int = 10

    # Demo & environment
    APP_ENV: str = "development"
    SECRET_KEY: str = "..."
    VITE_API_URL: str = os.environ.get("VITE_API_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
