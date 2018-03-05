import re
import sys
import threading
import getopt
import time
import nacl.encoding
import nacl.signing
import nacl.utils
import hashlib
from queue import Queue
from pprint import pprint

import blockchain
import networking
from pow_chain import Block, PoW_Blockchain, Transaction

# Create queues for message transfer blockchain<->networking
# Every message on the send_queue should be sent to all connected
#  nodes
# Every message on the receive_queue should be worked on by the
#  blockchain
send_queue = Queue()
receive_queue = Queue()


def receive_msg(msg_type, msg_data, msg_address, blockchain):
    """ Call blockchain functionality for received messages
    Arguments:
    msg_type -> String containing the type of the message
    msg_type -> Data contained by the message
    msg_address -> Address of message sender
    blockchain -> Blockchain that provides the functionality
    """
    if msg_type == 'new_block':
        blockchain.new_block(msg_data)

    elif msg_type == 'new_transaction':
        blockchain.new_transaction(msg_data)

    elif msg_type == 'mine' and msg_address == 'local':
        proof = blockchain.create_proof()
        block = blockchain.create_block(proof)
        blockchain.new_block(block)

    elif msg_type == 'get_newest_block':
        block = blockchain.latest_block()
        send_queue.put(('new_block', block, msg_address))

    elif msg_type == 'get_chain':
        send_queue.put(('resolve_conflict', blockchain.chain, msg_address))

    elif msg_type == 'resolve_conflict':
        blockchain.resolve_conflict(msg_data)

    elif msg_type == 'exit' and msg_address == 'local':
        sys.exit()


def blockchain_loop(blockchain):
    while True:
        msg_type, msg_data, msg_address = receive_queue.get()
        print('### DEBUG ### Processing: ' + msg_type)
        receive_msg(msg_type, msg_data, msg_address, blockchain)


def main(argv=sys.argv):

    port = 6666
    try:
        opts, args = getopt.getopt(argv[1:], 'hp=', ['help', 'port='])
        for o, a in opts:
            if o in ('-h', '--help'):
                print('-p/--port to change default port')
                sys.exit()
            if o in ('-p', '--port'):
                try:
                    port = int(a)
                except:
                    print("Port was invalid (e.g. not an int)")
    except getopt.GetoptError as err:
        print('for help use --help')
        print(err)
        sys.exit()

    # Create proof-of-work blockchain
    my_blockchain = PoW_Blockchain(send_queue, 4)

    # Create networking thread
    networker = threading.Thread(
        target=networking.worker,
        args=(send_queue, receive_queue, port))
    networker.start()

    # Main blockchain loop
    blockchain_thread = threading.Thread(
        target=blockchain_loop,
        args=(my_blockchain,))
    blockchain_thread.start()

    # Update to newest chain
    send_queue.put(('get_newest_block', '', 'broadcast'))

    # Initialize signing (private) and verify (public) key
    # TODO: Add saving/loading private key
    signing_key = nacl.signing.SigningKey.generate()
    verify_key = signing_key.verify_key
    verify_key_hex = verify_key.encode(nacl.encoding.HexEncoder)

    # User Interaction
    while True:
        print('Action: ')
        command = input()
        if command == 'help':
            print(""" Available commands:
                transaction <from> <to> <amount>
                mine
                dump
                peers

                exit
                """)
        elif command == 'exit':
            receive_queue.put(('exit', '', 'local'))
            send_queue.put(None)

            blockchain_thread.join()
            networker.join()
            sys.exit()
        elif command == 'mine':
            receive_queue.put(('mine', '', 'local'))
        elif re.fullmatch(r'transaction \w+ \w+ \d+', command):
            t = command.split(' ')
            # Create new Transaction, sender = hex(public_key), signature = signed random number
            timestamp = time.time()
            hash = hashlib.sha256((str(verify_key_hex) + str(t[2]) + str(t[3]) + str(timestamp)).encode()).hexdigest()
            receive_queue.put(('new_transaction',
                               Transaction(verify_key_hex, t[2], int(t[3]), timestamp,
                                           signing_key.sign(hash.encode())),
                               'local'
                               ))
        elif command == 'dump':
            pprint(vars(my_blockchain))
        elif command == 'peers':
            pprint(networking.peer_list)  # TODO: threadsafe!!!
        else:
            print('Command not found!')


if __name__ == "__main__":
    main()
