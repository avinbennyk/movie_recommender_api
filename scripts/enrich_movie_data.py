# scripts/enrich_movie_data.py
import requests
import pandas as pd
from sqlalchemy import create_engine, text
import time
import urllib.parse

# --- CONFIGURATION ---
# Paste your new OMDb key and Supabase credentials here
OMDB_API_KEY = "19fbc5cd"
DB_PASSWORD = "Remo123the"
DB_HOST = "db.epbqdwygxkvvkljjawnr.supabase.co"       # e.g., db.epbqdwygxkvvkljjawnr.supabase.co

# Construct the database URL safely
encoded_password = urllib.parse.quote_plus(DB_PASSWORD)
DATABASE_URL = f"postgresql://postgres:{encoded_password}@{DB_HOST}:5432/postgres"
engine = create_engine(DATABASE_URL)

OMDB_API_URL = "http://www.omdbapi.com/"

def get_poster_url(movie_title):
    """Fetches the poster URL for a movie from OMDb."""
    # OMDb uses 't' for title and 'apikey' for the key
    params = {"apikey": OMDB_API_KEY, "t": movie_title}
    try:
        response = requests.get(OMDB_API_URL, params=params)
        response.raise_for_status() # Raise an exception for bad status codes
        data = response.json()
        
        # Check if the API returned a successful response and a poster
        if data.get('Response') == 'True' and data.get('Poster') != 'N/A':
            return data['Poster']
            
    except requests.exceptions.RequestException as e:
        print(f"API request failed for {movie_title}: {e}")
    return None

# --- MAIN SCRIPT ---
with engine.connect() as connection:
    print("Fetching movies from the database that don't have a poster URL yet...")
    movies_df = pd.read_sql("SELECT movie_id, title FROM movies WHERE poster_url IS NULL", connection)
    
    if movies_df.empty:
        print("All movies already have poster URLs. Exiting.")
        exit()

    print(f"Found {len(movies_df)} movies to enrich.")
    
    for index, row in movies_df.iterrows():
        movie_id = row['movie_id']
        title = row['title']
        
        print(f"Processing: {title} (ID: {movie_id})")
        poster_url = get_poster_url(title)
        
        if poster_url:
            # Update the database with the new poster URL
            update_query = text("UPDATE movies SET poster_url = :poster_url WHERE movie_id = :movie_id")
            connection.execute(update_query, {"poster_url": poster_url, "movie_id": movie_id})
            print(f"  -> Found poster URL.")
        else:
            print(f"  -> Poster not found.")
        
        # OMDb's free tier is limited, so a short delay is good practice
        time.sleep(0.1) 
    
    connection.commit()
    print("✅ Movie enrichment complete.")