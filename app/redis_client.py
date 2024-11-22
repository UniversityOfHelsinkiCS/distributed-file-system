import redis.asyncio as redis

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASSWORD = "password"


async def setup():
    r = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True,
    )

    try:
        await r.ping()
        print("Redis is connected")
    except Exception as e:
        print(f"Redis is not connected: {e}")
    return r
