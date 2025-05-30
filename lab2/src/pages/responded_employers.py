import streamlit as st
from psycopg2.extras import RealDictCursor
from repositories.connector import get_connection
from services.edit_session_data import get_session_data, ensure_token

import redis
import os
import threading
import json
from dotenv import load_dotenv

from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=500, key="datarefresh")

# --- Redis PubSub слушатель likes_channel ---
def start_likes_channel_listener(candidate_id, on_new_like):
    load_dotenv("env.env")
    r = redis.Redis(host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), db=0, decode_responses=True)

    def listen():
        pubsub = r.pubsub()
        pubsub.subscribe('likes_channel')
        for message in pubsub.listen():
            if message['type'] == 'message':
                data = message['data']
                # Сообщение вида: liked:{candidate_id}:{employer_id}
                if data.startswith('liked:'):
                    parts = data.split(':')
                    if len(parts) == 3:
                        liked_candidate_id = parts[1]
                        if str(liked_candidate_id) == str(candidate_id):
                            # Новый отклик на ваше резюме!
                            on_new_like()
    thread = threading.Thread(target=listen, daemon=True)
    thread.start()

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

    if not token:
        st.error("Необходим токен для доступа к странице.")
        return

    session_data = get_session_data(token)
    if not session_data:
        st.error("Сессия недействительна или истекла. Пожалуйста, войдите заново.")
        return

    if 'user_id' not in session_data:
        st.error("Ошибка в данных сессии: отсутствует идентификатор пользователя.")
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

    # --- Функция обновления списка работодателей ---
    def rerun_on_new_like():
        st.session_state['employers_rerun'] = not st.session_state.get('employers_rerun', False)
        st.rerun()

    # --- Запускаем слушатель PubSub для likes_channel ---
    if "likes_listener_started" not in st.session_state:
        start_likes_channel_listener(candidate_id, rerun_on_new_like)
        st.session_state["likes_listener_started"] = True

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