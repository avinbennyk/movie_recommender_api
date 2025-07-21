# scripts/load_data_to_db.py
import pandas as pd
from sqlalchemy import create_engine
import urllib.parse

# --- PASTE YOUR NEW SUPABASE CREDENTIALS HERE ---
db_password = "Remo123the"
db_host = "db.epbqdwygxkvvkljjawnr.supabase.co" # e.g., db.xxxxxxxx.supabase.co

# URL-encode the password to handle special characters
encoded_password = urllib.parse.quote_plus(db_password)
DATABASE_URL = f"postgresql://postgres:{encoded_password}@{db_host}:5432/postgres"

engine = create_engine(DATABASE_URL)

print("Loading movies data from CSV file...")
movies = pd.read_csv(
    'data/u.item', sep='|', encoding='latin-1', header=None,
    names=['movie_id', 'title', 'release_date', 'video_release_date', 'imdb_url', 'unknown', 'Action', 'Adventure', 'Animation', 'Childrens', 'Comedy', 'Crime', 'Documentary', 'Drama', 'Fantasy', 'Film-Noir', 'Horror', 'Musical', 'Mystery', 'Romance', 'Sci-Fi', 'Thriller', 'War', 'Western']
)
movies['title'] = movies['title'].str.replace(r'\s*\(\d{4}\)$', '', regex=True)
genre_cols = ['Action', 'Adventure', 'Animation', 'Childrens', 'Comedy', 'Crime', 'Documentary', 'Drama', 'Fantasy', 'Film-Noir', 'Horror', 'Musical', 'Mystery', 'Romance', 'Sci-Fi', 'Thriller', 'War', 'Western']
movies['genres'] = movies[genre_cols].apply(lambda row: '|'.join(row.index[row == 1]), axis=1)
movies_to_load = movies[['movie_id', 'title', 'genres']]

print("Uploading movie data to the PostgreSQL database...")
try:
    movies_to_load.to_sql('movies', engine, if_exists='append', index=False)
    print("✅ Data uploaded successfully to the 'movies' table.")
except Exception as e:
    print(f"❌ An error occurred: {e}")