import os
import redis.asyncio as redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "password")


async def setup_redis():
    r = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True,
    )

    try:
        await r.ping()
        print(f"Redis is connected to {REDIS_HOST}:{REDIS_PORT}")
    except Exception as e:
        print(f"Redis is not connected: {e}")
    return r
