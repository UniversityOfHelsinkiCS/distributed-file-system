import time
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from .raft_node import RaftNode, RaftState

rpc_router = APIRouter()


class RPCRequest(BaseModel):
    method: str
    params: Dict[str, Any]


class HeartbeatParams(BaseModel):
    term: int


class RequestVoteParams(BaseModel):
    term: int
    candidate_id: str


async def heartbeat(raft_node: RaftNode, params: HeartbeatParams):
    async with raft_node.lock:
        term = params.term
        print(f"Received heartbeat for term {term}")
        if term > raft_node.current_term:
            raft_node.current_term = term
            raft_node.state = RaftState.FOLLOWER
            raft_node.voted_for = None
            print(f"Stepping down to follower due to higher term {term}")
        elif term == raft_node.current_term:
            if raft_node.state != RaftState.FOLLOWER:
                raft_node.state = RaftState.FOLLOWER
                raft_node.voted_for = None
                print(
                    f"Stepping down to follower due to heartbeat from leader in same term {term}"
                )
        else:
            print(f"Received stale heartbeat from term {term}")
            return {"term": raft_node.current_term}
        raft_node.last_heartbeat = time.time()
        return {"term": raft_node.current_term}


async def request_vote(raft_node: RaftNode, params: RequestVoteParams):
    async with raft_node.lock:
        term = params.term
        candidate_id = params.candidate_id
        print(f"Received vote request from {candidate_id} for term {term}")

        if term < raft_node.current_term:
            print(f"Rejecting vote request from {candidate_id} for stale term {term}")
            return {"term": raft_node.current_term, "vote_granted": False}

        if term > raft_node.current_term:
            raft_node.current_term = term
            raft_node.voted_for = None
            raft_node.state = RaftState.FOLLOWER

        vote_granted = False
        if raft_node.voted_for in (None, candidate_id):
            raft_node.voted_for = candidate_id
            vote_granted = True
            raft_node.last_heartbeat = time.time()
            print(f"Voted for {candidate_id} in term {term}")
        else:
            print(
                f"Did not vote for {candidate_id} in term {term}; already voted for {raft_node.voted_for}"
            )

    return {"term": raft_node.current_term, "vote_granted": vote_granted}


rpc_methods = {
    "heartbeat": (heartbeat, HeartbeatParams),
    "request_vote": (request_vote, RequestVoteParams),
}


@rpc_router.post("/rpc")
async def rpc_handler(request: RPCRequest, fastapi_request: Request):
    method_tuple = rpc_methods.get(request.method)
    if not method_tuple:
        raise HTTPException(status_code=400, detail="Method not found")

    method, params_model = method_tuple
    raft_node = fastapi_request.app.raft_node

    try:
        params = params_model(**request.params)
        result = await method(raft_node, params)
        return {"result": result}
    except TypeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Parameter type error: {e}")
