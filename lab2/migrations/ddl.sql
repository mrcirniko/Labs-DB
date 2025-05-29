-- Создание таблицы Users
CREATE TABLE Users (
    user_id SERIAL PRIMARY KEY,
    password_hash VARCHAR(255) NOT NULL,
    username VARCHAR(255) NOT NULL UNIQUE,
    role VARCHAR(50) NOT NULL CHECK (role IN ('candidate', 'employer', 'admin'))
);

COMMENT ON TABLE Users IS 'Хранит информацию о пользователях';
COMMENT ON COLUMN Users.user_id IS 'Уникальный идентификатор пользователя';
COMMENT ON COLUMN Users.password_hash IS 'Хеш пароля';
COMMENT ON COLUMN Users.username IS 'Имя пользователя';
COMMENT ON COLUMN Users.role IS 'Роль пользователя';

-- Создание таблицы Professions
CREATE TABLE Professions (
    profession_id SERIAL PRIMARY KEY,
    profession_name VARCHAR(255) NOT NULL UNIQUE
);

COMMENT ON TABLE Professions IS 'Хранит информацию о профессиях';

-- Создание таблицы Resumes
CREATE TABLE Resumes (
    resume_id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE REFERENCES Users(user_id),
    profession_id INTEGER REFERENCES Professions(profession_id),
    last_modified DATE DEFAULT CURRENT_DATE,
    age INTEGER CHECK (age > 0),
    experience INTEGER CHECK (experience >= 0),
    city VARCHAR(255),
    nearby_metro VARCHAR(255),
    employment_type VARCHAR(255),
    description TEXT,
    remote_work_possible BOOLEAN DEFAULT FALSE
);

COMMENT ON TABLE Resumes IS 'Хранит информацию о резюме';
COMMENT ON COLUMN Resumes.last_modified IS 'Дата последнего изменения резюме';
COMMENT ON COLUMN Resumes.age IS 'Возраст кандидата';
COMMENT ON COLUMN Resumes.experience IS 'Опыт работы кандидата';

-- Таблица Employers
CREATE TABLE Employers (
    user_id INTEGER PRIMARY KEY REFERENCES Users(user_id),
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(15),
    show_phone BOOLEAN DEFAULT FALSE,
    company_name VARCHAR(255),
    company_description TEXT
);

COMMENT ON TABLE Employers IS 'Хранит информацию о работодателях';
COMMENT ON COLUMN Employers.email IS 'Email работодателя';
COMMENT ON COLUMN Employers.phone IS 'Телефон работодателя';
COMMENT ON COLUMN Employers.show_phone IS 'Флаг отображения телефона';
COMMENT ON COLUMN Employers.company_name IS 'Название компании';
COMMENT ON COLUMN Employers.company_description IS 'Краткое описание компании';


-- Создание таблицы Candidates
CREATE TABLE Candidates (
    user_id INTEGER PRIMARY KEY REFERENCES Users(user_id),
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(15),
    show_phone BOOLEAN DEFAULT FALSE
);

COMMENT ON TABLE Candidates IS 'Хранит информацию о кандидатах';
COMMENT ON COLUMN Candidates.email IS 'Email кандидата';
COMMENT ON COLUMN Candidates.phone IS 'Телефон кандидата';
COMMENT ON COLUMN Candidates.show_phone IS 'Флаг отображения телефона';

-- Создание таблицы LikedResumes
CREATE TABLE LikedResumes (
    user_id INTEGER REFERENCES Candidates(user_id),
    employer_id INTEGER REFERENCES Employers(user_id),
    liked_date DATE DEFAULT CURRENT_DATE,
    PRIMARY KEY (user_id, employer_id)
);

COMMENT ON TABLE LikedResumes IS 'Хранит информацию о понравившихся резюме';

-- Создание таблицы Skills
CREATE TABLE Skills (
    skill_id SERIAL PRIMARY KEY,
    skill_name VARCHAR(255) NOT NULL UNIQUE
);

COMMENT ON TABLE Skills IS 'Хранит информацию о навыках';

-- Создание таблицы ResumeSkills (связь резюме с навыками)
CREATE TABLE ResumeSkills (
    resume_id INTEGER REFERENCES Resumes(resume_id),
    skill_id INTEGER REFERENCES Skills(skill_id),
    PRIMARY KEY (resume_id, skill_id)
);

COMMENT ON TABLE ResumeSkills IS 'Связь резюме с навыками кандидата';

-- Создание таблицы WorkExperience
CREATE TABLE WorkExperience (
    work_experience_id SERIAL PRIMARY KEY,
    candidate_id INTEGER REFERENCES Candidates(user_id),
    workplace_name VARCHAR(255) NOT NULL,
    description TEXT,
    position VARCHAR(255),
    start_date DATE NOT NULL,
    end_date DATE,
    responsibilities TEXT
);

COMMENT ON TABLE WorkExperience IS 'Хранит информацию об опыте работы кандидатов';


-- Триггер для автоматического обновления last_modified в Resumes при изменении
CREATE OR REPLACE FUNCTION update_last_modified() 
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified = CURRENT_DATE;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_resume_date
BEFORE UPDATE ON Resumes
FOR EACH ROW
EXECUTE FUNCTION update_last_modified();


-- Представление для поиска резюме по ключевым полям, включая навыки
CREATE OR REPLACE VIEW ResumeSearch AS
SELECT r.resume_id, r.user_id, r.profession_id, r.age, r.description, r.experience, r.city, r.nearby_metro, 
       r.employment_type, r.remote_work_possible, r.last_modified, p.profession_name,
       array_agg(s.skill_name) FILTER (WHERE s.skill_name IS NOT NULL) AS skills
FROM Resumes r
JOIN Professions p ON r.profession_id = p.profession_id
LEFT JOIN ResumeSkills rs ON r.resume_id = rs.resume_id
LEFT JOIN Skills s ON rs.skill_id = s.skill_id
GROUP BY r.resume_id, p.profession_name;


COMMENT ON VIEW ResumeSearch IS 'Представление для поиска резюме по основным полям и навыкам';
