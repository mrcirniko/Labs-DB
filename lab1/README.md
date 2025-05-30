```sudo docker-compose down -v --remove-orphans```  
```sudo docker-compose up --build```  


# 1.1
Изучим индексы:  
1) B-tree в PostgreSQL основано на структуре данных B-дерево - сбалансированное сильноветвящееся дерево поиска. Работает лучше всего с простыми типами данных.  
2) GIN (Generalized Inverted Index) – обобщённый инвертированный индекс. Применяется к составным типам, работа с которыми осуществляется с помощью ключей: массивы и tsvector. Предназначен для случаев, когда индексируемые значения являются составными, а запросы ищут значения элементов в этих составных объектах.
3) BRIN (block range index) – блоковый индекс. Идея состоит в том, чтобы разбить данные на блоки и при поиске элемента пропускать блоки, в которых точно нету искомого, по средством хранения метаданных о блоке, таких как, например, минимальное и максимальное значение. Данный индекс лучше работает с данными, в которых порядок значений столбца коррелируется с порядком их расположения в физической памяти.  
Сравним производительность до и после добавления индексов:  
```
\d resumes

\timing
```
```sql
SELECT COUNT(*) FROM resumes WHERE category = 'Data Science';

SELECT COUNT(*) FROM resumes WHERE resume ILIKE '%python%';

SELECT COUNT(*) FROM resumes WHERE id BETWEEN 1000 AND 400000;
```
Вывод:
```
big_db=# \d resumes
                             Table "public.resumes"
  Column  |  Type   | Collation | Nullable |               Default
----------+---------+-----------+----------+-------------------------------------
 id       | integer |           | not null | nextval('resumes_id_seq'::regclass)
 category | text    |           |          |
 resume   | text    |           |          |
Indexes:
    "resumes_pkey" PRIMARY KEY, btree (id)
big_db=# \timing
Timing is on.
big_db=# SELECT COUNT(*) FROM resumes WHERE category = 'Data Science';
 count
-------
 20111
(1 row)

Time: 50.662 ms
big_db=# SELECT COUNT(*) FROM resumes WHERE resume ILIKE '%python%';

 count
-------
 78631
(1 row)

Time: 5181.891 ms (00:05.182)
big_db=#
big_db=# SELECT COUNT(*) FROM resumes WHERE id BETWEEN 1000 AND 400000;
 count
--------
 399001
(1 row)

Time: 24.838 ms
big_db=#
```
Внедрим индексы:
```sql
SET maintenance_work_mem = '2GB';
SET work_mem = '64MB';
SET statement_timeout = 0;


ALTER TABLE resumes ADD COLUMN IF NOT EXISTS tsv_resume tsvector;

DO $$
DECLARE
    batch_size INT := 30000;
    max_id INT;
    current_id INT := 0;
BEGIN
    SELECT MAX(id) INTO max_id FROM resumes;
    
    WHILE current_id <= max_id LOOP
        RAISE NOTICE 'Обновление tsvector для ID %-%', current_id, current_id + batch_size;
        
        UPDATE resumes 
        SET tsv_resume = to_tsvector('english', resume)
        WHERE id BETWEEN current_id AND current_id + batch_size
        AND tsv_resume IS NULL;
        
        COMMIT;
        current_id := current_id + batch_size;
        PERFORM pg_sleep(0.1);
    END LOOP;
END $$;


CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resumes_category ON resumes (category);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resumes_tsv ON resumes USING GIN(tsv_resume);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resumes_id_brin ON resumes USING BRIN(id);

SELECT 
    indexname, 
    indexdef 
FROM 
    pg_indexes 
WHERE 
    tablename = 'resumes';

RESET maintenance_work_mem;
RESET work_mem;
```
Протестим:
```sql
SELECT COUNT(*) FROM resumes WHERE category = 'Data Science';

SELECT COUNT(*) FROM resumes WHERE tsv_resume @@ plainto_tsquery('english', 'python');

SELECT COUNT(*) FROM resumes WHERE id BETWEEN 1000 AND 1100;
```
Вывод:
```
big_db=# SELECT COUNT(*) FROM resumes WHERE category = 'Data Science';
 count
-------
 20111
(1 row)

Time: 14.518 ms
big_db=# SELECT COUNT(*) FROM resumes WHERE tsv_resume @@ plainto_tsquery('english', 'python');
 count
-------
 78631
(1 row)

Time: 315.514 ms
big_db=# SELECT COUNT(*) FROM resumes WHERE id BETWEEN 1000 AND 400000;
 count
--------
 399001
(1 row)

Time: 79.900 ms
big_db=#
```
| Запрос                                                                 | До индексации       | После индексации      | Ускорение | Индекс                          | Примечания                                                                 |
|------------------------------------------------------------------------|---------------------|-----------------------|-----------|---------------------------------|----------------------------------------------------------------------------|
| `SELECT COUNT(*) FROM resumes WHERE category = 'Data Science'`         | 50.662 ms           | **14.518 ms**         | **3.5x**  | B-tree (`idx_resumes_category`) | Оптимальный случай для B-tree индекса                                      |
| `SELECT COUNT(*) FROM resumes WHERE resume ILIKE '%python%'` →<br>`tsv_resume @@ plainto_tsquery('python')` | 5181.891 ms | **315.514 ms**        | **16x**   | GIN (`idx_resumes_tsv`)         | Кардинальное ускорение полнотекстового поиска                              |
| `SELECT COUNT(*) FROM resumes WHERE id BETWEEN 1000 AND 400000`        | **24.838 ms**       | 79.900 ms             | **0.3x**  | BRIN (`idx_resumes_id_brin`)    | BRIN оказался медленнее встроенного B-tree PK, так как строк не так много и столбец **id** изначально отсортирован           |



# 1.2
В стандарте SQL описывается 4 уровня изоляции транзакций:  
1) READ UNCOMMITTED (Чтение неподтвержденных данных): Наименьший уровень изоляции, где транзакции видят неподтвержденные изменения других транзакций. Этот уровень обеспечивает максимальную параллельность, но может привести к непредсказуемым результатам из-за “грязного чтения”.  
2) READ COMMITTED (Чтение подтвержденных данных): Большинство баз данных, включая PostgreSQL, используют этот уровень по умолчанию. Транзакции видят только подтвержденные изменения других транзакций. Это предотвращает “грязное чтение”, но допускает “неповторяющееся чтение”.  
3) REPEATABLE READ (Повторяемое чтение): В этом режиме транзакции видят только данные, которые были считаны на момент начала транзакции. Это предотвращает “грязное чтение” и “неповторяющееся чтение”, но может привести к “фантомным” записям, когда другая транзакция вставляет новые записи.  
4) SERIALIZABLE (Сериализуемость): Самый строгий уровень изоляции. Транзакции выполняются так, как если бы они выполнялись последовательно. Это предотвращает “грязное чтение”, “неповторяющееся чтение” и “фантомные” записи. Однако это может привести к блокировкам и ухудшению производительности.  

В PostgreSQL нету READ UNCOMMITTED, а значит и “грязного чтения”.  

Для уровней изоляции Read committed и Read uncommited допустимы следующие аномалиия чтения данных:  

1) Неповторяемое чтение — транзакция повторно читает те же данные, что и раньше, и обнаруживает, что они были изменены другой транзакцией (которая завершилась после первого чтения).  

2) Фантомное чтение — транзакция повторно выполняет запрос, возвращающий набор строк для некоторого условия, и обнаруживает, что набор строк, удовлетворяющих условию, изменился из-за транзакции, завершившейся за это время.  
PostgreSQL по умолчанию использует Read committed.  
## Демонстрация аномалии: (Phantom Read)
Терминал 1:
```sql
BEGIN;
SELECT COUNT(*) FROM resumes WHERE category = 'new category';

```
Терминал 2:
```sql
BEGIN;
INSERT INTO resumes (category, resume)
VALUES ('new category', 'phantom resume');
COMMIT;
```
Терминал 1:
```sql
SELECT COUNT(*) FROM resumes WHERE category = 'new category';
COMMIT;
```
Устраним с уровнем изоляции REPEATABLE READ:  
Терминал 1:
```sql
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT COUNT(*) FROM resumes WHERE category = 'new category';
```
Терминал 2:
```sql
BEGIN;
INSERT INTO resumes (category, resume)
VALUES ('new category', 'phantom resume');
COMMIT;
```
Терминал 1:
```sql
SELECT COUNT(*) FROM resumes WHERE category = 'new category';
COMMIT;
```
## Non-Repeatable 
Терминал 1:
```sql
BEGIN;
SELECT resume FROM resumes WHERE category = 'new category';
```
Терминал 2:
```sql
BEGIN;
UPDATE resumes SET resume = 'updated resume' WHERE category = 'new category';
COMMIT;
```
Терминал 1:
```sql
SELECT resume FROM resumes WHERE category = 'new category';
COMMIT;
```
Исправление:
Перед вводом добавить:
```sql
BEGIN ISOLATION LEVEL REPEATABLE READ;
```

# 1.3
```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```
```sql
DROP INDEX IF EXISTS idx_resume_trgm;
DROP INDEX IF EXISTS idx_resume_bigram;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pg_bigm;
CREATE INDEX idx_resume_trgm ON resumes USING gin (resume gin_trgm_ops);
CREATE INDEX idx_resume_bigram ON resumes USING gin (resume gin_bigm_ops);
SET enable_seqscan = OFF;
DROP INDEX IF EXISTS idx_resume_bigram;
EXPLAIN ANALYZE
SELECT * FROM resumes WHERE resume LIKE '%machine learning%';
CREATE INDEX idx_resume_bigram ON resumes USING gin (resume gin_bigm_ops);
DROP INDEX IF EXISTS idx_resume_trgm;
EXPLAIN ANALYZE
SELECT * FROM resumes WHERE resume LIKE '%machine learning%';
```
## Сравнение индексов `pg_trgm` и `pg_bigm` в PostgreSQL

Запрос:  
```sql
SELECT * FROM resumes WHERE resume LIKE '%machine learning%';
```

Результаты выполнения (`EXPLAIN ANALYZE`):  

| Параметр                      | `pg_trgm`                                       | `pg_bigm`                                       |
|------------------------------|--------------------------------------------------|--------------------------------------------------|
| Bitmap Index Scan            | `idx_resume_trgm`                               | `idx_resume_bigram`                             |
| Index Cond                   | `(resume ~~ '%machine learning%'::text)`        | `(resume ~~ '%machine learning%'::text)`        |
| Rows matched (до Recheck)    | 32345                                           | 250398                                           |
| Rows Removed by Recheck      | 22530                                           | 240583                                           |
| Rows (после Recheck)         | 9815                                            | 9815                                             |
| Heap Blocks (exact)          | 24670                                           | 55235                                            |
| Planning Time                | 4.301 ms                                        | 0.636 ms                                         |
| Bitmap Index Scan Time       | 63.285..63.286 ms                               | 160.384..160.384 ms                              |
| Execution Time               | 695.238 ms                                      | 5779.180 ms                                      |
| Index Creation Time          | 296545.892 ms (04:56.546)                       | 210034.017 ms (03:30.034)                        |

---
Обе расширения позволяют ускорить поиск по подстроке, но:

Преимущества `pg_trgm`:
- Более точный индекс: меньше ложных срабатываний.
- Существенно быстрее при выполнении запроса.
- Меньше чтений с диска (`Heap Blocks`).
- Лучше подходит для длинных текстов и произвольных подстрок.

Недостатки `pg_trgm`:
- Более долгое время создания индекса (почти 5 минут).

---

Преимущества `pg_bigm`:
- Быстрее создается индекс (на 1.5 минуты быстрее, чем `pg_trgm`).
- Возможен выигрыш при коротких строках и коротких подстроках.

Недостатки `pg_bigm`:
- Сильно перегружает фильтрацию (`Rows Removed by Recheck`: 240k).
- В 8 раз медленнее выполнения.
- Использует в 2 раза больше блоков памяти.

---

### Вывод:  
pg_trgm:
- Для европейских языков с длинными словами.
- Поиск подстрок.
pg_bigm:
- Для азиатских языков или коротких терминов.
- Частые запросы с LIKE 'prefix%' или LIKE '%suffix'.

## pgcrypto
Зашифруем:  
```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE resumes
    ALTER COLUMN resume TYPE bytea USING convert_to(resume, 'UTF8');

INSERT INTO resumes (category, resume)
VALUES (
    'some_category',
    pgp_sym_encrypt('Ivanov Ivan, Fullstack developer, phone: 123-456', 'my_secret_key')
);
```
Попробуем получить доступ к данным:
```sql
SELECT id, category,
       resume AS resume_text
FROM resumes
WHERE category = 'some_category';
```
Результат:  
```
 id |   category    |                                                                                                              resume_text                              
----+---------------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  5000003 | some_category | \xc30d040703024dad3621eba7328b64d26101a1bfa47aa09c1380f8a38416f31b3759b0564303e396e7db7e42fcc0f722dcba3c3c1792a0c908e3c27718f6b8d082bf2fce1ab13df039ad1cd52be9fa72d44e7d7ec820cfffa3122f624caacf1fbf6627204995103f091bb1b0b0f910b44c6a
(1 row)

(END)
```
Используем ключ для расшифровки:
```sql
SELECT id, category,
       pgp_sym_decrypt(resume, 'my_secret_key') AS resume_text
FROM resumes
WHERE category = 'some_category';
```
Результат:
```
 id |   category    |                   resume_text
----+---------------+--------------------------------------------------
  5000003 | some_category | Ivanov Ivan, Fullstack developer, phone: 123-456
(1 row)
```
**Преимущества** :
- Данные защищены на уровне БД
- Поддержка AES-256 и других алгоритмов
- Возможность разделения прав доступа

**Риски** :
- Нет индексирования зашифрованных полей
- Добавляет нагрузку на CPU

### Вывод
`pgcrypto` обеспечивает:
   - Шифрование "из коробки"
   - Совместимость со стандартами
   - Требует аккуратного управления ключами
