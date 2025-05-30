import streamlit as st
from repositories.connector import get_connection
from psycopg2.extras import RealDictCursor
from services.edit_resume_service import add_resume_to_db, add_work_experience_to_db, add_skills_to_db, get_professions, get_resume_by_user, update_resume_in_db
from services.edit_session_data import get_session_data, ensure_token, update_session_in_redis

import queue
import os
import time
import redis
from dotenv import load_dotenv

import json
from services.edit_resume_service import get_resume_by_user

load_dotenv("env.env")
r = redis.Redis(host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), db=0, decode_responses=True)


def invalidate_resumes_cache():
    """
    Инвалидировать кеш с результатами поиска резюме.
    Можно удалить все ключи с префиксом resumes: (фильтры), чтобы при следующем запросе обновились данные.
    """
    try:
        keys = r.keys("resumes:*")
        if keys:
            r.delete(*keys)
            print(f"[CACHE INVALIDATE] Deleted keys: {keys}")
    except Exception as e:
        print(f"Ошибка при инвалидировании кеша: {e}")


def update_resume_cache(user_id):
    """Обновляет кеш резюме конкретного пользователя"""
    try:
        updated_resume = get_resume_by_user(user_id)
        if updated_resume:
            r.set(f"resumes:user_{user_id}", json.dumps(updated_resume), ex=600)  # кеш на 10 минут
    except Exception as e:
        print(f"Ошибка при обновлении кеша резюме пользователя {user_id}: {e}")


like_notifications_queue = queue.Queue()

def listen_for_likes(candidate_id):
    pubsub = r.pubsub()
    pubsub.subscribe('likes_channel')

    for message in pubsub.listen():
        if message['type'] == 'message':
            #data = message['data'].decode('utf-8')
            data = message['data']
            parts = data.split(':')
            if len(parts) == 3 and parts[0] == 'liked':
                liked_candidate_id = parts[1]
                if liked_candidate_id == str(candidate_id):
                    employer_id = parts[2]
                    like_notifications_queue.put(employer_id)


def show_edit_resume_page():
    ensure_token()
    token = st.session_state.get('token')
    session_data = get_session_data(token)
    st.query_params.token = token

    user_id = session_data['user_id']

    if 'like_listener_thread' not in st.session_state:
        import threading
        thread = threading.Thread(target=listen_for_likes, args=(user_id,), daemon=True)
        thread.start()
        st.session_state['like_listener_thread'] = thread

    # Проверяем очередь уведомлений
    while not like_notifications_queue.empty():
        employer_id = like_notifications_queue.get_nowait()
        st.toast(f"Ваше резюме понравилось работодателю с ID: {employer_id}!")

    if not token or 'user_id' not in session_data:
        st.error("Необходимо авторизоваться")
        return

    st.page_link("pages/edit_candidate_data.py", label="Изменить данные аккаунта")
    st.page_link("pages/edit_resume.py", label="Ваше резюме")
    st.page_link("pages/responded_employers.py", label="Посмотреть отклики на ваше резюме")
    st.page_link("pages/view_resumes.py", label="Посмотреть другие резюме")

    st.title("Редактировать резюме")
    
    with st.form("edit_form"):
        user_id = session_data['user_id']

        try:
            resume = get_resume_by_user(user_id)
            if not resume:
                st.warning("Резюме не найдено. Вы можете создать новое резюме.")
                st.switch_page("pages/create_resume.py")
        except Exception as e:
            st.error(f"Ошибка при загрузке резюме: {e}")
            return

        profession_id = resume.get('profession_id')
        age = resume.get('age')
        experience = resume.get('experience')
        city = resume.get('city')
        nearby_metro = resume.get('nearby_metro')
        employment_type = resume.get('employment_type')
        description = resume.get('description')
        remote_work_possible = resume.get('remote_work_possible')

        st.subheader("Текущие данные резюме")

        professions = get_professions()
        profession_options = [profession[1] for profession in professions]
        current_profession = next((p[1] for p in professions if p[0] == profession_id), None)

        new_profession = st.selectbox(
            "Специальность",
            profession_options,
            index=profession_options.index(current_profession) if current_profession else 0
        )
        new_profession_id = next((p[0] for p in professions if p[1] == new_profession), profession_id)

        new_age = st.number_input("Возраст", min_value=18, max_value=100, value=age or 18)
        new_experience = st.number_input("Опыт работы (в годах)", min_value=0, value=experience or 0)
        new_city = st.text_input("Город проживания", value=city or "")
        new_nearby_metro = st.text_input("Ближайшее метро", value=nearby_metro or "")
        new_employment_type = st.selectbox(
            "Тип занятости",
            ["Полная", "Частичная", "Проектная", "Стажировка", "Волонтёрская"],
            index=["Полная", "Частичная", "Проектная", "Стажировка", "Волонтёрская"].index(employment_type) if employment_type else 0
        )
        new_description = st.text_area("Описание", value=description or "")
        new_remote_work_possible = st.checkbox("Готовность работать удаленно", value=remote_work_possible)
        submitted = st.form_submit_button("Сохранить изменения")
        
    if submitted:
        updates = {}
        if new_profession_id != profession_id:
            updates["profession_id"] = new_profession_id
        if new_age != age:
            updates["age"] = new_age
        if new_experience != experience:
            updates["experience"] = new_experience
        if new_city != city:
            updates["city"] = new_city
        if new_nearby_metro != nearby_metro:
            updates["nearby_metro"] = new_nearby_metro
        if new_employment_type != employment_type:
            updates["employment_type"] = new_employment_type
        if new_description != description:
            updates["description"] = new_description
        if new_remote_work_possible != remote_work_possible:
            updates["remote_work_possible"] = new_remote_work_possible

        if updates:
            try:
                update_resume_in_db(resume['resume_id'], updates)
                # Сброс кеша после обновления
                invalidate_resumes_cache()
                update_resume_cache(user_id)
                st.success("Резюме успешно обновлено!")
            except Exception as e:
                st.error(f"Ошибка при обновлении резюме: {e}")
        else:
            st.info("Изменений не найдено.")

    st.subheader("Опыт работы")
    with st.expander("Добавить место работы"):
        workplace_name = st.text_input("Название компании")
        workplace_description = st.text_area("Описание места работы (необязательно)")
        position = st.text_input("Должность")
        start_date = st.date_input("Дата начала работы")
        end_date = st.date_input("Дата окончания работы (оставьте пустым, если работаете сейчас)")
        responsibilities = st.text_area("Обязанности")
        
        if st.button("Добавить опыт работы"):
            try:
                if workplace_name and position and start_date:
                    add_work_experience_to_db(user_id, workplace_name, workplace_description, position, start_date, end_date, responsibilities)
                    # Сброс кеша после добавления опыта
                    invalidate_resumes_cache()
                    update_resume_cache(user_id)
                    st.success("Опыт работы добавлен!")
            except Exception as e:
                st.error(f"Ошибка при добавлении опыта работы: {e}")

    st.subheader("Профессиональные навыки")
    skill_input = st.text_input("Добавьте навыки (через запятую)")
    if st.button("Сохранить навыки"):
        skills = skill_input.split(',')
        skills = [skill.strip() for skill in skills]
        try:
            if resume['resume_id']:
                add_skills_to_db(skills, resume['resume_id'])
                # Сброс кеша после сохранения навыков
                invalidate_resumes_cache()
                update_resume_cache(user_id)
                st.success("Навыки сохранены!")
            else:
                st.error("Резюме не найдено!")
        except Exception as e:
            st.error(f"Ошибка при сохранении навыков: {e}")


if __name__ == "__main__":
    show_edit_resume_page()
