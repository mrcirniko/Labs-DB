import streamlit as st
from psycopg2.extras import RealDictCursor
from repositories.connector import get_connection
from services.edit_session_data import get_session_data, ensure_token

def get_responded_employers(candidate_id):
    query = """
        SELECT e.user_id AS employer_id,
               u.username AS employer_username,
               e.email,
               e.phone,
               e.show_phone,
               e.company_name,
               e.company_description,
               lr.liked_date
        FROM LikedResumes lr
        JOIN Employers e ON lr.employer_id = e.user_id
        JOIN Users u ON e.user_id = u.user_id
        WHERE lr.user_id = %s
        ORDER BY lr.liked_date DESC;
    """
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (candidate_id,))
                return cur.fetchall()
    except Exception as e:
        st.error(f"Ошибка при получении откликнувшихся работодателей: {e}")
        return []


def show_responded_employers_page():
    ensure_token()
    token = st.session_state.get("token")
    session_data = get_session_data(token)
    st.query_params.token = token

    if not token or 'user_id' not in session_data:
        st.error("Необходимо авторизоваться")
        return

    st.page_link("pages/edit_candidate_data.py", label="Изменить данные аккаунта")
    st.page_link("pages/edit_resume.py", label="Ваше резюме")
    st.page_link("pages/responded_employers.py", label="Посмотреть отклики на ваше резюме")
    st.page_link("pages/view_resumes.py", label="Посмотреть другие резюме")

    st.title("Работодатели, откликнувшиеся на ваше резюме")

    candidate_id = session_data.get("user_id")
    if not candidate_id or session_data.get("role") != "candidate":
        st.warning("Только кандидаты могут просматривать откликнувшихся работодателей.")
        return

    employers = get_responded_employers(candidate_id)

    if not employers:
        st.info("Пока ни один работодатель не откликнулся на ваше резюме.")
        return

    for employer in employers:
        with st.container():
            st.subheader(employer["company_name"] or employer["employer_username"])
            st.markdown(f"**Дата отклика:** {employer['liked_date']}")
            if employer["company_description"]:
                st.markdown(f"**Описание компании:** {employer['company_description']}")
            if employer["show_phone"] and employer["phone"]:
                st.markdown(f"**Телефон:** {employer['phone']}")
            st.markdown(f"**Email:** {employer['email']}")
            st.markdown("---")

if __name__ == "__main__":
    show_responded_employers_page()
