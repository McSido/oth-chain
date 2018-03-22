""" Networking module for the blockchain client,
    contains all necessary functions to communicate with other clients
    in the blockchain network, as well as interpret incoming messages
"""

import pickle  # change for secure solution
# (https://docs.python.org/3/library/pickle.html?highlight=pickle#module-pickle)
import socket
import sys
import time
from pprint import pprint
from queue import Empty

from blockchain import Block, Transaction
from utils import print_debug_info

# Initialize
PORT = 6666
BUFFER_SIZE = 1024
peer_list = set()  # Known peers
active_peers = set()  # Active peers
unresponsive_peers = set()
self_address = set()
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def send_msg(msg_type, msg_data, address):
    """ Send message to address
    Arguments:
    msg_type -> Type of the message
    msg_data -> Data of the message
    address  -> Address to send message to
    """

    message = pack_msg((msg_type, msg_data))

    if len(message) < BUFFER_SIZE:
        # Simple message
        server_socket.sendto(b'0' + message, address)
    else:
        # Longer message (maybe work with bytes send?)
        index = (BUFFER_SIZE-1) - 1
        # Send first part
        server_socket.sendto(b'1' + message[0:index], address)
        # Send intermediate parts
        while index + (BUFFER_SIZE-1) < len(message):
            server_socket.sendto(
                b'2' + message[index:index+(BUFFER_SIZE-1)], address)
            index += (BUFFER_SIZE-1)
        # Send last part
        server_socket.sendto(b'3' + message[index:], address)


def broadcast(msg_type, msg_data):
    """ Send message to all connected peers
    Arguments:
    msg_type -> Type of the message
    msg_data -> Data of the message
    """

    if len(active_peers) == 0:
        # If no active peers, try messaging everyone
        for peer in peer_list:
            if peer not in self_address:
                send_msg(msg_type, msg_data, peer)

    for peer in active_peers:
        if peer not in self_address:
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
            active_peers.add(in_address)
            try:
                unresponsive_peers.remove(in_address)
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
    for peer in peer_list:
        send_msg('N_new_peer', peer, address)


def new_peer(address):
    """ Process a new peer
    New peer is broadcast to all known peers and added to peerlist
    Arguments:
    address -> Address of the new peer
    """
    if (address not in self_address and
            address not in active_peers.union(unresponsive_peers)):
        broadcast('N_new_peer', address)
        get_peers(address)  # Send known peers to new peer
        peer_list.add(address)
        unresponsive_peers.add(address)
        send_msg('N_ping', '', address)  # check if peer is active


def ping_peers():
    """ Ping all peers in peer_list
    """
    for p in peer_list:
        if p not in self_address:
            unresponsive_peers.add(p)
            send_msg('N_ping', '', p)


def load_initial_peers():
    """ Load initial peers from peers.cfg file
        and add current addresses to self_address
    """
    # TODO: check for validity (IP-address PORT)
    with open('./peers.cfg') as f:
        for peer in f:
            p = peer.split(' ')
            assert len(p) == 2
            peer_list.add((p[0], int(p[1])))

    self_address.add(('127.0.0.1', PORT))
    hostname = socket.gethostname()
    IP = socket.gethostbyname(hostname)
    self_address.add((IP, PORT))


def example_worker(send_queue, receive_queue, command_queue):
    """ Simple example of a networker
    Arguments:
    send_queue -> Queue for messages to other nodes
    receive_queue -> Queue for messages to the attached blockchain
    """
    # Setup peers
    global active_peers
    load_initial_peers()
    ping_peers()
    counter = 0
    received_data = {}

    # Main loop
    while True:
        try:
            cmd = command_queue.get(block=False)
            if cmd == 'print_peers':
                print('all peers:')
                pprint(peer_list)
                print('active peers:')
                pprint(active_peers)
        except Empty:
            pass
        try:
            msg = send_queue.get(block=False)
            if msg is None:
                server_socket.close()
                sys.exit()
            msg_out_type, msg_out_data, msg_out_address = msg
        except Empty:
            pass
        else:
            if msg_out_address == 'broadcast':
                broadcast(msg_out_type, msg_out_data)
            else:
                send_msg(msg_out_type, msg_out_data, msg_out_address)

        try:
            msg_in, address = server_socket.recvfrom(BUFFER_SIZE)
            if msg_in[0:1] == b'0':
                # unsplit message
                received_data[address] = (True, msg_in[1:])
            elif msg_in[0:1] == b'1':
                # beginning of split message
                if address in received_data.keys():
                    # remove old unfinished message
                    received_data.pop(address)
                received_data[address] = (False, msg_in[1:])
            elif msg_in[0:1] == b'2':
                # middle of split message
                if (address in received_data.keys() and
                        received_data[address][0] is False):
                    received_data[address] = (
                        False, received_data[address][1]+msg_in[1:])
            elif msg_in[0:1] == b'3':
                # end of split message
                if (address in received_data.keys() and
                        received_data[address][0] is False):
                    received_data[address] = (
                        True, received_data[address][1]+msg_in[1:])
            else:
                # No useful message
                if address in received_data.keys():
                    # remove old unfinished message
                    received_data.pop(address)
                continue

            # print(received_data.items())
            # check for finished message
            for ad, (finished, msg) in received_data.items():
                # print(ad, finished, msg)
                if finished:
                    process_incoming_msg(msg, ad, receive_queue)
                    received_data.pop(ad)
                    break  # Only 1 message should be finished per cycle

        except socket.error:
            pass
        else:
            # Add unknown node
            if address not in active_peers:
                new_peer(address)

        if counter == 100*10:  # ~ 10-20 sec
            active_peers = peer_list.difference(unresponsive_peers)
            unresponsive_peers.clear()
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

    global PORT
    PORT = port
    server_socket.bind(('', PORT))
    server_socket.settimeout(0.01)

    example_worker(send_queue, receive_queue, command_queue)
