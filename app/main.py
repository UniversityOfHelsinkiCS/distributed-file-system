from contextlib import asynccontextmanager
import os
import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .constants import FILE_DIRECTORY
from .middleware import LoggingMiddleware
from .raft_node import RaftNode
from .redis_client import get_redis_store
from .routes import router as routes_router
from .rpc import rpc_router

node_id = os.environ.get("NODE_ID")
raft_nodes = os.environ.get("RAFT_NODES")

if not node_id:
    raise ValueError("NODE_ID environment variable is required")

if not raft_nodes:
    raise ValueError("RAFT_NODES environment variable is required")

raft_node = RaftNode(
    node_id,
    raft_nodes.split(","),
    get_redis_store(),
)

# Ensure storage directory exists
if not os.path.exists(FILE_DIRECTORY):
    os.makedirs(FILE_DIRECTORY)


async def heartbeat():
    while True:
        await raft_node.run()
        await asyncio.sleep(raft_node.heartbeat_interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(heartbeat())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)
app.add_middleware(LoggingMiddleware)
app.mount("/app/static", StaticFiles(directory="app/static"), name="static")
app.raft_node = raft_node

app.include_router(routes_router)
app.include_router(rpc_router)
