import os
from threading import Thread
import time
from fastapi import FastAPI

from .raft_node import RaftNode
from .routes import router as routes_router

FILE_DIRECTORY = "storage"

# Set up RaftNode
is_leader = os.environ.get("LEADER") == "true"
print(f"Is leader: {is_leader}")

raft_node = RaftNode(
    1,
    ["app-2:8000", "app-3:8000"],
    is_leader,
)

# Ensure storage directory exists
if not os.path.exists(FILE_DIRECTORY):
    os.makedirs(FILE_DIRECTORY)

app = FastAPI()
app.include_router(routes_router)

def heartbeat():
    while True:
        raft_node.run()
        time.sleep(5)


t = Thread(target=heartbeat, daemon=True)
t.start()
