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
from GUI import *

import blockchain
import networking
from pow_chain import Block, PoW_Blockchain, Transaction
from utils import print_debug_info, set_debug

# Create queues for message transfer blockchain<->networking
# Every message on the send_queue should be sent to all connected
#  nodes
# Every message on the receive_queue should be worked on by the
#  blockchain
send_queue = Queue()
receive_queue = Queue()
networker_command_queue = Queue()
#queue for exchanging values between gui
gui_send_queue = Queue()
gui_receive_queue = Queue()

keystore = dict()
keystore_filename = 'keystore'


def receive_msg(msg_type, msg_data, msg_address, blockchain):
    """ Call blockchain functionality for received messages
    Arguments:
    msg_type -> String containing the type of the message
    msg_type -> Data contained by the message
    msg_address -> Address of message sender
    blockchain -> Blockchain that provides the functionality
    """
    if msg_type == 'new_block':
        assert isinstance(msg_data, Block)
        blockchain.new_block(msg_data)

    elif msg_type == 'new_transaction':
        # ignore mining transactions (those are stored immediately in the mined block)
        assert isinstance(msg_data, Transaction)
        if not msg_data.sender == '0':
            blockchain.new_transaction(msg_data)

    elif msg_type == 'mine' and msg_address == 'local':
        proof = blockchain.create_proof(msg_data)
        block = blockchain.create_block(proof)
        # Calculate the transaction fees - Maybe exclude transactions where the miner == the sender/recipient?
        fee_sum = 0
        for transaction in block.transactions:
            fee_sum += transaction.fee
        mining_reward = math.floor(50/max(math.floor(math.log(block.index) / 2), 1))
        if mining_reward == 1:
            mining_reward = 0
        block.transactions.append(
            Transaction(sender='0', recipient=msg_data,
                        amount=mining_reward+fee_sum, fee=0, timestamp=time.time(), signature='0'))
        blockchain.new_block(block)

    elif msg_type == 'get_newest_block':
        block = blockchain.latest_block()
        send_queue.put(('new_block', block, msg_address))

    elif msg_type == 'get_chain':
        send_queue.put(('resolve_conflict', blockchain.chain, msg_address))

    elif msg_type == 'resolve_conflict':
        assert isinstance(msg_data, list)
        blockchain.resolve_conflict(msg_data)

    elif msg_type == 'print_balance' and msg_address == 'local':
        print(f'Current Balance: {blockchain.check_balance(msg_data[0], msg_data[1])}')

    elif msg_type == 'exit' and msg_address == 'local':
        sys.exit()

def blockchain_loop(blockchain):
    while True:
        msg_type, msg_data, msg_address = receive_queue.get()
        print_debug_info('### DEBUG ### Processing: ' + msg_type)
        try:
            receive_msg(msg_type, msg_data, msg_address, blockchain)
        except AssertionError as e:
            print_debug_info(f'### DEBUG ### Assertion Error on message {msg_type}:{msg_data}:{msg_address}')
            print_debug_info(e)

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


def save_keystore():
    with open(keystore_filename, 'wb') as f:
        pickle.dump(keystore, f)


def load_keystore():
    with open(keystore_filename, 'rb') as f:
        global keystore
        keystore = pickle.load(f)


def resolve_name(name):
    try:
        return keystore[name]
    except KeyError:
        print_debug_info('### DEBUG ### Unknown name')
        return 'Error'


def add_to_keystore(name, key):
    try:
        if keystore[name]:
            print('Name already exists, use update if you want to change the respective key')
            return
    except KeyError:
        keystore[name] = key
    save_keystore()


def update_keystore(name, key):
    if key == '':
        keystore.pop(name)
    keystore[name] = key
    save_keystore()


def main(argv=sys.argv):

    port = 6666
    signing_key = None
    try:
        opts, args = getopt.getopt(argv[1:], 'hdp=k=s=', ['help',  'debug', 'port=', 'key=', 'store='])
        for o, a in opts:
            if o in ('-h', '--help'):
                print('-d/--debug to enable debug prints')
                print('-p/--port to change default port')
                print('-k/--key to load a private key from a file')
                print('-s/--store to load a keystore from a file')
                sys.exit()
            if o in ('-d', '--debug'):
                set_debug()
            if o in ('-p', '--port'):
                try:
                    port = int(a)
                except:
                    print("Port was invalid (e.g. not an int)")
            elif o in ('-k', '--key'):
                try:
                    signing_key = load_key(filename=a)
                    print('Key successfully loaded')
                except Exception as e:
                    print('Could not load Key / Key is invalid')
                    print(e)
            elif o in ('-s', '--store'):
                global keystore_filename
                keystore_filename = a
                print(keystore_filename)
                try:
                    load_keystore()
                    print('Keystore successfully loaded')
                except Exception as e:
                    print('Could not load Keystore')
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
        args=(send_queue, receive_queue, networker_command_queue, port))
    networker.start()

    # Main blockchain loop
    blockchain_thread = threading.Thread(
        target=blockchain_loop,
        args=(my_blockchain,))
    blockchain_thread.start()

    # gui thread
    gui_thread = threading.Thread(
        target=gui_loop,
        args=(gui_send_queue, gui_receive_queue),)#daemon=True

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


        if(gui_thread.is_alive()): #
            if(not gui_receive_queue.empty()):
                command = gui_receive_queue.get(block=True)
                print('Command from GUI: {}'.format(command))
            else:
                continue
        else:
            print('Action: ')
            
        try:
            command = input()
        except KeyboardInterrupt:
            print('Detected Keyboard interrupt, exiting program')
            command = 'exit'

        command = command.lower().strip()
        command = re.sub(r'\s\s*', ' ', command)

        gui_send_queue.put(command)
        if command == 'help':
            print(""" Available commands:
                help: prints commands
                transaction <to> <amount> : Create transaction
                mine: mine a new block
                balance [<name>]: Print balance (name optional)
                dump: print blockchain
                peers: print peers
                key <filename> : Save current key to <filename>
                import <key> <name> : Imports a public key associated with <name> from file <file> to the keystore
                deletekey <name> : Deletes key associated with <name> from keystore
                export <filename> : Exports one own public key to file <filename>
                save: Save blockchain to bc_file.txt
                exit: exits programm
                """)
        elif command == 'exit':
            receive_queue.put(('exit', '', 'local'))
            send_queue.put(None)
            save_keystore()
            blockchain_thread.join()
            networker.join()
            sys.exit()
        elif command == 'mine':
            receive_queue.put(('mine', verify_key_hex, 'local'))
        elif re.fullmatch(r'transaction \w+ \d+', command):
            t = command.split(' ')
            # Create new Transaction, sender = hex(public_key), signature = signed hash of the transaction
            if not int(t[2]) > 0:
                print('Transactions must contain a amount greater than zero!')
                continue
            recipient = resolve_name(t[1])
            if recipient == 'Error':
                continue
            timestamp = time.time()
            # fee equals 5% of the transaction amount - at least 1
            fee = math.ceil(int(t[2]) * 0.05)
            transaction_hash = hashlib.sha256((str(verify_key_hex) + str(recipient) + str(t[2])
                                               + str(fee) + str(timestamp)).encode()).hexdigest()
            receive_queue.put(('new_transaction',
                               Transaction(verify_key_hex, recipient, int(t[2]), fee, timestamp,
                                           signing_key.sign(transaction_hash.encode())),
                               'local'
                               ))
        elif command == 'dump':
            gui_send_queue.put(vars(my_blockchain))
            pprint(vars(my_blockchain))
        elif command == 'peers':
            networker_command_queue.put('print_peers')
        elif re.fullmatch(r'key \w+', command):
            try:
                t = command.split(' ')
                save_key(signing_key, t[1])
                print('Key saved successfully')
            except Exception as e:
                print('Could not save key')
                print(e)
        elif re.fullmatch(r'import \w+ \w+', command):
            try:
                t = command.split(' ')
                if resolve_name(t[2]):
                    update_keystore(t[2], load_key(t[1]))
                else:
                    print('importing public key')
                    add_to_keystore(t[1], load_key(t[1]))
            except Exception as e:
                print('Could not import key')
                print(e)
        elif re.fullmatch(r'deletekey \w+', command):
            try:
                t = command.split(' ')
                if resolve_name(t[1]):
                    update_keystore(t[1], '')
                else:
                    print(
                        f'Could not delete {t[1]} from keystore. Was it spelt right?')
            except Exception as e:
                print('Could not delete key')
                print(e)
        elif re.fullmatch(r'export \w+', command):
            try:
                print('Exporting public key')
                t = command.split(' ')
                save_key(verify_key_hex, t[1])
            except Exception as e:
                print('Could not export public key')
                print(e)
        elif command == 'balance':
            receive_queue.put(('print_balance',
                              (verify_key_hex, time.time()),
                              'local'))
        elif re.fullmatch(r'balance \w+', command):
            t = command.split(' ')
            account = resolve_name(t[1])
            if not account == 'Error':
                receive_queue.put(('print_balance',
                                   (account, time.time()),
                                   'local'
                                   ))
        elif command == 'save':
            pprint('saving to file named bc_file.txt')
            with open('bc_file.txt', 'wb') as output:
                pickle.dump(my_blockchain.chain, output,
                            pickle.HIGHEST_PROTOCOL)  # Threadsafe?
        elif command == 'gui':
            print("open gui")
            gui_thread.start()

        else:
            print('Command not found!')


if __name__ == "__main__":
    main()
