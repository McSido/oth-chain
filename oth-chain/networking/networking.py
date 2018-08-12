""" Networking module for the blockchain client.

Contains all necessary functions to communicate with other clients
in the blockchain network, as well as interpret incoming messages
"""


import pickle  # change for secure solution
import sys
import time
from pprint import pprint
from queue import Empty, Queue
from typing import Any, Tuple

from .ext_udp import ExtendedUDP
from .peers import PeerManager
from utils import print_debug_info

# (https://docs.python.org/3/library/pickle.html?highlight=pickle#module-pickle)

Address = Tuple[str, int]

# Initialize
PEERS = PeerManager()
SERVER = ExtendedUDP(1024)


def send_msg(msg_type: str, msg_data: Any, address: Address):
    """ Send message to address.

Args:
    msg_type: Type of the message
    msg_data: Data of the message
    address: Address to send message to
    """

    message = pack_msg((msg_type, msg_data))

    SERVER.send_msg(message, address)


def broadcast(msg_type: str, msg_data: Any):
    """ Send message to all connected peers.

    Args:
        msg_type: Type of the message.
        msg_data: Data of the message.
    """
    for peer in PEERS.get_broadcast_peers():
        send_msg(msg_type, msg_data, peer)


def unpack_msg(msg: bytes) -> Tuple[str, Any]:
    """ Deserialize a message.

    Args:
        msg: Message to unpack.

    Returns:
        Unpacked message.
    """
    return pickle.loads(msg)


def pack_msg(msg: Tuple[str, Any]) -> bytes:
    """ Serialize a message.

    Args:
        msg: Message to serialize

    Returns:
        Packed message.
    """
    return pickle.dumps(msg)


def process_incoming_msg(msg: bytes, in_address: Address,
                         receive_queue: Queue):
    """ Process messages received from other nodes

    Args:
        msg: Received message
        in_address: Address of the sender
        receive_queue: Queue for communication with the blockchain
    """
    try:
        msg_type, msg_data = unpack_msg(msg)
    except ValueError as err:
        print_debug_info(f'Received invalid message\n {err}')
        return

    PEERS.peer_seen(in_address)

    print_debug_info('received: ' + msg_type)
    if msg_type.startswith('N_'):
        # networking messages
        if msg_type == 'N_new_peer':
            PEERS.peer_inferred(msg_data)
        elif msg_type == 'N_get_peers':
            get_peers(in_address)
        elif msg_type == 'N_ping':
            send_msg('N_pong', '', in_address)
        elif msg_type == 'N_pong':
            pass  # Only needed for peer update. Ignore!
    else:
        # blockchain messages

        receive_queue.put((msg_type, msg_data, in_address))


def get_peers(address: Address):
    """ Send all known peers.

    Args:
        address: Address to send peers to.
    """
    for peer in PEERS.get_all_peers():
        send_msg('N_new_peer', peer, address)


def example_worker(send_queue: Queue,
                   receive_queue: Queue,
                   command_queue: Queue):
    """ Simple example of a networker.

    Args:
        send_queue: Queue for messages to other nodes.
        receive_queue: Queue for messages to the attached blockchain.
    """

    # Main loop
    while True:
        try:
            cmd = command_queue.get(block=False)
            if cmd == 'print_peers':
                print('all peers:')
                pprint(PEERS.get_all_peers())
                print('active peers:')
                pprint(PEERS.get_active_peers())
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

        time.sleep(0.01)  # Maybe use threading.Event()
        # (https://stackoverflow.com/questions/29082268/python-time-sleep-vs-event-wait)


def worker(send_queue: Queue,
           receive_queue: Queue,
           command_queue: Queue,
           gui_queue: Queue,
           port: int = 6666):
    """ Takes care of the communication between nodes.

    Args:
        send_queue: Queue for messages to other nodes.
        receive_queue: Queue for messages to the attached blockchain.
    """
    print_debug_info("Started networking")
    # Example:
    # Find peers
    # Main loop:
    # - check send_queue (send new messages)
    # - check incoming messages
    #   -- networking message (e.g. new peer, get peers)
    #   -- Blockchain message: put on receive_queue

    SERVER.setup(port)
    PEERS.setup(send_queue, gui_queue, port)

    example_worker(send_queue, receive_queue, command_queue)
