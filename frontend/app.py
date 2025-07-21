# frontend/app.py
import streamlit as st
import requests
from streamlit_cookies_manager import EncryptedCookieManager
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(layout="wide")
API_URL = "http://127.0.0.1:8000"
# This should be a secret key from your environment variables in a real app
cookies = EncryptedCookieManager(password="a_very_secret_password_12345")

# --- SESSION STATE INITIALIZATION ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'access_token' not in st.session_state:
    st.session_state['access_token'] = ""
if 'user_email' not in st.session_state:
    st.session_state['user_email'] = ""

# --- VIEWS (Functions for each "page") ---

def login_view():
    # (This function remains the same)
    st.header("Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log In")
        if submitted:
            res = requests.post(f"{API_URL}/auth/login", json={"email": email, "password": password})
            if res.status_code == 200:
                token = res.json().get('access_token')
                st.session_state['access_token'] = token
                st.session_state['logged_in'] = True
                cookies['access_token'] = token
                # To get user email for display
                headers = {"Authorization": f"Bearer {token}"}
                user_res = requests.get(f"{API_URL}/users/me", headers=headers) # Assumes you have a /users/me endpoint
                if user_res.status_code == 200:
                    st.session_state.user_email = user_res.json().get('email')
                st.rerun()
            else:
                st.error(f"Login failed: {res.json().get('detail')}")
    if st.button("Don't have an account? Sign Up"):
        st.session_state.page = "signup"
        st.rerun()

def signup_view():
    # (This function remains the same)
    st.header("Register a New Account")
    with st.form("signup_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Register")
        if submitted:
            res = requests.post(f"{API_URL}/auth/register", json={"email": email, "password": password})
            if res.status_code == 200:
                st.success("Registration successful! Please log in.")
                st.session_state.page = "login"
                st.rerun()
            else:
                st.error(f"Registration failed: {res.json().get('detail')}")
    if st.button("Already have an account? Log In"):
        st.session_state.page = "login"
        st.rerun()

def home_view():
    # We will build out recommendations here later
    st.header(f"Welcome to CineRecs!")
    st.info("Navigate to 'My Reviews' to see and edit your reviews, or find a new movie to review!")

def my_reviews_view():
    st.header("My Past Reviews")
    headers = {"Authorization": f"Bearer {st.session_state['access_token']}"}
    
    # Fetch user's reviews from the API
    response = requests.get(f"{API_URL}/reviews/me", headers=headers)
    
    if response.status_code == 200:
        reviews = response.json()
        if not reviews:
            st.info("You haven't submitted any reviews yet. Find a movie and add one!")
        else:
            for review in reviews:
                with st.container(border=True):
                    st.subheader(review['title'])
                    st.write(f"**Your Rating:** {'⭐' * review['rating']}")
                    st.write(f"**Your Review:** {review['review_text']}")
                    st.caption(f"Sentiment: {review['sentiment']}")

                    # Form to update the review
                    with st.expander("Update this review"):
                        with st.form(key=f"update_form_{review['review_id']}", clear_on_submit=True):
                            new_rating = st.slider("New Rating", 1, 5, value=review['rating'])
                            new_text = st.text_area("New Review Text", value=review['review_text'])
                            submitted_update = st.form_submit_button("Submit Update")

                            if submitted_update:
                                update_data = {"rating": new_rating, "review_text": new_text}
                                update_res = requests.put(f"{API_URL}/reviews/{review['review_id']}", json=update_data, headers=headers)
                                if update_res.status_code == 200:
                                    st.success("Review updated successfully!")
                                    st.rerun() # Rerun to show the updated review
                                else:
                                    st.error(f"Update failed: {update_res.json().get('detail')}")

    else:
        st.error("Could not fetch your reviews.")


# --- MAIN APP LOGIC (The "Router") ---

# Check for login cookie
if not st.session_state.logged_in:
    token_from_cookie = cookies.get('access_token')
    if token_from_cookie:
        st.session_state.logged_in = True
        st.session_state.access_token = token_from_cookie

# Sidebar Navigation
with st.sidebar:
    st.header("Navigation")
    if st.session_state.logged_in:
        if st.button("Home"):
            st.session_state.page = "home"
            st.rerun()
        if st.button("My Reviews"):
            st.session_state.page = "my_reviews"
            st.rerun()
        if st.button("Logout"):
            cookies.delete('access_token')
            st.session_state.logged_in = False
            st.session_state.page = "login"
            st.rerun()
    else:
        st.info("Please log in or register.")

# Initialize page state
if 'page' not in st.session_state:
    st.session_state.page = 'login' if not st.session_state.logged_in else 'home'

# Display the current view
if st.session_state.logged_in:
    if st.session_state.page == "home":
        home_view()
    elif st.session_state.page == "my_reviews":
        my_reviews_view()
    else:
        home_view() # Default to home
else:
    if st.session_state.page == "signup":
        signup_view()
    else:
        login_view()