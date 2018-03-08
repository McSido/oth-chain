import re
import sys
import threading
import getopt
import time
import nacl.encoding
import nacl.signing
import nacl.utils
import hashlib
import pickle
import math
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
        if not msg_data.sender == '0':
            blockchain.new_transaction(msg_data)

    elif msg_type == 'mine' and msg_address == 'local':
        proof = blockchain.create_proof(msg_data)
        block = blockchain.create_block(proof)
        # Calculate the transaction fees - Maybe exclude transactions where the miner == the sender/recipient?
        fee_sum = 0
        for transaction in block.transactions:
            fee_sum += math.ceil(0.05 * transaction.amount)
        block.transactions.append(
            Transaction(sender='0', recipient=msg_data, amount=50+fee_sum, timestamp=time.time(), signature='0'))
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


def load_key(filename):
    """Attempts to load the private key from the provided file
    """
    with open(filename, 'rb') as f:
        return pickle.load(f)


def save_key(key, filename):
    """Attempts to save the private key to the provided file
    """
    with open(filename, 'wb') as f:
        pickle.dump(key, f)


def main(argv=sys.argv):

    port = 6666
    signing_key = None
    try:
        opts, args = getopt.getopt(argv[1:], 'hp=k=', ['help', 'port=', 'key='])
        for o, a in opts:
            if o in ('-h', '--help'):
                print('-p/--port to change default port')
                print('-k/--key to load a private key from a file')
                sys.exit()
            if o in ('-p', '--port'):
                try:
                    port = int(a)
                except:
                    print("Port was invalid (e.g. not an int)")
            if o in ('-k', '--key'):
                try:
                    signing_key = load_key(filename=a)
                    print('Key successfully loaded')
                except Exception as e:
                    print('Could not load Key / Key is invalid')
                    print(e)

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
    if not signing_key:
        print('No key was detected, generating private key')
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
                key <filename>
                save
                exit
                """)
        elif command == 'exit':
            receive_queue.put(('exit', '', 'local'))
            send_queue.put(None)

            blockchain_thread.join()
            networker.join()
            sys.exit()
        elif command == 'mine':
            receive_queue.put(('mine', verify_key_hex, 'local'))
        elif re.fullmatch(r'transaction \w+ \w+ \d+', command):
            t = command.split(' ')
            # Create new Transaction, sender = hex(public_key), signature = signed hash of the transaction
            timestamp = time.time()
            transaction_hash = hashlib.sha256((str(verify_key_hex) + str(t[2]) + str(t[3]) + str(timestamp)).encode())\
                .hexdigest()
            receive_queue.put(('new_transaction',
                               Transaction(verify_key_hex, t[2], int(t[3]), timestamp,
                                           signing_key.sign(transaction_hash.encode())),
                               'local'
                               ))
        elif command == 'dump':
            pprint(vars(my_blockchain))
        elif command == 'peers':
            print('all peers:')
            pprint(networking.peer_list)  # TODO: threadsafe!!!
            print('active peers:')
            pprint(networking.active_peers)  # TODO: threadsafe!!!
        elif re.fullmatch(r'key \w+', command):
            try:
                t = command.split(' ')
                save_key(signing_key, t[1])
                print('Key saved successfully')
            except Exception as e:
                print('Could not save key')
                print(e)
        elif command == 'save':
            pprint('saving to file named bc_file.txt')
            with open('bc_file.txt', 'wb') as output:
                pickle.dump(my_blockchain.chain, output, pickle.HIGHEST_PROTOCOL)
        else:
            print('Command not found!')


if __name__ == "__main__":
    main()
