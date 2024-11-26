from enum import Enum
import random
import requests
import time


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
        response = requests.get(f"http://{peer}/ping")
        print(response.json(), response.status_code)

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
        while True:
            current_time = time.time()
            if self.state == RaftState.LEADER:
                for peer in self.peers:
                    self.send_append_entries(peer)
            time.sleep(1)

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
