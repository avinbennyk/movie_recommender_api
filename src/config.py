# src/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    supabase_url: str
    supabase_key: str

    class Config:
        env_file = ".env"

settings = Settings()