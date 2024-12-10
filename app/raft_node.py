import asyncio
import base64
import json
import os
from pathlib import Path
import time
import random
from enum import Enum
import httpx
from kubernetes import client, config
from redis import Redis

from .constants import FILE_DIRECTORY
from .logger import logger


class LogEntry:
    def __init__(self, term: int, index: int, command: dict):
        self.term = term
        self.index = index
        self.command = command

    def to_dict(self):
        return {"term": self.term, "index": self.index, "command": self.command}

    @classmethod
    def from_json(cls, json_string: str):
        try:
            entry = json.loads(json_string)
            return cls(entry["term"], entry["index"], entry["command"])
        except KeyError as e:
            logger.error(f"Missing key in JSON string: {e}", exc_info=True)
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON string: {e}", exc_info=True)
            return None

    def __repr__(self):
        return json.dumps(self.to_dict())


class RaftState(Enum):
    LEADER = 0
    FOLLOWER = 1
    CANDIDATE = 2


class RaftNode:
    def __init__(self, node_id: str, peers: list[str], redis: Redis):
        self.node_id = node_id
        self.peers = [
            peer
            for peer in peers
            if peer
            not in [
                f"app-{self.node_id}:8000",
                f"distributed-filesystem-node-{self.node_id}:8080",
            ]
        ]
        self.state = RaftState.FOLLOWER
        self.current_term = 0
        self.voted_for = None
        self.log: list[LogEntry] = []
        self.last_heartbeat = time.time()
        self.election_timeout = random.uniform(1.5, 3.0)
        self.heartbeat_interval = 0.5
        self.votes_received = 0
        self.lock = asyncio.Lock()
        self.redis = redis
        self.commit_index = 0
        self.last_applied = 0
        self.next_index = {}
        self.match_index = {}
        self.leader_address: str | None = None

    async def send_request_vote(self, peer: str):
        async with self.lock:
            term = self.current_term
        try:
            rpc_payload = {
                "method": "request_vote",
                "params": {
                    "term": term,
                    "candidate_id": self.node_id,
                    "last_log_index": len(self.log),
                    "last_log_term": self.log[-1].term if self.log else 0,
                },
            }
            async with httpx.AsyncClient() as http_client:
                response = await http_client.post(
                    f"http://{peer}/rpc", json=rpc_payload, timeout=5
                )
            if response.status_code == 200:
                response_json = response.json()
                resp_term = response_json.get("result", {}).get("term")
                if resp_term > term:
                    async with self.lock:
                        self.current_term = resp_term
                        self.state = RaftState.FOLLOWER
                        self.voted_for = None
                        self.last_heartbeat = time.time()
                    logger.info(
                        f"Stepping down to follower due to higher term from {peer}"
                    )
                    return
                if response_json.get("result", {}).get("vote_granted"):
                    async with self.lock:
                        self.votes_received += 1
                        votes = self.votes_received
                        total_nodes = len(self.peers) + 1
                    logger.info(f"Received vote from {peer}")
                    if votes > total_nodes // 2:
                        await self.become_leader()
            else:
                logger.error(
                    f"Error from {peer}: {response.text} ({response.status_code})",
                    exc_info=True,
                )
        except httpx.RequestError as e:
            logger.error(f"Error contacting {peer}: {e}", exc_info=False)

    async def send_append_entries(self, peer: str):
        async with self.lock:
            if self.state != RaftState.LEADER:
                return

            next_index = self.next_index[peer]
            prev_log_index = next_index - 1
            prev_log_term = (
                self.log[prev_log_index - 1].term if prev_log_index > 0 else 0
            )

            entries_to_send = []
            if next_index <= len(self.log):
                entries_to_send = [
                    {
                        "term": entry.term,
                        "index": entry.index,
                        "command": entry.command,
                    }
                    for entry in self.log[prev_log_index:]
                ]
            rpc_payload = {
                "method": "append_entries",
                "params": {
                    "term": self.current_term,
                    "leader_id": self.node_id,
                    "prev_log_index": prev_log_index,
                    "prev_log_term": prev_log_term,
                    "entries": entries_to_send,
                    "leader_commit": self.commit_index,
                },
            }
        try:
            async with httpx.AsyncClient() as http_client:
                response = await http_client.post(
                    f"http://{peer}/rpc", json=rpc_payload, timeout=5
                )
            if response.status_code == 200:
                response_json = response.json()
                success = response_json.get("result", {}).get("success", False)
                term = response_json.get("result", {}).get("term", 0)

                async with self.lock:
                    if term > self.current_term:
                        self.state = RaftState.FOLLOWER
                        self.current_term = term
                        self.voted_for = None
                        logger.info(
                            f"Stepping down to follower due to higher term from {peer}"
                        )
                        return
                    if success:
                        # Advance nextIndex and matchIndex for that follower
                        if entries_to_send:
                            self.match_index[peer] = entries_to_send[-1]["index"]
                            self.next_index[peer] = entries_to_send[-1]["index"] + 1
                        else:
                            # If no entries were sent, just ensure nextIndex isn't stuck
                            if self.next_index[peer] < len(self.log) + 1:
                                self.next_index[peer] = len(self.log) + 1
                        # Check if we can advance commit_index
                        await self.update_commit_index()
                    else:
                        self.next_index[peer] = max(1, self.next_index[peer] - 1)
                        asyncio.create_task(self.send_append_entries(peer))
            else:
                logger.error(
                    f"Error from {peer}: {response.text} ({response.status_code})",
                    exc_info=True,
                )
        except httpx.RequestError as e:
            logger.error(f"Error contacting {peer}: {e}", exc_info=False)

    async def update_commit_index(self):
        """
        Updates the commit index if a majority of servers have replicated an entry.
        """
        for i in range(self.commit_index + 1, len(self.log) + 1):
            count = 1  # Leader counts as one
            for peer in self.peers:
                if self.match_index[peer] >= i:
                    count += 1
            if (
                count > (len(self.peers) + 1) // 2
                and self.log[i - 1].term == self.current_term
            ):
                self.commit_index = i
        await self.apply_entries()

    async def apply_entries(self):
        """
        Asynchronously applies log entries (i.e. saves them into log stored in Redis)
        up to the commit index. If the node is a follower and the file is missing,
        it will fetch the file from the leader.
        """
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            entry = self.log[self.last_applied - 1]
            filename = entry.command["filename"]
            file_path = Path(os.path.join(FILE_DIRECTORY, filename))
            if self.state == RaftState.FOLLOWER and not file_path.is_file():
                await self.fetch_file_from_leader(filename)
            await self.redis.rpush("raft_log", str(entry))

    # TODO: Retry fetching the file if the first attempt fails
    async def fetch_file_from_leader(self, filename: str):
        if not self.leader_address:
            return
        rpc_payload = {
            "method": "transfer_file",
            "params": {"filename": filename},
        }
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                f"http://{self.leader_address}/rpc", json=rpc_payload, timeout=10
            )
        if response.status_code == 200:
            response_json = response.json()
            file_data = response_json.get("result", {})
            if file_data:
                content = base64.b64decode(file_data["content"][1:-1])
                file_path = os.path.join(FILE_DIRECTORY, file_data["filename"])
                with open(file_path, "wb") as fh:
                    fh.write(content)
                logger.info(f"Successfully fetched file {filename} from leader")
                return True
        else:
            logger.error(f"Failed to fetch file {filename} from leader")

    async def run(self):
        async with self.lock:
            current_time = time.time()
            state = self.state
            term = self.current_term
        logger.debug(f"Node {self.node_id} in state {state} at term {term}")
        if state == RaftState.LEADER:
            async with self.lock:
                self.last_heartbeat = current_time
            for peer in self.peers:
                asyncio.create_task(self.send_append_entries(peer))
        else:
            async with self.lock:
                time_since_heartbeat = current_time - self.last_heartbeat
                election_timeout = self.election_timeout
            if time_since_heartbeat >= election_timeout:
                logger.info(
                    f"No heartbeat received for {election_timeout} seconds, starting election"
                )
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
        logger.info(f"Node {self.node_id} starting election for term {term}")
        for peer in self.peers:
            await self.send_request_vote(peer)

    async def become_leader(self):
        async with self.lock:
            self.state = RaftState.LEADER
            last_log_index = len(self.log)
            self.next_index = {peer: last_log_index + 1 for peer in self.peers}
            self.match_index = {peer: 0 for peer in self.peers}
        logger.info(f"Node {self.node_id} became leader in term {self.current_term}")
        await self.update_leader_k8s()

    async def add_command(self, command):
        async with self.lock:
            new_entry = LogEntry(self.current_term, len(self.log) + 1, command)
            self.log.append(new_entry)
            for peer in self.peers:
                asyncio.create_task(self.send_append_entries(peer))

    async def update_leader_k8s(self):
        try:
            config.load_incluster_config()
            route_v1 = client.CustomObjectsApi()

            namespace = "ohtuprojekti-staging"
            route_name = "distributed-filesystem-route"

            # Update Route
            route = route_v1.get_namespaced_custom_object(
                group="route.openshift.io",
                version="v1",
                namespace=namespace,
                plural="routes",
                name=route_name,
            )
            route["spec"]["to"]["name"] = f"distributed-filesystem-node-{self.node_id}"
            route_v1.patch_namespaced_custom_object(
                group="route.openshift.io",
                version="v1",
                namespace=namespace,
                plural="routes",
                name=route_name,
                body=route,
            )
            logger.info(
                f"Updated Route {route_name} to point to distributed-filesystem-node-{self.node_id}"
            )
        except config.ConfigException as e:
            logger.error(f"ConfigException: {e}")
            logger.info("Not running in a Kubernetes cluster, skipping leader update")
        except client.exceptions.ApiException as e:
            logger.error(f"ApiException: {e}", exc_info=True)
            logger.error(
                f"Failed to update Route {route_name} in namespace {namespace}",
                exc_info=True,
            )
        except Exception as e:
            logger.error(f"Unexpected exception: {e}", exc_info=True)
