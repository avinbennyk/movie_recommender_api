# src/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .database import supabase

app = FastAPI(title="Movie Recommender API")

class UserCredentials(BaseModel):
    email: str
    password: str

@app.get("/")
def read_root():
    return {"message": "Welcome to the Movie Recommender API"}

@app.post("/auth/register", tags=["Authentication"])
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