""" Testing module for the Peer2Peer part
    of the blockchain client
"""

import socket
from queue import Queue

from peers import PeerManager


class TestPeers():
    """ Testcase used to bundle all test for the
        Peer2Peer module of the blockchain client
    """

    def setup_method(self):
        """ Setup PeerMananger for the tests
        """
        self.send_queue = Queue()
        self.peers = PeerManager()

        self.peers.setup(self.send_queue, 1234)

        while not self.send_queue.empty():
            self.send_queue.get_nowait()

    def test_self_address(self):
        """ Test the exclusion of the address
            of the current node
        """
        hostname = socket.gethostname()
        host_ip = socket.gethostbyname(hostname)
        self_address = [('127.0.0.1', 1234),
                        (host_ip, 1234)]
        for addr in self_address:
            self.peers.peer_seen(addr)

        assert all((addr not in self.peers.get_broadcast_peers())
                   for addr in self_address)

    def test_initial_ping(self):
        """ Test that new inferred peers are
            pinged
        """
        test_address = ('8.8.8.8', 5555)
        self.peers.peer_inferred(test_address)

        assert self.send_queue.get() == ('N_ping', '', test_address)

    def test_get_peers(self):
        """ Test that new seen/active peers are
            asked for their peers
        """
        test_address = ('8.8.8.8', 5555)
        self.peers.peer_seen(test_address)

        assert test_address in self.peers.get_active_peers()
        assert test_address in self.peers.get_all_peers()
        assert test_address in self.peers.get_broadcast_peers()

        assert self.send_queue.get() == ('N_get_peers', '', test_address)

    def test_initial_order(self):
        """ Test that the normal order of events
            (inferred->ping->seen) for a new peer
            works
        """
        test_address = ('8.8.8.8', 5555)

        self.peers.peer_inferred(test_address)

        assert test_address not in self.peers.get_active_peers()
        assert test_address in self.peers.get_all_peers()
        assert test_address in self.peers.get_broadcast_peers()

        # Expectation: Peer responded to ping

        self.peers.peer_seen(test_address)

        assert test_address in self.peers.get_active_peers()
        assert test_address in self.peers.get_all_peers()
        assert test_address in self.peers.get_broadcast_peers()
