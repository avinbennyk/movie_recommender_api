# src/database.py
from sqlalchemy import create_engine
from supabase import create_client, Client
from .config import settings

# Client for authentication
supabase: Client = create_client(settings.supabase_url, settings.supabase_key)

# Engine for direct database access
engine = create_engine(settings.database_url)