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
# (This section remains the same)
svd = joblib.load('src/svd_model.joblib')
movies_df = joblib.load('src/movies_df.joblib')
ratings_df = joblib.load('src/ratings_df.joblib')
tfidf_matrix = joblib.load('src/tfidf_matrix.joblib')
indices = pd.Series(movies_df.index, index=movies_df['movie_id'])
sentiment_analyzer = SentimentIntensityAnalyzer()

# --- Pydantic Models ---
class UserCredentials(BaseModel):
    email: str
    password: str

class ReviewCreate(BaseModel):
    movie_id: int
    rating: int
    review_text: Optional[str] = None

class ReviewUpdate(BaseModel): # New model for updating
    rating: int
    review_text: Optional[str] = None

# --- Authentication ---
# (This section remains the same)
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

# (Authentication endpoints remain the same)
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

# (Review creation endpoint remains the same)
@app.post("/reviews", tags=["Reviews"])
def create_review(review: ReviewCreate, current_user: dict = Depends(get_current_user)):
    sentiment = "neutral"
    if review.review_text:
        sentiment_scores = sentiment_analyzer.polarity_scores(review.review_text)
        if sentiment_scores['compound'] >= 0.05:
            sentiment = "positive"
        elif sentiment_scores['compound'] <= -0.05:
            sentiment = "negative"
    query = text("INSERT INTO reviews (user_id, movie_id, rating, review_text, sentiment) VALUES (:user_id, :movie_id, :rating, :review_text, :sentiment)")
    params = {"user_id": current_user.id, "movie_id": review.movie_id, "rating": review.rating, "review_text": review.review_text, "sentiment": sentiment}
    try:
        with engine.connect() as connection:
            connection.execute(query, params)
            connection.commit()
        return {"message": "Review created successfully", "sentiment": sentiment}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating review: {e}")

# --- NEW ENDPOINTS ---

@app.get("/reviews/me", tags=["Reviews"])
def get_my_reviews(current_user: dict = Depends(get_current_user)):
    """Fetches all reviews for the currently logged-in user."""
    query = text(
        "SELECT r.review_id, r.rating, r.review_text, r.sentiment, r.created_at, m.title "
        "FROM reviews r JOIN movies m ON r.movie_id = m.movie_id "
        "WHERE r.user_id = :user_id ORDER BY r.created_at DESC"
    )
    with engine.connect() as connection:
        result = connection.execute(query, {"user_id": current_user.id})
        reviews = result.fetchall()
        return [dict(row._mapping) for row in reviews]

@app.put("/reviews/{review_id}", tags=["Reviews"])
def update_review(review_id: int, review_update: ReviewUpdate, current_user: dict = Depends(get_current_user)):
    """Updates a user's own review."""
    with engine.connect() as connection:
        # Security Check: First, verify the review belongs to the current user
        owner_check_query = text("SELECT user_id FROM reviews WHERE review_id = :review_id")
        owner_result = connection.execute(owner_check_query, {"review_id": review_id}).fetchone()
        
        if not owner_result:
            raise HTTPException(status_code=404, detail="Review not found")
        if str(owner_result[0]) != str(current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized to update this review")

        # If check passes, proceed with update
        sentiment = "neutral"
        if review_update.review_text:
            sentiment_scores = sentiment_analyzer.polarity_scores(review_update.review_text)
            if sentiment_scores['compound'] >= 0.05:
                sentiment = "positive"
            elif sentiment_scores['compound'] <= -0.05:
                sentiment = "negative"

        update_query = text(
            "UPDATE reviews SET rating = :rating, review_text = :review_text, sentiment = :sentiment "
            "WHERE review_id = :review_id"
        )
        params = {
            "rating": review_update.rating,
            "review_text": review_update.review_text,
            "sentiment": sentiment,
            "review_id": review_id
        }
        connection.execute(update_query, params)
        connection.commit()
        return {"message": "Review updated successfully"}


# (Existing movie endpoints remain the same)
# ... /recommendations, /movies, /movies/{movie_id}/similar endpoints go here ...
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
    
    # Add this endpoint to src/main.py
@app.get("/users/me", tags=["Users"])
def get_user_info(current_user: dict = Depends(get_current_user)):
    """Gets information for the currently logged-in user."""
    return {"id": current_user.id, "email": current_user.email}