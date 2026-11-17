"""Optional authenticated Redis cache. PostgreSQL remains the permission/budget authority."""

from datetime import datetime
from functools import lru_cache
import json
from redis import Redis
from redis.exceptions import RedisError
from src.config.settings import get_settings
from src.integrations.contracts import now, utc
from src.integrations.secrets import cipher


@lru_cache(maxsize=4)
def client(url):
    return Redis.from_url(url, socket_connect_timeout=0.2, socket_timeout=0.2, decode_responses=True)


def get(key):
    settings = get_settings()
    if not settings.redis_url or not settings.secret_encryption_key:
        return None
    try:
        token = client(settings.redis_url).get("agrilo:connector:" + key)
        if not token:
            return None
        payload = json.loads(cipher().decrypt(token.encode()))
        if payload["key"] != key or utc(datetime.fromisoformat(payload["expires_at"])) <= now():
            return None
        return payload["value"]
    except Exception:
        # Cache/key rotation failures never change permissions or fabricate results.
        return None


def put(key, value, expires_at):
    settings = get_settings()
    if not settings.redis_url or not settings.secret_encryption_key:
        return
    ttl = int((utc(expires_at) - now()).total_seconds())
    if ttl <= 0:
        return
    try:
        token = cipher().encrypt(
            json.dumps({"key": key, "value": value, "expires_at": expires_at.isoformat()}).encode()
        )
        client(settings.redis_url).setex("agrilo:connector:" + key, ttl, token.decode())
    except (RedisError, ValueError):
        return
