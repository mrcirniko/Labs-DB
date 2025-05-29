import streamlit as st
from psycopg2.extras import RealDictCursor
from passlib.hash import bcrypt
from repositories.connector import get_connection
from services.edit_session_data import store_session_in_redis
from pages.edit_resume import show_edit_resume_page
import redis
import uuid
import json
import time
import os
from dotenv import load_dotenv

def authenticate_user(username, password):
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM Users WHERE username = %s", (username,))
                user = cur.fetchone()
                if user and bcrypt.verify(password, user['password_hash']):
                    return user
                else:
                    return None 
    except Exception as e:
        st.error(f"Ошибка: {e}")

def show_login_page():
    #role = st.session_state.get("role")
    st.subheader("Авторизация пользователя")
    username = st.text_input("Логин")
    password = st.text_input("Пароль", type="password")
    st.session_state.username = username
    if st.button("Войти"):
        user = authenticate_user(username, password)
        if user:
            token = store_session_in_redis(user)
            st.session_state['token'] = token
            st.success(f"Добро пожаловать, {user['username']}!")
            
            if user['role'] == "candidate":
                st.session_state.page = "authenticate_candidate"
            elif user['role'] == "employer":
                st.session_state.page = "authenticate_employer"
            elif user['role'] == "admin":
                st.session_state.page = "authenticate_admin"
        else:
            st.error("Неправильный логин или пароль")
        if st.session_state.get("page") == "authenticate_candidate":
            st.switch_page("pages/edit_resume.py")
        elif st.session_state.get("page") == "authenticate_employer":
            st.switch_page("pages/view_resumes.py")
        elif st.session_state.get("page") == "authenticate_admin":
            st.switch_page("pages/admin_page.py")
if __name__ == "__main__":
    show_login_page()