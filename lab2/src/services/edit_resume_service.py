import psycopg2
from psycopg2.extras import RealDictCursor
from repositories.connector import get_connection

# Функция для получения данных о резюме
def get_resume_by_user(user_id):
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM Resumes WHERE user_id = %s", (user_id,))
                resume = cur.fetchone()
                return resume
    except Exception as e:
        raise Exception(f"Ошибка при загрузке резюме: {e}")

# Функция для обновления резюме
def update_resume_in_db(resume_id, updates):
    print(updates)
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                set_clauses = ", ".join([f"{key} = %s" for key in updates.keys()])
                values = list(updates.values()) + [resume_id]
                query = f"UPDATE Resumes SET {set_clauses} WHERE resume_id = %s"
                cur.execute(query, values)
                conn.commit()
    except Exception as e:
        raise Exception(f"Ошибка при обновлении резюме: {e}")

# Функция для добавления резюме
def add_resume_to_db(user_id, profession_id, age, experience, city, nearby_metro, employment_type, description, remote_work_possible):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO Resumes (user_id, profession_id, age, experience, city, nearby_metro, employment_type, description, remote_work_possible)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING resume_id
                """, (user_id, profession_id, age, experience, city, nearby_metro, employment_type, description, remote_work_possible))
                resume_id = cur.fetchone()[0]
                conn.commit()
                return resume_id
    except Exception as e:
        raise Exception(f"Ошибка при сохранении резюме: {e}")

# Функция для добавления опыта работы
def add_work_experience_to_db(candidate_id, workplace_name, description, position, start_date, end_date, responsibilities):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO WorkExperience (candidate_id, workplace_name, description, position, start_date, end_date, responsibilities)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (candidate_id, workplace_name, description, position, start_date, end_date, responsibilities))
                conn.commit()
    except Exception as e:
        raise Exception(f"Ошибка при сохранении опыта работы: {e}")

# Функция для сохранения навыков
def add_skills_to_db(skills, resume_id):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Добавляем скиллы в таблицу Skills (если они уже не существуют)
                for skill in skills:
                    cur.execute(
                        "INSERT INTO Skills (skill_name) VALUES (%s) ON CONFLICT (skill_name) DO NOTHING",
                        (skill,)
                    )
                conn.commit()

                # Получаем ID всех добавленных скиллов
                for skill in skills:
                    cur.execute("SELECT skill_id FROM Skills WHERE skill_name = %s", (skill,))
                    skill_id = cur.fetchone()[0]
                    
                    # Связываем скиллы с резюме в таблице ResumeSkills
                    cur.execute(
                        "INSERT INTO ResumeSkills (resume_id, skill_id) VALUES (%s, %s) ON CONFLICT (resume_id, skill_id) DO NOTHING",
                        (resume_id, skill_id)
                    )
                conn.commit()

    except Exception as e:
        raise Exception(f"Ошибка при сохранении скиллов и связи с резюме: {e}")


# Функция для получения списка профессий (для отображения в интерфейсе)
def get_professions():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT profession_id, profession_name FROM Professions")
                professions = cur.fetchall()
                return professions
    except Exception as e:
        raise Exception(f"Ошибка при получении профессий: {e}")

# Функция для получения списка профессиональных навыков (для отображения в интерфейсе)
def get_skills():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT skill_name FROM Skills")
                skills = cur.fetchall()
                return skills
    except Exception as e:
        raise Exception(f"Ошибка при получении навыков: {e}")

def get_work_experience(user_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT * FROM WorkExperience WHERE candidate_id = %s
            """, (user_id,))
            return cursor.fetchall()
