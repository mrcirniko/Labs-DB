import streamlit as st
import redis
from psycopg2.extras import RealDictCursor
from repositories.connector import get_connection
from services.edit_session_data import get_session_data, ensure_token
from dotenv import load_dotenv
import os

load_dotenv("env.env")

REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)


# --- Redis: ключ для лайков (Set) ---
def get_redis_key(employer_id):
    return f"liked_resumes:{employer_id}"


# --- Получить список user_id лайков из Redis Set ---
def get_liked_resume_ids_from_cache(employer_id):
    redis_key = get_redis_key(employer_id)
    if r.exists(redis_key):
        return list(r.smembers(redis_key))
    return None


# --- Заполнить кеш Set лайков из базы ---
def fill_liked_resume_ids_cache(employer_id):
    query = "SELECT user_id FROM LikedResumes WHERE employer_id = %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (employer_id,))
            rows = cur.fetchall()
            liked_ids = [str(row[0]) for row in rows]
            if liked_ids:
                redis_key = get_redis_key(employer_id)
                r.delete(redis_key)  # на всякий случай очистим
                r.sadd(redis_key, *liked_ids)
            return liked_ids


# --- Получить лайки (полные данные резюме) по user_id ---
def get_liked_resumes_from_db_by_ids(user_ids):
    if not user_ids:
        return []

    # Приводим к int, игнорируя нечисловые
    user_ids = [int(uid) for uid in user_ids if str(uid).isdigit()]

    if not user_ids:
        return []

    query = """
        SELECT lr.liked_date, rs.resume_id, rs.user_id, rs.last_modified, rs.age, rs.experience, rs.city, 
               rs.nearby_metro, rs.employment_type, rs.remote_work_possible, rs.profession_name,
               rs.skills, rs.description, u.username AS candidate_username
        FROM LikedResumes lr
        JOIN ResumeSearch rs ON lr.user_id = rs.user_id
        JOIN Users u ON rs.user_id = u.user_id
        WHERE lr.user_id = ANY(%s)
        ORDER BY lr.liked_date DESC;
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (user_ids,))
            return cur.fetchall()



# --- Основная функция получения лайков с кешированием через Set ---
def get_liked_resumes(employer_id):
    liked_ids = get_liked_resume_ids_from_cache(employer_id)
    if liked_ids is None:
        liked_ids = fill_liked_resume_ids_cache(employer_id)

    try:
        resumes = get_liked_resumes_from_db_by_ids(liked_ids)
        return resumes
    except Exception as e:
        st.error(f"Ошибка при получении понравившихся резюме: {e}")
        return []


# --- Удаление лайка и обновление кеша (удаляем из Set) ---
def remove_from_liked(employer_id, user_id):
    query = """
        DELETE FROM LikedResumes
        WHERE employer_id = %s AND user_id = %s;
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (employer_id, user_id))
                conn.commit()

        redis_key = get_redis_key(employer_id)
        r.srem(redis_key, str(user_id))

        st.success("Резюме удалено из понравившихся.")
    except Exception as e:
        st.error(f"Не удалось удалить резюме: {e}")


# --- Основная страница ---
def show_liked_resumes_page():
    ensure_token()
    token = st.session_state.get('token')
    session_data = get_session_data(token)
    st.query_params.token = token

    st.title("Понравившиеся резюме")

    if not token or session_data.get("role") != "employer":
        st.warning("Только работодатели могут просматривать понравившиеся резюме.")
        return

    # Навигация
    st.page_link("pages/edit_employer_data.py", label="Изменить данные аккаунта")
    st.page_link("pages/liked_resumes.py", label="Понравившиеся резюме")
    st.page_link("pages/view_resumes.py", label="Посмотреть другие резюме")

    employer_id = session_data.get("user_id")
    liked_resumes = get_liked_resumes(employer_id)

    if not liked_resumes:
        st.info("У вас пока нет понравившихся резюме.")
        return

    for i, resume in enumerate(liked_resumes):
        with st.container():
            st.markdown(f"### {resume['profession_name']}")
            st.markdown(f"**Дата добавления в понравившиеся:** {resume['liked_date']}")
            st.markdown(f"**Возраст:** {resume['age']} | **Опыт:** {resume['experience']} лет")
            st.markdown(f"**Город:** {resume['city']} | **Метро:** {resume['nearby_metro']}")
            st.markdown(f"**Тип занятости:** {resume['employment_type']} | **Удаленная работа:** {'Да' if resume['remote_work_possible'] else 'Нет'}")
            st.markdown(f"**Последнее изменение резюме:** {resume['last_modified']}")
            st.markdown(f"**Описание:** {resume['description']}")

            skills = resume.get('skills', [])
            if skills:
                st.markdown(f"**Навыки:** {', '.join(skills)}")
            else:
                st.markdown("**Навыки:** Не указаны")

            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("Узнать подробнее", key=f"view_{i}"):
                    session_data['selected_resume'] = resume
                    st.switch_page("pages/view_resume_details.py")
            with col2:
                if st.button("Удалить из понравившихся", key=f"del_{i}"):
                    remove_from_liked(employer_id, resume['user_id'])
                    st.rerun()

            st.markdown("---")


if __name__ == "__main__":
    show_liked_resumes_page()
