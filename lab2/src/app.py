import streamlit as st
from psycopg2.extras import RealDictCursor
from passlib.hash import bcrypt
import psycopg2.pool
import atexit
from streamlit_option_menu import option_menu

from pages.login import show_login_page
from pages.register import show_register_page
from repositories.connector import get_connection
from psycopg2.extras import RealDictCursor

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
                #st.success("Регистрация кандидата прошла успешно!")
    except Exception as e:
        st.error(f"Ошибка: {e}")

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
                #st.success("Регистрация кандидата прошла успешно!")
    except Exception as e:
        st.error(f"Ошибка: {e}")


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
                if role == "candidate":
                    register_candidate(user_id, email, phone, show_phone)
                elif role == "employer":
                    register_employer(user_id, email, phone, show_phone)
                st.success("Регистрация прошла успешно!")
    except Exception as e:
        st.error(f"Ошибка: {e}")

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

def check_login_in_database(login, role):
    query = """
        SELECT user_id
        FROM {}
        WHERE phone = %s OR email = %s
    """.format("Candidates" if role == "candidate" else "Employers")

    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (login, login))
            result = cursor.fetchone()
            return result['user_id'] if result else None

def main():
    if 'role' in st.session_state and st.session_state.role == "candidate" and 'username' in st.session_state:
        st.page_link("pages/edit_candidate_data.py", label="Изменить данные аккаунта")
        st.page_link("pages/edit_resume.py", label="Ваше резюме")
        st.page_link("pages/view_resumes.py", label="Посмотреть другие резюме")
    else:
        #print("DB_CONFIG:", DB_CONFIG)
        st.title("Вход и регистрация")



        with st.container():
            role = option_menu(
                menu_title=None,
                options=["Ищу работу", "Ищу сотрудников"],
                icons=["briefcase", "people"],
                menu_icon="cast",
                default_index=0,
                orientation="horizontal",
                styles={
                    "container": {"text-align": "center"},
                    "nav-link": {"font-size": "16px", "margin": "0px"},
                    "nav-link-selected": {"background-color": "#00cc96"},
                },
            )
        
        if st.button("Или зайти как администратор", type="tertiary"):
            role = "admin"
        elif role == "Ищу работу":
            role = "candidate"
        else:
            role = "employer"
        st.session_state.role = role
        login = st.text_input("Телефон или email", key="login")
        if role == "admin":
            st.session_state.page = "login"
        elif st.button("Продолжить"):
            user_id = check_login_in_database(login, role)
            if user_id:
                st.session_state.user_id = user_id
                st.session_state.page = "login"
                #st.success(f"Пользователь найден: user_id = {user_id}")
            else:
                st.session_state.page = "register"
                #st.warning("Пользователь не найден")
        if st.session_state.get("page") == "register":
            st.switch_page("pages/register.py")
        elif st.session_state.get("page") == "login":
            #show_login_page()
            st.switch_page("pages/login.py")


if __name__ == "__main__":
    main()
