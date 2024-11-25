import os
import redis.asyncio as redis

REDIS_HOST = os.getenv("REDIS_HOST", "http://redis-distributed-filesystem-svc")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "password")


pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
)


def get_redis_store():
    return redis.Redis(connection_pool=pool)
