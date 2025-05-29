import streamlit as st
from pages.create_resume import show_create_resume_page
from psycopg2.extras import RealDictCursor
from passlib.hash import bcrypt
from repositories.connector import get_connection
import redis
import uuid
import json
import time
from services.edit_session_data import store_session_in_redis

def register_candidate(user_id, email, phone, show_phone):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO Candidates (user_id, email, phone, show_phone)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (user_id, email, phone, show_phone)
                )
                conn.commit()
    except Exception as e:
        st.error(f"Ошибка регистрации кандидата: {e}")

def register_employer(user_id, email, phone, show_phone):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO Employers (user_id, email, phone, show_phone)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (user_id, email, phone, show_phone)
                )
                conn.commit()
    except Exception as e:
        st.error(f"Ошибка регистрации работодателя: {e}")

def register_user(username, password, role, email, phone, show_phone):
    password_hash = bcrypt.hash(password)
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO Users (username, password_hash, role)
                    VALUES (%s, %s, %s)
                    RETURNING user_id
                    """,
                    (username, password_hash, role)
                )
                user_id = cur.fetchone()[0]
                conn.commit()

                # Регистрация роли
                if role == "candidate":
                    register_candidate(user_id, email, phone, show_phone)
                elif role == "employer":
                    register_employer(user_id, email, phone, show_phone)

                user_data = {
                    "user_id": user_id,
                    "username": username,
                    "role": role
                }
                token = store_session_in_redis(user_data)


                st.session_state['token'] = token

                st.success("Регистрация прошла успешно!")

                if role == "candidate":
                    st.switch_page("pages/create_resume.py")
                elif role == "employer":
                    st.switch_page("pages/view_resumes.py")
    except Exception as e:
        st.error(f"Ошибка регистрации: {e}")

def show_register_page():
    role = st.session_state.get("role")
    st.subheader("Регистрация пользователя")
    username = st.text_input("Логин")
    email = st.text_input("Email")
    phone = st.text_input("Телефон")
    show_phone = st.checkbox("Показывать телефон")
    password = st.text_input("Пароль", type="password")
    password_confirm = st.text_input("Подтвердите пароль", type="password")

    if st.button("Зарегистрироваться"):
        if not (username and password and password_confirm and role):
            st.warning("Заполните все поля!")
        elif password != password_confirm:
            st.error("Пароли не совпадают!")
        else:
            register_user(username, password, role, email, phone, show_phone)

if __name__ == "__main__":
    show_register_page()
