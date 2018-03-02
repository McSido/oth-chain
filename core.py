import re
import sys
import threading
from queue import Queue
from pprint import pprint

import blockchain
import networking
from pow_chain import Block, PoW_Blockchain, Transaction


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


def blockchain_loop(receive_queue, blockchain):
    while True:
        msg_type, msg_data = receive_queue.get()
        print('### DEBUG ### Processing: ' + msg_type)
        receive_msg(msg_type, msg_data, blockchain)


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
    blockchain_thread = threading.Thread(
        target=blockchain_loop,
        args=(receive_queue, my_blockchain))
    blockchain_thread.start()

    # User Interaction
    while True:
        print('Action: ')
        command = input()
        if command == 'help':
            print(""" Available commands:
                transaction <from> <to> <amount>
                mine
                dump

                exit
                """)
        elif command == 'exit':
            # TODO: close queues
            # TODO: join threads
            sys.exit()
        elif command == 'mine':
            receive_queue.put(('mine', ''))
        elif re.fullmatch(r'transaction \w+ \w+ \d+', command):
            t = command.split(' ')
            receive_queue.put(('new_transaction',
                               Transaction(t[1], t[2], int(t[3]))
                               ))
        elif command == 'dump':
            pprint(vars(my_blockchain))
        else:
            print('Command not found!')


if __name__ == "__main__":
    main()
