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
    def __init__(self, node_id, peers, is_leader):
        self.node_id = node_id
        self.peers = peers
        self.state = RaftState.LEADER if is_leader else RaftState.FOLLOWER
        self.current_term = 0
        self.voted_for = None
        self.log = []
        self.commit_index = 0
        self.last_applied = 0
        self.next_index = {}
        self.match_index = {}
        self.election_timeout = random.randint(150, 300)
        self.heartbeat_timeout = 50
        self.last_heartbeat = time.time()
        self.last_election = time.time()
        self.votes = 0

    def send_request_vote(self, peer):
        pass
    
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

    def request_vote(self, message):
        pass

    def append_entries(self, message):
        pass

    def handle_message(self, message):
        pass

    def send_message(self, message):
        pass

    def run(self):
        print(self.state)

        # The leader node send either information about the new log entries or a heartbeat 
        # to all followers if no new log entries are available.
        if self.state == RaftState.LEADER:
            for peer in self.peers:
                self.send_append_entries(peer)

        # if current_time - self.last_heartbeat >= self.heartbeat_timeout:
        #     self.last_heartbeat = current_time
        #     for peer in self.peers:
        #         self.send_append_entries(peer)
        # elif current_time - self.last_election >= self.election_timeout:
        #     self.last_election = current_time
        #     self.start_election()

    def start_election(self):
        self.state = RaftState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self.votes = 1
        self.last_election = time.time()
        for peer in self.peers:
            self.send_request_vote(peer)

    def start(self):
        pass

    def stop(self):
        pass

    def on_election_timeout(self):
        pass

    def on_heartbeat_timeout(self):
        pass

    def on_vote_received(self):
        pass

    def on_append_entries_received(self):
        pass

    def on_majority_received(self):
        pass

    def on_majority_committed(self):
        pass

    def on_majority_applied(self):
        pass

    def on_majority_heartbeat(self):
        pass

    def on_majority_election(self):
        pass

    # def on_majority_vote
