import pickle  # change for secure solution
# (https://docs.python.org/3/library/pickle.html?highlight=pickle#module-pickle)
import socket
import time
import sys
from queue import Empty

from blockchain import Block, Transaction

# Initialize
PORT = 6666
peer_list = set()
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def send_msg(msg_type, msg_data, address):
    """ Send message to address
    Arguments:
    msg_type -> Type of the message
    msg_data -> Data of the message
    address  -> Address to send message to
    """
    server_socket.sendto(
        pack_msg((msg_type, msg_data)),
        address
    )


def broadcast(msg_type, msg_data):
    """ Send message to all connected peers
    Arguments:
    msg_type -> Type of the message
    msg_data -> Data of the message
    """
    for peer in peer_list:
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
    msg_type, msg_data = unpack_msg(msg)
    print('### DEBUG ### received: ' + msg_type)
    if msg_type.startswith('N_'):
        # networking messages
        if msg_type == 'N_new_peer':
            new_peer(msg_data)
        elif msg_type == 'N_get_peers':
            get_peers(in_address)
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
    if address != (('', PORT)) and address not in peer_list:
        broadcast('N_new_peer', address)
        get_peers(address)  # Send known peers to new peer
        peer_list.add(address)


def load_initial_peers():
    """ Load initial peers from peers.cfg file
    """
    # TODO: check for validity (IP-address PORT)
    with open('./peers.cfg') as f:
        for peer in f:
            p = peer.split(' ')
            peer_list.add((p[0], int(p[1])))


def example_worker(send_queue, receive_queue):
    """ Simple example of a networker
    Arguments:
    send_queue -> Queue for messages to other nodes
    receive_queue -> Queue for messages to the attached blockchain
    """
    # Setup peers
    load_initial_peers()

    # Main loop
    while True:
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
            msg_in, address = server_socket.recvfrom(1024)
        except socket.error:
            pass
        else:
            # Add unknown node
            if address not in peer_list:
                new_peer(address)

            process_incoming_msg(msg_in, address, receive_queue)

        time.sleep(0.01)  # Maybe use threading.Event()
        # (https://stackoverflow.com/questions/29082268/python-time-sleep-vs-event-wait)


def local_worker(send_queue, receive_queue):
    receive_queue.put(('new_transaction', Transaction("a", "b", 10)))
    receive_queue.put(('new_transaction', Transaction("a", "c", 50)))
    receive_queue.put(('mine', ''))


def worker(send_queue, receive_queue, port=6666):
    """ Takes care of the communication between nodes
    Arguments:
    send_queue -> Queue for messages to other nodes
    receive_queue -> Queue for messages to the attached blockchain
    """
    print("### DEBUG ### Started networking")
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

    example_worker(send_queue, receive_queue)
