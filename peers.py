""" PeerManagement module for the blockchain client.
"""
import ipaddress
import os
import socket
import time


class PeerManager():
    """ PeerManager that handles all aspects of the Peer2Peer connections.

    Call setup() before use.
    """

    def __init__(self):
        self._peer_list = set()
        self._last_seen = {}
        self._active_peers = set()
        self._self_addresses = set()
        self._send_queue = None

    def setup(self, send_queue, port):
        """ Setup PeerManager.

        Loads initial peers from peers.cfg, creates the file if needed.

        Args:
            send_queue: Queue for messaging other nodes.
            port: Port of the node.
        """
        self._send_queue = send_queue
        self._init_peers(port)

    def _init_peers(self, port):
        """ Initialize peers.

        Arguments:
            port: Port of the node.
        """
        self._self_addresses.add(('127.0.0.1', port))
        hostname = socket.gethostname()
        host_ip = socket.gethostbyname(hostname)
        self._self_addresses.add((host_ip, port))

        self._load_initial_peers()

    def _load_initial_peers(self):
        """ Load initial peers from peers.cfg file.

        Creates peers.cfg if it doesn't exist.
        """
        if not os.path.exists('./peers.cfg'):
            print("Could not find peers.cfg\nUpdated with defaults")
            with open('./peers.cfg', 'w') as peers_file:
                peers_file.write("127.0.0.1 6666\n")
                peers_file.write("127.0.0.1 6667")
                # Change to valid default peers

        with open('./peers.cfg') as peers_cfg:
            for peer in peers_cfg:
                addr = peer.split(' ')
                try:
                    assert len(addr) == 2
                    ipaddress.ip_address(addr[0])  # Check valid IP
                    if int(addr[1]) > 65535:  # Check valid port
                        raise ValueError
                except (ValueError, AssertionError):
                    pass
                else:
                    self.peer_inferred((addr[0], int(addr[1])))

    def _update_active_peers(self):
        """ Check for inactive peers.

        inactive:  > 60 sec between messages

        Pings inactive peers and removes them from the active peers list.
        """
        cur_time = time.time()
        to_remove = set()

        for addr in self._active_peers:
            if cur_time - self._last_seen[addr] > 60:
                to_remove.add(addr)
                self._send_queue.put(('N_ping', '', addr))

        for addr in to_remove:
            self._active_peers.discard(addr)

    def get_broadcast_peers(self):
        """ Get the peers that sould receive broadcast messages.

        Returns:
            List of addresses for broadcast use.
        """
        self._update_active_peers()

        if not self._active_peers:
            return self._peer_list
        return self._active_peers

    def peer_inferred(self, address):
        """ Add new inferred peer

        Infer peers by e.g. receiving 'N_new_peer' messages.

        Puts ping message on send_queue to receive confirmation.

        Args:
            address: Address of peer.
        """
        if address in self._self_addresses:
            return
        if address not in self._peer_list:
            self._peer_list.add(address)
            self._send_queue.put(('N_ping', '', address))

    def peer_seen(self, address):
        """ Add new seen/active peer

        Seen/Active peer is a peer that directly messaged this node.

        Puts message on send_queue to receive additional peers
        from the new peer.

        Args:
            address: Address of peer.
        """
        if address in self._self_addresses:
            return
        if address not in self._active_peers:
            self._peer_list.add(address)
            self._active_peers.add(address)
            self._send_queue.put(('N_get_peers', '', address))

        self._last_seen[address] = time.time()

    def get_all_peers(self):
        """ Get all peers.

        For information only!
        Use get_broadcast_peers() instead.

        Returns:
            List of all peers.
        """
        return self._peer_list

    def get_active_peers(self):
        """ Get active peers.

        For information only!
        Use get_broadcast_peers() instead.

        Returns:
            List of active peers.
        """
        return self._active_peers
