from enum import Enum

import time
import random
import requests

from requests.exceptions import RequestException


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
    def __init__(self, node_id, peers):
        self.node_id = node_id
        self.peers = peers
        self.state = RaftState.FOLLOWER
        self.current_term = 0
        self.voted_for = None
        self.log = []
        self.election_timeout = random.randint(150, 300)
        self.heartbeat_timeout = 50
        self.last_heartbeat = time.time()
        self.last_election = time.time()
        self.votes = 0

    def send_append_entries(self, peer):
        """
        Send log entries or heartbeat to a peer.
        """
        if self.state != RaftState.LEADER:
            return

        message = LogEntry(self.current_term, self.log)

        try:
            response = requests.post(f"http://{peer}/append_entries", json=message)
            print(f"AppendEntries sent to {peer}, response: {response.json()}")
        except RequestException as e:
            print(f"Error contacting {peer}: {e}")

    def run(self):
        # The leader node send either information about the new log entries or a heartbeat
        # to all followers if no new log entries are available.
        if self.state == RaftState.LEADER:
            for peer in self.peers:
                self.send_append_entries(peer)

    def start_election(self):
        self.state = RaftState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self.votes = 1
        self.last_election = time.time()
        for peer in self.peers:
            self.send_request_vote(peer)
