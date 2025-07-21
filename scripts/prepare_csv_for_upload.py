# scripts/prepare_csv_for_upload.py
import pandas as pd
print("Loading and preparing movie data...")
movies = pd.read_csv(
    'data/u.item', sep='|', encoding='latin-1', header=None,
    names=['movie_id', 'title', 'release_date', 'video_release_date', 'imdb_url', 'unknown', 'Action', 'Adventure', 'Animation', 'Childrens', 'Comedy', 'Crime', 'Documentary', 'Drama', 'Fantasy', 'Film-Noir', 'Horror', 'Musical', 'Mystery', 'Romance', 'Sci-Fi', 'Thriller', 'War', 'Western']
)
movies['title'] = movies['title'].str.replace(r'\s*\(\d{4}\)$', '', regex=True)
genre_cols = ['Action', 'Adventure', 'Animation', 'Childrens', 'Comedy', 'Crime', 'Documentary', 'Drama', 'Fantasy', 'Film-Noir', 'Horror', 'Musical', 'Mystery', 'Romance', 'Sci-Fi', 'Thriller', 'War', 'Western']
movies['genres'] = movies[genre_cols].apply(lambda row: '|'.join(row.index[row == 1]), axis=1)
movies_to_load = movies[['movie_id', 'title', 'genres']]
output_path = 'movies_to_upload.csv'
movies_to_load.to_csv(output_path, index=False)
print(f"✅ Successfully created '{output_path}'.")