# src/main.py
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import pandas as pd
from pydantic import BaseModel
import joblib
from sklearn.metrics.pairwise import linear_kernel

from .database import supabase

app = FastAPI(title="Movie Recommender API")

# --- Load ML Models & Data ---
svd = joblib.load('src/svd_model.joblib')
movies_df = joblib.load('src/movies_df.joblib')
ratings_df = joblib.load('src/ratings_df.joblib')
tfidf_matrix = joblib.load('src/tfidf_matrix.joblib')
# Create a mapping from movie_id to dataframe index
indices = pd.Series(movies_df.index, index=movies_df['movie_id'])

# --- Authentication ---
class UserCredentials(BaseModel):
    email: str
    password: str

# Define the security scheme
bearer_scheme = HTTPBearer()

# Dependency to get current user from token
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
# ... (register_user function remains the same as before)
def register_user(credentials: UserCredentials):
    """Registers a new user in the Supabase auth system."""
    try:
        res = supabase.auth.sign_up({
            "email": credentials.email,
            "password": credentials.password,
        })
        return {"message": "User registered successfully!", "user_id": res.user.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/auth/login", tags=["Authentication"])
# ... (login_user function remains the same as before)
def login_user(credentials: UserCredentials):
    """Logs in a user and returns a session token."""
    try:
        res = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password,
        })
        return {
            "message": "Login successful!",
            "access_token": res.session.access_token,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/recommendations", tags=["Recommendations"])
def get_recommendations(current_user: dict = Depends(get_current_user)):
    """
    Get personalized movie recommendations for the logged-in user.
    This is a simplified hybrid model.
    """
    # We need the user's ID from the original dataset, not the Supabase UUID
    # In a real app, you would link these. For now, we'll simulate by using a fixed user ID.
    user_id_sim = 196 # Simulate recommendations for user 196

    # --- Candidate Generation (SVD) ---
    unrated_movie_ids = movies_df[~movies_df['movie_id'].isin(ratings_df[ratings_df['user_id'] == user_id_sim]['item_id'])]['movie_id']
    predictions = [svd.predict(user_id_sim, movie_id) for movie_id in unrated_movie_ids]
    predictions.sort(key=lambda x: x.est, reverse=True)
    top_svd_candidates = predictions[:50]

    # --- Re-ranking (Content-Based) ---
    user_high_ratings = ratings_df[(ratings_df['user_id'] == user_id_sim) & (ratings_df['rating'] >= 4)]
    if user_high_ratings.empty:
        # Cold start: Fallback to SVD if user has no high ratings
        top_n_movie_ids = [pred.iid for pred in top_svd_candidates[:10]]
    else:
        user_profile_indices = [indices[mid] for mid in user_high_ratings['item_id']]
        user_profile = tfidf_matrix[user_profile_indices].mean(axis=0)
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