from contextlib import asynccontextmanager
import os
import asyncio
from fastapi import FastAPI

from .raft_node import RaftNode
from .routes import router as routes_router
from .rpc import rpc_router

FILE_DIRECTORY = "storage"

node_id = os.environ.get("NODE_ID")

if not node_id:
    raise ValueError("NODE_ID environment variable is required")

raft_node = RaftNode(
    node_id,
    ["app-1:8000", "app-2:8000", "app-3:8000"],
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
app.raft_node = raft_node

app.include_router(routes_router)
app.include_router(rpc_router)
