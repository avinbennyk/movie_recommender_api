# src/model.py
import pandas as pd
from surprise import SVD, Dataset, Reader
from sklearn.feature_extraction.text import TfidfVectorizer
import joblib

print("Training models...")

# --- Load Data ---
ratings = pd.read_csv('data/u.data', sep='\t', names=['user_id', 'item_id', 'rating', 'timestamp'])
movies = pd.read_csv(
    'data/u.item', sep='|', encoding='latin-1', header=None,
    names=['movie_id', 'title', 'release_date', 'video_release_date', 'imdb_url', 'unknown', 'Action', 'Adventure', 'Animation', 'Childrens', 'Comedy', 'Crime', 'Documentary', 'Drama', 'Fantasy', 'Film-Noir', 'Horror', 'Musical', 'Mystery', 'Romance', 'Sci-Fi', 'Thriller', 'War', 'Western']
)
movies['title'] = movies['title'].str.replace(r'\s*\(\d{4}\)$', '', regex=True)

# --- Collaborative Filtering Model (SVD) ---
reader = Reader(rating_scale=(1, 5))
data = Dataset.load_from_df(ratings[['user_id', 'item_id', 'rating']], reader)
trainset = data.build_full_trainset()
svd = SVD(n_factors=100, n_epochs=20, random_state=42)
svd.fit(trainset)
print("SVD model trained.")

# --- Content-Based Model (TF-IDF) ---
genre_cols = ['Action', 'Adventure', 'Animation', 'Childrens', 'Comedy', 'Crime', 'Documentary', 'Drama', 'Fantasy', 'Film-Noir', 'Horror', 'Musical', 'Mystery', 'Romance', 'Sci-Fi', 'Thriller', 'War', 'Western']
movies['genres'] = movies[genre_cols].apply(lambda row: ' '.join(row.index[row==1]), axis=1)
tfidf = TfidfVectorizer(stop_words='english')
tfidf_matrix = tfidf.fit_transform(movies['genres'])
print("TF-IDF matrix created.")

# --- Save all artifacts ---
joblib.dump(svd, 'src/svd_model.joblib')
joblib.dump(movies, 'src/movies_df.joblib') # Save movies dataframe for API use
joblib.dump(ratings, 'src/ratings_df.joblib') # Save ratings dataframe for API use
joblib.dump(tfidf_matrix, 'src/tfidf_matrix.joblib')
print("✅ All models and data saved successfully.")