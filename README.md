
# 1.1
Изучим индексы:  
1) B-tree в Postgresql основано на структуре данных B-дерево - сбалансированное сильноветвящееся дерево поиска. Работает лучше всего с простыми типами данных.  
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
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pg_bigm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```
```sql
CREATE INDEX resume_trgm_idx ON resumes USING gin (resume gin_trgm_ops);
```
```sql
CREATE INDEX resume_bigm_idx ON resumes USING gin (resume gin_bigm_ops);
```





```
CREATE INDEX resume_trgm_idx ON resumes USING gin (resume gin_trgm_ops);
big_db=# EXPLAIN ANALYZE SELECT * FROM resumes WHERE resume ILIKE '%python developer%';
big_db=#
                                                            QUERY PLAN              
-----------------------------------------------------------------------------------------------------------------------------------
 Bitmap Heap Scan on resumes  (cost=916.22..18811.15 rows=6222 width=846) (actual time=58.702..2602.698 rows=20018 loops=1)
   Recheck Cond: (resume ~~* '%python developer%'::text)
   Rows Removed by Index Recheck: 45997
   Heap Blocks: exact=38774
   ->  Bitmap Index Scan on idx_resume_trgm  (cost=0.00..914.67 rows=6222 width=0) (actual time=52.807..52.807 rows=66015 loops=1)
         Index Cond: (resume ~~* '%python developer%'::text)
 Planning Time: 0.449 ms
 Execution Time: 2603.942 ms
(8 rows)

(END)
```
```
big_db=# CREATE INDEX idx_resume_bigram ON resumes USING GIN (resume gin_bigm_ops);
CREATE INDEX
big_db=# EXPLAIN ANALYZE SELECT * FROM resumes WHERE resume ILIKE '%python developer%';
                                                            QUERY PLAN              
-----------------------------------------------------------------------------------------------------------------------------------
 Bitmap Heap Scan on resumes  (cost=916.22..18811.15 rows=6222 width=846) (actual time=54.961..2480.944 rows=20018 loops=1)
   Recheck Cond: (resume ~~* '%python developer%'::text)
   Rows Removed by Index Recheck: 45997
   Heap Blocks: exact=38774
   ->  Bitmap Index Scan on idx_resume_trgm  (cost=0.00..914.67 rows=6222 width=0) (actual time=49.674..49.675 rows=66015 loops=1)
         Index Cond: (resume ~~* '%python developer%'::text)
 Planning Time: 2.160 ms
 Execution Time: 2482.199 ms
(8 rows)

(END)
```
