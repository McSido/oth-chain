import socket
import pickle  # change for secure solution
# (https://docs.python.org/3/library/pickle.html?highlight=pickle#module-pickle)
from blockchain import Transaction, Block
from queue import Empty
import time


# Initialize
PORT = 6666
peer_list = set()
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind(('', PORT))
server_socket.settimeout(0.01)


def send_msg(msg_type, msg_data, address):
    server_socket.sendto(
        pack_msg((msg_type, msg_data)),
        address
    )


def broadcast(msg_type, msg_data):
    for peer in peer_list:
        send_msg(msg_type, msg_data, peer)


def unpack_msg(msg):
    return pickle.loads(msg)


def pack_msg(msg):
    return pickle.dumps(msg)


def process_incoming_msg(msg, in_address, receive_queue):
    msg_type, msg_data = unpack_msg(msg)
    if msg_type.startswith('N_'):
        # networking messages
        if msg_type == 'N_new_peer':
            new_peer(msg_data)
        elif msg_type == 'N_get_peers':
            get_peers(in_address)
    else:
        # blockchain messages
        receive_queue.put((msg_type, msg_data))


def get_peers(address):
    for peer in peer_list:
        send_msg('N_new_peer', peer, address)


def new_peer(address):
    if address != (('', PORT)):
        broadcast('N_new_peer', address)
        peer_list.add(address)


def example_worker(broadcast_queue, receive_queue):
    # Setup peers
    peer_list.add(('localhost', 6667))

    # Add fake messages to node with PORT=6666
    if PORT == 6666:
        broadcast_queue.put(('new_transaction', Transaction("a", "b", 10)))
        broadcast_queue.put(('new_transaction', Transaction("a", "c", 50)))
        broadcast_queue.put(('mine', ''))

    # Main loop
    while True:
        try:
            msg_out_type, msg_out_data = broadcast_queue.get(block=False)
        except Empty:
            pass
        else:
            broadcast(msg_out_type, msg_out_data)

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


def local_worker(broadcast_queue, receive_queue):
    receive_queue.put(('new_transaction', Transaction("a", "b", 10)))
    receive_queue.put(('new_transaction', Transaction("a", "c", 50)))
    receive_queue.put(('mine', ''))


def worker(broadcast_queue, receive_queue):
    """ Takes care of the communication between nodes
    Arguments:
    broadcast_queue -> Queue for messages to other nodes
    receive_queue -> Queue for messages to the attached blockchain
    """
    print("Started networking")
    # Example:
    # Find peers
    # Main loop:
    # - check broadcast_queue (send new messages)
    # - check incoming messages
    #   -- Networking message (e.g. new peer, get peers)
    #   -- Blockchain message: put on receive_queue

    example_worker(broadcast_queue, receive_queue)
