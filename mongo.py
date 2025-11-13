# mongo.py
from pymongo import MongoClient, ASCENDING
from config import settings

_client = MongoClient(settings.MONGO_URI)
mongo_db = _client[settings.MONGO_DB]

# Collections
scrum_col = mongo_db["daily_scrums"]

# Ensure indexes (idempotent)
scrum_col.create_index([("subproject_id", ASCENDING)])
scrum_col.create_index([("user_id", ASCENDING)])
scrum_col.create_index([("created_at", ASCENDING)])
