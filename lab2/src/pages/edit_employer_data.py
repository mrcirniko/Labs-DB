import streamlit as st
from repositories.connector import get_connection
from psycopg2.extras import RealDictCursor
from passlib.hash import bcrypt
from services.edit_session_data import get_session_data, ensure_token, update_session_in_redis


def update_employer_data(user_id, username=None, email=None, phone=None, password=None, show_phone=None,
                         company_name=None, company_description=None):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            if username:
                cursor.execute(
                    """
                    UPDATE Users
                    SET username = %s
                    WHERE user_id = %s
                    """,
                    (username, user_id)
                )

            if password:
                password_hash = bcrypt.hash(password)
                cursor.execute(
                    """
                    UPDATE Users
                    SET password_hash = %s
                    WHERE user_id = %s
                    """,
                    (password_hash, user_id)
                )

            updates = []
            params = []

            if email:
                updates.append("email = %s")
                params.append(email)
            if phone:
                updates.append("phone = %s")
                params.append(phone)
            if show_phone is not None:
                updates.append("show_phone = %s")
                params.append(show_phone)
            if company_name:
                updates.append("company_name = %s")
                params.append(company_name)
            if company_description:
                updates.append("company_description = %s")
                params.append(company_description)

            if updates:
                params.append(user_id)
                cursor.execute(
                    f"""
                    UPDATE Employers
                    SET {', '.join(updates)}
                    WHERE user_id = %s
                    """,
                    params
                )

            connection.commit()


def get_employer_data(user_id):
    query = """
        SELECT u.username, e.email, e.phone, e.show_phone,
               e.company_name, e.company_description
        FROM Users u
        JOIN Employers e ON u.user_id = e.user_id
        WHERE u.user_id = %s
    """

    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (user_id,))
            return cursor.fetchone()


def show_edit_employer_page():
    ensure_token()
    token = st.session_state.get('token')
    session_data = get_session_data(token)
    st.query_params.token = token

    if not token:
        st.error("Вы не авторизованы.")
        return

    user_id = session_data.get("user_id")
    if not user_id:
        st.error("Вы не авторизованы.")
        return

    st.page_link("pages/edit_employer_data.py", label="Изменить данные аккаунта")
    st.page_link("pages/liked_resumes.py", label="Понравившиеся резюме")
    st.page_link("pages/view_resumes.py", label="Посмотреть другие резюме")

    st.title("Редактировать данные профиля")



    employer_data = get_employer_data(user_id)
    if not employer_data:
        st.error("Не удалось загрузить данные пользователя.")
        return

    username = st.text_input("Имя пользователя", employer_data["username"])
    email = st.text_input("Email", employer_data["email"])
    phone = st.text_input("Телефон", employer_data["phone"])
    show_phone = st.checkbox("Показывать телефон", employer_data["show_phone"])
    company_name = st.text_input("Название компании", employer_data.get("company_name", ""))
    company_description = st.text_area("Краткое описание компании", employer_data.get("company_description", ""))
    password = st.text_input("Новый пароль (если нужно изменить)", type="password")

    if st.button("Сохранить изменения"):
        try:
            update_employer_data(
                user_id,
                username=username if username != employer_data["username"] else None,
                email=email if email != employer_data["email"] else None,
                phone=phone if phone != employer_data["phone"] else None,
                password=password if password else None,
                show_phone=show_phone if show_phone != employer_data["show_phone"] else None,
                company_name=company_name if company_name != employer_data.get("company_name", "") else None,
                company_description=company_description if company_description != employer_data.get("company_description", "") else None,
            )
            st.success("Данные успешно обновлены!")
        except Exception as e:
            st.error(f"Ошибка при обновлении данных: {e}")


if __name__ == "__main__":
    show_edit_employer_page()
