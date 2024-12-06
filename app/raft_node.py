import asyncio
import base64
import os
import time
import random
from enum import Enum
import httpx
from .routes import FILE_DIRECTORY


class LogEntry:
    def __init__(self, term, command):
        self.term = term
        self.command = command

    def __repr__(self):
        return f"LogEntry(term={self.term}, command={self.command})"


class RaftState(Enum):
    LEADER = 0
    FOLLOWER = 1
    CANDIDATE = 2


class RaftNode:
    def __init__(self, node_id: str, peers: list[str], redis):
        self.node_id = node_id
        self.peers = [peer for peer in peers if peer != f"app-{self.node_id}:8000" and peer != f"distributed-filesystem-node-{self.node_id}:8080"]
        self.state = RaftState.FOLLOWER
        self.current_term = 0
        self.voted_for = None
        self.log = []
        self.last_heartbeat = time.time()
        self.election_timeout = random.uniform(1.5, 3.0)
        self.heartbeat_interval = 0.5
        self.votes_received = 0
        self.lock = asyncio.Lock()
        self.redis = redis

    async def send_request_vote(self, peer):
        async with self.lock:
            term = self.current_term
        try:
            rpc_payload = {
                "method": "request_vote",
                "params": {
                    "term": term,
                    "candidate_id": self.node_id,
                },
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(f"http://{peer}/rpc", json=rpc_payload, timeout=5)
            if response.status_code == 200:
                response_json = response.json()
                resp_term = response_json.get("result", {}).get("term")
                if resp_term > term:
                    async with self.lock:
                        self.current_term = resp_term
                        self.state = RaftState.FOLLOWER
                        self.voted_for = None
                        self.last_heartbeat = time.time()
                    print(f"Stepping down to follower due to higher term from {peer}")
                    return
                if response_json.get("result", {}).get("vote_granted"):
                    async with self.lock:
                        self.votes_received += 1
                        votes = self.votes_received
                        total_nodes = len(self.peers) + 1
                    print(f"Received vote from {peer}")
                    if votes > total_nodes // 2:
                        await self.become_leader()
            else:
                print(f"Error from {peer}: {response.text} ({response.status_code})")
        except httpx.RequestError as e:
            print(f"Error contacting {peer}: {e}")

    async def send_append_entries(self, peer):
        async with self.lock:
            term = self.current_term
        try:
            rpc_payload = {
                "method": "heartbeat",
                "params": {
                    "term": term,
                    "log": self.log,
                },
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(f"http://{peer}/rpc", json=rpc_payload, timeout=5)
            if response.status_code == 200:
                response_json = response.json()
                resp_term = response_json.get("result", {}).get("term")
                resp_update_files = response_json.get("result", {}).get("update_files", [])
                if resp_term > term:
                    async with self.lock:
                        self.current_term = resp_term
                        self.state = RaftState.FOLLOWER
                        self.voted_for = None
                        self.last_heartbeat = time.time()
                    print(f"Stepping down to follower due to higher term from {peer}")
                if len(resp_update_files) > 0:
                    rpc_payload = {
                        "method": "transfer_files",
                        "params": {"files": []},
                    }
                    files = []
                    for key in resp_update_files:
                        metadata = await self.redis.hgetall(key)
                        file_name = metadata.get("filename")
                        file_path = os.path.join(FILE_DIRECTORY, file_name)
                        with open(file_path, "rb") as fh:
                            content = fh.read()
                        file = {
                            "filename": file_name,
                            "content_type": metadata.get("content_type"),
                            "content": str(base64.b64encode(content)),
                            "hash": key,
                        }
                        files.append(file)
                    rpc_payload["params"]["files"] = files
                    async with httpx.AsyncClient() as client:
                        await client.post(f"http://{peer}/rpc", json=rpc_payload, timeout=5)
            else:
                print(f"Error from {peer}: {response.text} ({response.status_code})")
        except httpx.RequestError as e:
            print(f"Error contacting {peer}: {e}")

    async def run(self):
        async with self.lock:
            current_time = time.time()
            state = self.state
            term = self.current_term
        print(f"Node {self.node_id} in state {state} at term {term}")
        await self.append_entries()
        if state == RaftState.LEADER:
            async with self.lock:
                self.last_heartbeat = current_time
            for peer in self.peers:
                await self.send_append_entries(peer)
        else:
            async with self.lock:
                time_since_heartbeat = current_time - self.last_heartbeat
                election_timeout = self.election_timeout
            if time_since_heartbeat >= election_timeout:
                print(f"No heartbeat received for {election_timeout} seconds, starting election")
                await self.start_election()

    async def start_election(self):
        async with self.lock:
            self.state = RaftState.CANDIDATE
            self.current_term += 1
            self.voted_for = self.node_id
            self.votes_received = 1
            self.election_timeout = random.uniform(1.5, 3.0)
            self.last_heartbeat = time.time()
            term = self.current_term
        print(f"Node {self.node_id} starting election for term {term}")
        for peer in self.peers:
            await self.send_request_vote(peer)

    async def become_leader(self):
        async with self.lock:
            self.state = RaftState.LEADER
        print(f"Node {self.node_id} became leader in term {self.current_term}")

    async def append_entries(self):
        keys = await self.redis.keys("*")
        self.log = keys
