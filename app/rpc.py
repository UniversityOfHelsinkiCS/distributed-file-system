from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

rpc_router = APIRouter()

class RPCRequest(BaseModel):
    method: str
    params: Dict[str, Any]

async def heartbeat():
    print("received heartbeat")

rpc_methods = {
    "heartbeat": heartbeat,
}

@rpc_router.post("/rpc")
async def rpc_handler(request: RPCRequest):
    method = rpc_methods.get(request.method)
    if not method:
        raise HTTPException(status_code=400, detail="Method not found")

    try:
        # Call the method with the provided parameters
        result = await method(**request.params)
        return {"result": result}
    except TypeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {e}")
