""" Networking module for the blockchain client,
    contains all necessary functions to communicate with other clients
    in the blockchain network, as well as interpret incoming messages
"""

import ipaddress
import os
import pickle  # change for secure solution
# (https://docs.python.org/3/library/pickle.html?highlight=pickle#module-pickle)
import socket
import sys
import time
from pprint import pprint
from queue import Empty

from ext_udp import ExtendedUDP
from utils import print_debug_info

# Initialize
PEER_LIST = set()  # Known peers
ACTIVE_PEERS = set()  # Active peers
UNRESPONSIVE_PEERS = set()
SELF_ADDRESS = set()
SERVER = ExtendedUDP(1024)


def send_msg(msg_type, msg_data, address):
    """ Send message to address
    Arguments:
    msg_type -> Type of the message
    msg_data -> Data of the message
    address  -> Address to send message to
    """

    message = pack_msg((msg_type, msg_data))

    SERVER.send_msg(message, address)


def broadcast(msg_type, msg_data):
    """ Send message to all connected peers
    Arguments:
    msg_type -> Type of the message
    msg_data -> Data of the message
    """

    if not ACTIVE_PEERS:
        # If no active peers, try messaging everyone
        for peer in PEER_LIST:
            if peer not in SELF_ADDRESS:
                send_msg(msg_type, msg_data, peer)

    for peer in ACTIVE_PEERS:
        if peer not in SELF_ADDRESS:
            send_msg(msg_type, msg_data, peer)


def unpack_msg(msg):
    """ Deserialize a message
    Arguments:
    msg -> Message to unpack
    """
    return pickle.loads(msg)


def pack_msg(msg):
    """ Serialize a message
    Arguments:
    msg -> Message to serialize
    """
    return pickle.dumps(msg)


def process_incoming_msg(msg, in_address, receive_queue):
    """ Process messages received from other nodes
    Arguments:
    msg -> Received message
    in_address -> Address of the sender
    receive_queue -> Queue for communication with the blockchain
    """
    try:
        msg_type, msg_data = unpack_msg(msg)
    except ValueError as err:
        print_debug_info(f'### DEBUG ### Received invalid message\n {err}')
        return

    print_debug_info('### DEBUG ### received: ' + msg_type)
    if msg_type.startswith('N_'):
        # networking messages
        if msg_type == 'N_new_peer':
            new_peer(msg_data)
        elif msg_type == 'N_get_peers':
            get_peers(in_address)
        elif msg_type == 'N_ping':
            send_msg('N_pong', '', in_address)
        elif msg_type == 'N_pong':
            ACTIVE_PEERS.add(in_address)
            try:
                UNRESPONSIVE_PEERS.remove(in_address)
            except KeyError:
                pass
    else:
        # blockchain messages

        receive_queue.put((msg_type, msg_data, in_address))


def get_peers(address):
    """ Send all known peers
    Arguments:
    address -> Address to send peers to
    """
    for peer in PEER_LIST:
        send_msg('N_new_peer', peer, address)


def new_peer(address):
    """ Process a new peer
    New peer is broadcast to all known peers and added to peerlist
    Arguments:
    address -> Address of the new peer
    """
    if (address not in SELF_ADDRESS and
            address not in ACTIVE_PEERS.union(UNRESPONSIVE_PEERS)):
        broadcast('N_new_peer', address)
        get_peers(address)  # Send known peers to new peer
        PEER_LIST.add(address)
        UNRESPONSIVE_PEERS.add(address)
        send_msg('N_ping', '', address)  # check if peer is active


def ping_peers():
    """ Ping all peers in peer_list
    """
    for peer in PEER_LIST:
        if peer not in SELF_ADDRESS:
            UNRESPONSIVE_PEERS.add(peer)
            send_msg('N_ping', '', peer)


def load_initial_peers():
    """ Load initial peers from peers.cfg file
        and add current addresses to self_address
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
                PEER_LIST.add((addr[0], int(addr[1])))

    SELF_ADDRESS.add(('127.0.0.1', SERVER.port))
    hostname = socket.gethostname()
    IP = socket.gethostbyname(hostname)
    SELF_ADDRESS.add((IP, SERVER))


def example_worker(send_queue, receive_queue, command_queue):
    """ Simple example of a networker
    Arguments:
    send_queue -> Queue for messages to other nodes
    receive_queue -> Queue for messages to the attached blockchain
    """
    # Setup peers
    load_initial_peers()
    ping_peers()
    counter = 0

    # Main loop
    while True:
        try:
            cmd = command_queue.get(block=False)
            if cmd == 'print_peers':
                print('all peers:')
                pprint(PEER_LIST)
                print('active peers:')
                pprint(ACTIVE_PEERS)
        except Empty:
            pass
        try:
            msg = send_queue.get(block=False)
            if msg is None:
                SERVER.teardown()
                sys.exit()
            msg_out_type, msg_out_data, msg_out_address = msg
        except Empty:
            pass
        else:
            if msg_out_address == 'broadcast':
                broadcast(msg_out_type, msg_out_data)
            else:
                send_msg(msg_out_type, msg_out_data, msg_out_address)

        received = SERVER.receive_msg()
        if received:
            process_incoming_msg(received[0], received[1], receive_queue)
            # Add unknown node
            if received[1] not in ACTIVE_PEERS:
                new_peer(received[1])

        if counter == 100*10:  # ~ 10-20 sec
            ACTIVE_PEERS.clear()
            ACTIVE_PEERS.update(PEER_LIST.difference(UNRESPONSIVE_PEERS))
            UNRESPONSIVE_PEERS.clear()
        elif counter == 100*60:  # ~ 1-2 min
            ping_peers()
            counter = 0

        counter += 1

        time.sleep(0.01)  # Maybe use threading.Event()
        # (https://stackoverflow.com/questions/29082268/python-time-sleep-vs-event-wait)


def worker(send_queue, receive_queue, command_queue, port=6666):
    """ Takes care of the communication between nodes
    Arguments:
    send_queue -> Queue for messages to other nodes
    receive_queue -> Queue for messages to the attached blockchain
    """
    print_debug_info("### DEBUG ### Started networking")
    # Example:
    # Find peers
    # Main loop:
    # - check send_queue (send new messages)
    # - check incoming messages
    #   -- Networking message (e.g. new peer, get peers)
    #   -- Blockchain message: put on receive_queue

    SERVER.setup(port)

    example_worker(send_queue, receive_queue, command_queue)
