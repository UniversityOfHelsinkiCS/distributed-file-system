import time
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any
from .raft_node import RaftNode

rpc_router = APIRouter()


class RPCRequest(BaseModel):
    method: str
    params: Dict[str, Any]


async def heartbeat(raft_node: RaftNode):
    print("received heartbeat")
    raft_node.last_heartbeat = time.time()


rpc_methods = {
    "heartbeat": heartbeat,
}


@rpc_router.post("/rpc")
async def rpc_handler(request: RPCRequest, fastapi_request: Request):
    method = rpc_methods.get(request.method)
    if not method:
        raise HTTPException(status_code=400, detail="Method not found")

    raft_node = fastapi_request.app.raft_node

    try:
        result = await method(raft_node, **request.params)
        return {"result": result}
    except TypeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {e}")
