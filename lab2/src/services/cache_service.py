import os
import json
import hashlib
import threading
import datetime
import redis
from dotenv import load_dotenv

load_dotenv("env.env")

cache = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=os.getenv("REDIS_PORT"),
    db=0,
    decode_responses=True
)


# --- Универсальный JSON encoder ---
def convert_dates(obj):
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    elif isinstance(obj, list):
        return [convert_dates(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_dates(v) for k, v in obj.items()}
    return obj


# --- Генерация ключа ---
def make_filters_key(filters, sort_by):
    key_dict = {
        "filters": filters,
        "sort_by": sort_by
    }
    json_string = json.dumps(key_dict, sort_keys=True)
    return "resumes:" + hashlib.sha256(json_string.encode()).hexdigest()


# --- Обертка для кеша ---
def get_or_set_resumes_cache(filters, sort_by, fetch_function, ttl=300):
    redis_key = make_filters_key(filters, sort_by)
    cached = cache.get(redis_key)
    if cached:
        print(f"[CACHE HIT] {redis_key}")
        return json.loads(cached)

    data = fetch_function(filters, sort_by)
    try:
        serialized = json.dumps(convert_dates(data))
        cache.set(redis_key, serialized, ex=ttl)
        print(f"[CACHE MISS] Stored {redis_key}")
    except Exception as e:
        print(f"Ошибка кеширования: {e}")
    return data


# --- Подписка и инвалидирование ---
def start_cache_invalidation_listener():
    def pubsub_listener():
        pubsub = cache.pubsub()
        pubsub.subscribe('resumes_cache_channel')
        for message in pubsub.listen():
            if message['type'] == 'message':
                key_to_delete = message['data']
                print(f"[PUBSUB] Invalidating cache: {key_to_delete}")
                cache.delete(key_to_delete)

    threading.Thread(target=pubsub_listener, daemon=True).start()


# --- Проверка лайка ---
def check_if_liked(candidate_id, employer_id, fetch_likes_from_db):
    redis_key = f"liked_resumes:{employer_id}"

    if cache.exists(redis_key):
        return cache.sismember(redis_key, str(candidate_id))

    liked_ids = fetch_likes_from_db(employer_id)
    if liked_ids:
        cache.sadd(redis_key, *liked_ids)
    return str(candidate_id) in liked_ids


# --- Добавление лайка ---
def add_liked_resume_to_cache(candidate_id, employer_id):
    redis_key = f"liked_resumes:{employer_id}"
    cache.sadd(redis_key, str(candidate_id))
    cache.publish("likes_channel", f"liked:{candidate_id}:{employer_id}")
    print(f"[ADD LIKE] Candidate {candidate_id} by employer {employer_id}")
