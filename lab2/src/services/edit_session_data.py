import os
import streamlit as st
import redis
import uuid
import json
import time
from dotenv import load_dotenv
import json
from datetime import date, datetime

def get_session_data(token):
    load_dotenv("env.env")
    r = redis.Redis(host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), db=0, decode_responses=True)
    if not token:
        return None
    session_json = r.get(f"session:{token}")
    if session_json:
        return json.loads(session_json)
    return None

def store_session_in_redis(user_data):
    load_dotenv("env.env")
    ttl = os.getenv("SESSION_TTL_SECONDS")
    r = redis.Redis(host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), db=0, decode_responses=True)
    token = str(uuid.uuid4())
    session_data = {
        "user_id": user_data['user_id'],
        "username": user_data['username'],
        "role": user_data['role'],
        "login_time": int(time.time())
    }
    r.setex(f"session:{token}", ttl, json.dumps(session_data))
    return token

def update_session_in_redis(token, new_data):
    load_dotenv("env.env")
    ttl = os.getenv("SESSION_TTL_SECONDS")
    r = redis.Redis(host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), db=0, decode_responses=True)
    session_key = f"session:{token}"
    session_json = r.get(session_key)
    if not session_json:
        raise Exception("Сессия не найдена или истекла")

    session_data = json.loads(session_json)
    session_data.update(new_data)

    def json_serializer(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    r.setex(session_key, ttl, json.dumps(session_data, default=json_serializer))

def ensure_token():
    query_params = st.query_params
    if "token" in query_params and "token" not in st.session_state:
        st.session_state["token"] = query_params["token"][0]
