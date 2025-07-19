"""
Configuration settings for the ingestion service
"""

import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/dossier")
    
    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Frappe API
    frappe_url: str = os.getenv("FRAPPE_URL", "")
    frappe_api_key: str = os.getenv("FRAPPE_API_KEY", "")
    frappe_api_secret: str = os.getenv("FRAPPE_API_SECRET", "")
    
    # Processing settings
    default_batch_size: int = int(os.getenv("DEFAULT_BATCH_SIZE", "100"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    class Config:
        env_file = ".env"


settings = Settings()