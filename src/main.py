# src/main.py
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import joblib
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import linear_kernel
from sqlalchemy import text
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from .database import supabase, engine

app = FastAPI(title="Movie Recommender API")

# --- Load ML Models & Data ---
svd = joblib.load('src/svd_model.joblib')
movies_df = joblib.load('src/movies_df.joblib')
ratings_df = joblib.load('src/ratings_df.joblib')
tfidf_matrix = joblib.load('src/tfidf_matrix.joblib')
indices = pd.Series(movies_df.index, index=movies_df['movie_id'])

# Initialize Sentiment Analyzer
sentiment_analyzer = SentimentIntensityAnalyzer()

# --- Pydantic Models ---
class UserCredentials(BaseModel):
    email: str
    password: str

class ReviewCreate(BaseModel):
    movie_id: int
    rating: int
    review_text: Optional[str] = None

# --- Authentication ---
bearer_scheme = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        token = credentials.credentials
        user_res = supabase.auth.get_user(token)
        return user_res.user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

# --- API Endpoints ---
@app.get("/")
def read_root():
    return {"message": "Welcome to the Movie Recommender API"}

@app.post("/auth/register", tags=["Authentication"])
def register_user(credentials: UserCredentials):
    try:
        res = supabase.auth.sign_up({"email": credentials.email, "password": credentials.password})
        return {"message": "User registered successfully!", "user_id": res.user.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/login", tags=["Authentication"])
def login_user(credentials: UserCredentials):
    try:
        res = supabase.auth.sign_in_with_password({"email": credentials.email, "password": credentials.password})
        return {"message": "Login successful!", "access_token": res.session.access_token}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/reviews", tags=["Reviews"])
def create_review(review: ReviewCreate, current_user: dict = Depends(get_current_user)):
    """Create a new review for a movie."""
    sentiment = "neutral"
    if review.review_text:
        sentiment_scores = sentiment_analyzer.polarity_scores(review.review_text)
        if sentiment_scores['compound'] >= 0.05:
            sentiment = "positive"
        elif sentiment_scores['compound'] <= -0.05:
            sentiment = "negative"

    query = text(
        "INSERT INTO reviews (user_id, movie_id, rating, review_text, sentiment) "
        "VALUES (:user_id, :movie_id, :rating, :review_text, :sentiment)"
    )
    params = {
        "user_id": current_user.id,
        "movie_id": review.movie_id,
        "rating": review.rating,
        "review_text": review.review_text,
        "sentiment": sentiment
    }
    try:
        with engine.connect() as connection:
            connection.execute(query, params)
            connection.commit() # Important: commit the transaction
        return {"message": "Review created successfully", "sentiment": sentiment}
    except Exception as e:
        # Handles errors like duplicate reviews from the same user
        raise HTTPException(status_code=400, detail=f"Error creating review: {e}")

# ... (all other endpoints like /recommendations and /movies remain the same) ...
@app.get("/recommendations", tags=["Recommendations"])
def get_recommendations(current_user: dict = Depends(get_current_user)):
    user_id_sim = 196
    unrated_movie_ids = movies_df[~movies_df['movie_id'].isin(ratings_df[ratings_df['user_id'] == user_id_sim]['item_id'])]['movie_id']
    predictions = [svd.predict(user_id_sim, movie_id) for movie_id in unrated_movie_ids]
    predictions.sort(key=lambda x: x.est, reverse=True)
    top_svd_candidates = predictions[:50]
    user_high_ratings = ratings_df[(ratings_df['user_id'] == user_id_sim) & (ratings_df['rating'] >= 4)]
    if user_high_ratings.empty:
        top_n_movie_ids = [pred.iid for pred in top_svd_candidates[:10]]
    else:
        user_profile_indices = [indices[mid] for mid in user_high_ratings['item_id']]
        user_profile_matrix = tfidf_matrix[user_profile_indices].mean(axis=0)
        user_profile = np.asarray(user_profile_matrix)
        candidate_scores = {}
        for pred in top_svd_candidates:
            candidate_index = indices[pred.iid]
            content_sim = linear_kernel(user_profile, tfidf_matrix[candidate_index]).flatten()[0]
            hybrid_score = pred.est * 0.5 + content_sim * 0.5
            candidate_scores[pred.iid] = hybrid_score
        reranked_candidates = sorted(candidate_scores.items(), key=lambda item: item[1], reverse=True)
        top_n_movie_ids = [mid for mid, score in reranked_candidates[:10]]
    recommended_titles = movies_df[movies_df['movie_id'].isin(top_n_movie_ids)]['title'].tolist()
    return {"recommendations": recommended_titles}

@app.get("/movies/", tags=["Movies"])
def search_movies(title: Optional[str] = None, genre: Optional[str] = None):
    with engine.connect() as connection:
        query = "SELECT movie_id, title, genres FROM movies"
        conditions = []
        params = {}
        if title:
            conditions.append("title ILIKE :title")
            params["title"] = f"%{title}%"
        if genre:
            conditions.append("genres ILIKE :genre")
            params["genre"] = f"%{genre}%"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        result = connection.execute(text(query), params)
        movies = result.fetchall()
        return [{"movie_id": m[0], "title": m[1], "genres": m[2]} for m in movies]

@app.get("/movies/{movie_id}/similar", tags=["Movies"])
def get_similar_movies(movie_id: int):
    try:
        idx = indices[movie_id]
        sim_scores = list(enumerate(linear_kernel(tfidf_matrix[idx], tfidf_matrix).flatten()))
        sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
        sim_scores = sim_scores[1:11]
        movie_indices = [i[0] for i in sim_scores]
        similar_movies = movies_df['title'].iloc[movie_indices].tolist()
        return {"similar_movies": similar_movies}
    except KeyError:
        raise HTTPException(status_code=404, detail="Movie not found")