""" PeerManagement module for the blockchain client

"""
import ipaddress
import os
import socket
import time


class PeerManager():
    def __init__(self):
        self._peer_list = set()
        self._last_seen = {}
        self._active_peers = set()
        self._self_addresses = set()
        self._send_queue = None

    def setup(self, send_queue, port):
        self._send_queue = send_queue
        self._init_peers(port)

    def _init_peers(self, port):
        self._self_addresses.add(('127.0.0.1', port))
        hostname = socket.gethostname()
        host_ip = socket.gethostbyname(hostname)
        self._self_addresses.add((host_ip, port))

        self._load_initial_peers()

    def _load_initial_peers(self):
        """ Load initial peers from peers.cfg file

            Creates peers.cfg if it doesn't exist
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
        cur_time = time.time()
        to_remove = set()

        for addr in self._active_peers:
            if cur_time - self._last_seen[addr] > 60:
                to_remove.add(addr)
                self._send_queue.put(('N_ping', '', addr))

        for addr in to_remove:
            self._active_peers.discard(addr)

    def get_broadcast_peers(self):
        self._update_active_peers()

        if not self._active_peers:
            return self._peer_list
        return self._active_peers

    def peer_inferred(self, address):
        if address in self._self_addresses:
            return
        if address not in self._peer_list:
            self._peer_list.add(address)
            self._send_queue.put(('N_ping', '', address))

    def peer_seen(self, address):
        if address in self._self_addresses:
            return
        if address not in self._active_peers:
            self._peer_list.add(address)
            self._active_peers.add(address)
            self._send_queue.put(('N_get_peers', '', address))

        self._last_seen[address] = time.time()

    def get_all_peers(self):
        return self._peer_list

    def get_active_peers(self):
        return self._active_peers
