import blockchain
from pow_chain import PoW_Blockchain, Transaction, Block
import networking
from queue import Queue
import threading


def receive_msg(msg_type, msg_data, blockchain):
    """ Call blockchain functionality for received messages
    Arguments:
    msg_type -> String containing the type of the message
    msg_type -> Data contained by the message
    blockchain -> Blockchain that provides the functionality
    """
    if msg_type == 'new_block':
        blockchain.new_block(msg_data)
    elif msg_type == 'new_transaction':
        blockchain.new_transaction(msg_data)
    elif msg_type == 'mine':
        proof = blockchain.create_proof()
        block = blockchain.create_block(proof)
        blockchain.new_block(block)


def main():
    # Create queues for message transfer blockchain<->networking
    # Every message on the broadcast_queue should be sent to all connected
    #  nodes
    # Every message on the receive_queue should be worked on by the
    #  blockchain
    broadcast_queue = Queue()
    receive_queue = Queue()

    # TODO: manage end of queue, maybe: (if queue.get() == None)

    # Create proof-of-work blockchain
    my_blockchain = PoW_Blockchain(broadcast_queue, 4)

    # Create networking thread
    networker = threading.Thread(
        target=networking.worker,
        args=(broadcast_queue, receive_queue))
    networker.start()

    # Main blockchain loop
    while True:
        msg_type, msg_data = receive_queue.get()
        print('received msg: ' + msg_type)
        receive_msg(msg_type, msg_data, my_blockchain)


if __name__ == "__main__":
    main()
