INSERT INTO Users (password_hash, username, role)
VALUES
    ('$2b$12$gOa/j.qo3RVO.0anHTKbJuH2HHnIpi5j4zRvOuQbp.Bu7tw4A5gs.', 'user1', 'candidate'), -- password: 123
    ('$2b$12$dy3gwX9hNObb/M4N0FpM4uLklavxjRrDSwaoe7.MLd9gbqrwKPwY.', 'user2', 'employer'), -- password: 1234
    ('$2b$12$4BH3hiJfrlNiSaKURBSmvOqDYggJKlyiKi6pSoTUk3VcBMWft7kcO', 'user3', 'admin'); -- password: maistud

INSERT INTO Professions (profession_name)
VALUES
    ('Software Developer'),
    ('Data Scientist'),
    ('Product Manager');

INSERT INTO Resumes (user_id, profession_id, age, experience, city, nearby_metro, employment_type, description, remote_work_possible)
VALUES
    (1, 2, 28, 5, 'Moscow', 'Kievskaya', 'Полная', 'Data scientist with a focus on AI', true);

INSERT INTO Employers (user_id, email, phone, show_phone)
VALUES
    (2, 'employer@example.com', '1234567890', true);

INSERT INTO Candidates (user_id, email, phone, show_phone)
VALUES
    (1, 'candidate@example.com', '9876543210', false);

INSERT INTO LikedResumes (user_id, employer_id, liked_date)
VALUES
    (1, 2, CURRENT_DATE);

INSERT INTO Skills (skill_name)
VALUES
    ('Java'),
    ('Python'),
    ('Machine Learning');

INSERT INTO ResumeSkills (resume_id, skill_id)
VALUES
    (1, 1),
    (1, 2);

INSERT INTO WorkExperience (candidate_id, workplace_name, description, position, start_date, end_date, responsibilities)
VALUES
    (1, 'Tech Corp', 'Software development company', 'Software Engineer', '2018-01-01', '2023-01-01', 'Developing software products');
