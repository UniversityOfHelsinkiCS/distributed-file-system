import base64
import os
from pathlib import Path
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .constants import FILE_DIRECTORY
from .logger import logger
from .raft_node import LogEntry, RaftNode, RaftState

rpc_router = APIRouter()


class AppendEntriesParams(BaseModel):
    term: int
    leader_id: str
    prev_log_index: int
    prev_log_term: int
    entries: list[dict[str, Any]]
    leader_commit: int


async def append_entries(raft_node: RaftNode, params: AppendEntriesParams):
    async with raft_node.lock:
        term = params.term
        if term < raft_node.current_term:
            return {"term": raft_node.current_term, "success": False}

        if term > raft_node.current_term:
            raft_node.current_term = term
            raft_node.voted_for = None
            raft_node.state = RaftState.FOLLOWER
        elif raft_node.state != RaftState.FOLLOWER and term == raft_node.current_term:
            raft_node.state = RaftState.FOLLOWER
            logger.info(
                f"Stepping down to follower due to appendEntries RPC from leader in same term {term}"
            )

        raft_node.last_heartbeat = time.time()
        raft_node.leader_address = (
            f"app-{params.leader_id}:8000"
            if f"app-{params.leader_id}:8000" in raft_node.peers
            else f"distributed-filesystem-node-{params.leader_id}:8080"
        )

        # Check log consistency
        if params.prev_log_index > 0:
            if len(raft_node.log) < params.prev_log_index:
                return {"term": raft_node.current_term, "success": False}
            if raft_node.log[params.prev_log_index - 1].term != params.prev_log_term:
                raft_node.log = raft_node.log[: params.prev_log_index - 1]
                return {"term": raft_node.current_term, "success": False}

        for i, new_entry in enumerate(params.entries, start=params.prev_log_index + 1):
            if i <= len(raft_node.log):
                if raft_node.log[i - 1].term != new_entry["term"]:
                    raft_node.log = raft_node.log[: i - 1]
                    raft_node.log.append(
                        LogEntry(new_entry["term"], i, new_entry["command"])
                    )
            else:
                raft_node.log.append(
                    LogEntry(new_entry["term"], i, new_entry["command"])
                )

        if params.leader_commit > raft_node.commit_index:
            raft_node.commit_index = min(params.leader_commit, len(raft_node.log))

        await raft_node.apply_entries()

        return {"term": raft_node.current_term, "success": True}


class RequestVoteParams(BaseModel):
    term: int
    candidate_id: str
    last_log_index: int
    last_log_term: int


async def request_vote(raft_node: RaftNode, params: RequestVoteParams):
    async with raft_node.lock:
        term = params.term
        candidate_id = params.candidate_id
        candidate_last_log_index = params.last_log_index
        candidate_last_log_term = params.last_log_term
        logger.info(f"Received vote request from {candidate_id} for term {term}")

        if term < raft_node.current_term:
            logger.info(
                f"Rejecting vote request from {candidate_id} due to stale term {term}"
            )
            return {"term": raft_node.current_term, "vote_granted": False}

        if term > raft_node.current_term:
            raft_node.current_term = term
            raft_node.voted_for = None
            raft_node.state = RaftState.FOLLOWER

        if raft_node.voted_for not in (None, candidate_id):
            logger.info(
                f"Already voted for {raft_node.voted_for} in term {term}, rejecting {candidate_id}"
            )
            return {"term": raft_node.current_term, "vote_granted": False}

        # Check log up-to-dateness
        own_last_log_index = len(raft_node.log)
        own_last_log_term = raft_node.log[-1].term if raft_node.log else 0
        up_to_date = (candidate_last_log_term > own_last_log_term) or (
            candidate_last_log_term == own_last_log_term
            and candidate_last_log_index >= own_last_log_index
        )

        if not up_to_date:
            logger.info(
                f"Rejecting vote request from {candidate_id}, log not up-to-date"
            )
            return {"term": raft_node.current_term, "vote_granted": False}

        raft_node.voted_for = candidate_id
        raft_node.last_heartbeat = time.time()
        logger.info(f"Voted for {candidate_id} in term {term}")
        return {"term": raft_node.current_term, "vote_granted": True}


class TransferFilesParams(BaseModel):
    filename: str


async def transfer_file(raft_node: RaftNode, params: TransferFilesParams):
    filename = params.filename
    file = Path(os.path.join(FILE_DIRECTORY, filename))
    if not file.is_file():
        raise FileNotFoundError(f"File {filename} not found")
    with open(file, "rb") as fh:
        content = fh.read()
    return {"filename": filename, "content": str(base64.b64encode(content))}


rpc_methods = {
    "append_entries": (append_entries, AppendEntriesParams),
    "request_vote": (request_vote, RequestVoteParams),
    "transfer_file": (transfer_file, TransferFilesParams),
}


class RPCRequest(BaseModel):
    method: str
    params: dict[str, Any]


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
