import streamlit as st
from repositories.connector import get_connection
from psycopg2.extras import RealDictCursor
from streamlit_tags import st_tags
from services.edit_resume_service import get_professions
from services.edit_session_data import get_session_data, ensure_token
from services.cache_service import (
    get_or_set_resumes_cache,
    check_if_liked,
    add_liked_resume_to_cache,
    start_cache_invalidation_listener
)

from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=500, key="datarefresh")

# Запуск слушателя pub/sub
start_cache_invalidation_listener()


# --- Навыки ---
def fetch_skills():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT skill_name FROM Skills")
                return [row[0] for row in cur.fetchall()]
    except Exception as e:
        raise Exception(f"Ошибка при получении навыков: {e}")


# --- Получение резюме из БД ---
def fetch_resumes(filters, sort_by):
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                SELECT r.*, 
                       p.profession_name, 
                       array_agg(DISTINCT s.skill_name) FILTER (WHERE s.skill_name IS NOT NULL) AS skills,
                       array_agg(DISTINCT we.position) FILTER (WHERE we.position IS NOT NULL) AS positions
                FROM Resumes r
                JOIN Professions p ON r.profession_id = p.profession_id
                LEFT JOIN ResumeSkills rs ON r.resume_id = rs.resume_id
                LEFT JOIN Skills s ON rs.skill_id = s.skill_id
                LEFT JOIN WorkExperience we ON r.user_id = we.candidate_id
                """
                where_clauses, values = [], []

                if filters.get('age_min') is not None:
                    where_clauses.append("r.age >= %s")
                    values.append(filters['age_min'])
                if filters.get('age_max') is not None:
                    where_clauses.append("r.age <= %s")
                    values.append(filters['age_max'])
                if filters.get('experience_min') is not None:
                    where_clauses.append("r.experience >= %s")
                    values.append(filters['experience_min'])
                if filters.get('experience_max') is not None:
                    where_clauses.append("r.experience <= %s")
                    values.append(filters['experience_max'])
                if filters.get('profession'):
                    where_clauses.append("p.profession_name = %s")
                    values.append(filters['profession'])
                if filters.get('employment_type'):
                    where_clauses.append("r.employment_type = %s")
                    values.append(filters['employment_type'])

                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)

                if sort_by == "Возраст":
                    query += " ORDER BY r.age"
                elif sort_by == "Опыт работы":
                    query += " ORDER BY r.experience"

                query += " GROUP BY r.resume_id, p.profession_name;"

                cur.execute(query, values)
                return cur.fetchall()
    except Exception as e:
        st.error(f"Ошибка при получении резюме: {e}")
        return []


# --- Получение лайков из БД ---
def fetch_likes_from_db(employer_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM LikedResumes WHERE employer_id = %s", (employer_id,))
            return [str(row[0]) for row in cur.fetchall()]


# --- Добавление лайка в БД ---
def add_liked_resume(candidate_id, employer_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO LikedResumes (user_id, employer_id, liked_date)
                VALUES (%s, %s, CURRENT_DATE)
            """, (candidate_id, employer_id))
            conn.commit()
    add_liked_resume_to_cache(candidate_id, employer_id)


# --- Основная страница ---
def show_resumes_page():
    ensure_token()
    token = st.session_state.get('token')
    session_data = get_session_data(token)
    st.query_params.token = token

    #import datetime
    #st.write(f"Время последней перезагрузки: {datetime.datetime.now().strftime('%H:%M:%S')}")

    if session_data:
        if 'role' in session_data and session_data['role'] == "candidate" and 'username' in session_data:
            st.page_link("pages/edit_candidate_data.py", label="Изменить данные аккаунта")
            st.page_link("pages/edit_resume.py", label="Ваше резюме")
            st.page_link("pages/responded_employers.py", label="Посмотреть отклики на ваше резюме")
            st.page_link("pages/view_resumes.py", label="Посмотреть другие резюме")

        elif 'role' in session_data and session_data['role'] == "employer" and 'username' in session_data:
            st.page_link(f"pages/edit_employer_data.py", label="Изменить данные аккаунта")
            st.page_link(f"pages/liked_resumes.py", label="Понравившиеся резюме")
            st.page_link(f"pages/view_resumes.py", label="Посмотреть другие резюме")

    st.title("Поиск резюме онлайн")

    try:
        professions = get_professions()
        skill_suggestions = fetch_skills()
    except Exception as e:
        st.error(str(e))
        return

    st.sidebar.header("Фильтры")
    age_min = st.sidebar.number_input("Минимальный возраст", min_value=18, max_value=100, value=18)
    age_max = st.sidebar.number_input("Максимальный возраст", min_value=18, max_value=100, value=100)
    experience_min = st.sidebar.number_input("Минимальный опыт (лет)", min_value=0, value=0)
    experience_max = st.sidebar.number_input("Максимальный опыт (лет)", min_value=0, value=50)
    profession = st.sidebar.selectbox("Профессия", [""] + [p[1] for p in professions])
    employment_type = st.sidebar.selectbox("Тип занятости", [""] + ["Полная", "Частичная", "Проектная", "Стажировка", "Волонтёрская"])
    skills = st_tags(label="", text="Введите навыки и нажмите Enter", value=[], suggestions=skill_suggestions, key="skill_tags")
    sort_by = st.sidebar.selectbox("Сортировать по", ["", "Возраст", "Опыт работы"])

    filters = {
        "age_min": age_min,
        "age_max": age_max,
        "experience_min": experience_min,
        "experience_max": experience_max,
        "profession": profession or None,
        "employment_type": employment_type or None,
        "skills": skills or None
    }

    resumes = get_or_set_resumes_cache(filters, sort_by, fetch_resumes)
    if not resumes:
        st.warning("Резюме не найдены.")
        return

    for i, resume in enumerate(resumes):
        with st.container():
            st.markdown(f"### {resume['profession_name']}")
            st.markdown(f"**Дата редактирования:** {resume['last_modified']}")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Возраст:** {resume['age']}")
                st.markdown(f"**Опыт:** {resume['experience']} лет")
                st.markdown(f"**Удалёнка:** {'Да' if resume['remote_work_possible'] else 'Нет'}")
            with col2:
                st.markdown(f"**Город:** {resume['city']}")
                st.markdown(f"**Метро:** {resume['nearby_metro']}")
                st.markdown(f"**Занятость:** {resume['employment_type']}")
            st.markdown(f"**Навыки:** {', '.join(resume.get('skills') or []) or 'Нет'}")
            st.markdown(f"**Позиции:** {', '.join(resume.get('positions') or []) or 'Нет'}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Узнать подробнее", key=f"view_{i}"):
                    st.session_state['selected_resume'] = resume
                    st.switch_page("pages/view_resume_details.py")
            with col2:
                if st.button("", icon=":material/library_add:", key=f"like_{i}"):
                    employer_id = session_data.get("user_id")
                    if not employer_id:
                        st.info("Только работодатели могут лайкать.")
                    else:
                        if check_if_liked(resume['user_id'], employer_id, fetch_likes_from_db):
                            st.info("Уже в понравившихся.")
                        else:
                            add_liked_resume(resume['user_id'], employer_id)
                            st.success("Добавлено в понравившиеся!")

            st.markdown("---")


if __name__ == "__main__":
    show_resumes_page()
