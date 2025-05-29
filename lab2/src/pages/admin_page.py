import streamlit as st
from repositories.connector import get_connection
from psycopg2.extras import RealDictCursor
from services.edit_session_data import get_session_data, ensure_token


def add_profession(profession_name):
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            try:
                cursor.execute(
                    "INSERT INTO Professions (profession_name) VALUES (%s) ON CONFLICT (profession_name) DO NOTHING;",
                    (profession_name,)
                )
                connection.commit()
                st.success(f"Добавлено успешно!")
            except Exception as e:
                st.error(f"Ошибка при добавлении специальности: {e}")

def show_admin_page():
    ensure_token()
    token = st.session_state.get('token')
    session_data = get_session_data(token)
    st.query_params.token = token
    
    if not session_data or session_data.get("role") != "admin":
        st.error("Вы не авторизованы для доступа к этой странице.")
        return

    st.title("Панель администратора")

    with st.form(key='add_profession_form'):
        st.header("Добавить новую специальность в базу данных")
        profession_name = st.text_input("Название специальности:")
        submit_button = st.form_submit_button("Добавить")
        if submit_button and profession_name:
            add_profession(profession_name)

if __name__ == "__main__":
    show_admin_page()
