"""Opt-in real local Redis contract, never a provider or model request."""

from datetime import timedelta
import os
from uuid import uuid4

from cryptography.fernet import Fernet
import pytest

from src.config.settings import get_settings
from src.integrations.contracts import digest, now
from src.tools import cache


@pytest.mark.skipif(
    not os.environ.get("AGRIROOTS_TEST_REDIS_URL"), reason="Set AGRIROOTS_TEST_REDIS_URL for the dedicated local Redis"
)
def test_redis_cache_authenticates_partition_freshness_and_key_rotation(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "secret_encryption_key", Fernet.generate_key().decode())
    key = digest({"office": uuid4().hex, "credential_scope": "account-a", "tool_version": "v1"})
    other = digest({"office": uuid4().hex, "credential_scope": "account-b", "tool_version": "v2"})
    private_value = {"data": {"fixture": True, "marker": uuid4().hex}, "retrieved_at": now().isoformat()}
    redis = cache.client(settings.redis_url)
    try:
        cache.put(key, private_value, now() + timedelta(minutes=1))
        assert cache.get(key) == private_value and cache.get(other) is None
        token = redis.get("agrilo:connector:" + key)
        assert private_value["data"]["marker"] not in token
        redis.setex("agrilo:connector:" + other, 60, token)
        assert cache.get(other) is None  # authenticated key partition defeats value swapping
        monkeypatch.setattr(settings, "secret_encryption_key", Fernet.generate_key().decode())
        assert cache.get(key) is None
    finally:
        redis.delete("agrilo:connector:" + key, "agrilo:connector:" + other)
