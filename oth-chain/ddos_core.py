import getopt
import re
import sys
import threading
import socket
import time

import nacl.encoding
import nacl.signing
import nacl.utils

import core
from chains import DDosChain, DDosTransaction, DDosData
from utils import keystore, set_debug
from gui import ddos_gui_loop


def parse_args(argv):
    """ Parse command line arguments

    Args:
        argv: Arguments from the command line.
    """
    port = 6666
    signing_key = None

    try:
        opts, _ = getopt.getopt(argv[1:], 'hdp=k=', [
            'help', 'debug', 'port=', 'key='])
        for o, a in opts:
            if o in ('-h', '--help'):
                print('-d/--debug to enable debug prints')
                print('-p/--port to change default port')
                print('-k/--key to load a private key from a file')
                sys.exit()
            if o in ('-d', '--debug'):
                set_debug()
            if o in ('-p', '--port'):
                try:
                    port = int(a)
                except ValueError:
                    print("Port was invalid (e.g. not an int)")
            elif o in ('-k', '--key'):
                try:
                    signing_key = keystore.load_key(filename=a)
                    print('Key successfully loaded')
                except Exception as e:
                    print('Could not load Key / Key is invalid')
                    print(e)
    except getopt.GetoptError as err:
        print('for help use --help')
        print(err)
        sys.exit()

    return port, signing_key


def init(port: int, signing_key):
    """ Initialize the blockchain client.

    Args:
        port: Port used for networking.
        signing_key: Key of the current user
    """
    my_blockchain = DDosChain(core.VERSION,
                              core.send_queue,
                              core.gui_send_queue)
    my_blockchain_processor = my_blockchain.get_message_processor()

    # Create networking thread
    networker = threading.Thread(
        target=core.worker,
        args=(core.send_queue,
              core.receive_queue,
              core.networker_command_queue,
              core.gui_send_queue, port))
    networker.start()

    # Main blockchain loop
    blockchain_thread = threading.Thread(
        target=core.blockchain_loop,
        args=(my_blockchain, my_blockchain_processor))
    blockchain_thread.start()

    # Update to newest chain
    core.send_queue.put(('get_newest_block', '', 'broadcast'))

    # Initialize signing (private) and verify (public) key
    if not signing_key:
        print('No key was detected, generating private key')
        signing_key = nacl.signing.SigningKey.generate()

    gui_thread = threading.Thread(
        target=ddos_gui_loop,
        args=(core.gui_send_queue, core.receive_queue, core.gui_receive_queue, None)
    )

    verify_key = signing_key.verify_key
    verify_key_hex = verify_key.encode(nacl.encoding.HexEncoder)

    return signing_key, verify_key_hex, networker, blockchain_thread, gui_thread


def create_transaction(sender: str,
                       timestamp: int,
                       data: DDosData,
                       signing_key: nacl.signing.SigningKey) \
        -> DDosTransaction:
    hash_str = (str(sender) +
                str(data) +
                str(timestamp))
    transaction_hash = DDosChain.hash(hash_str)

    transaction = DDosTransaction(
        sender,
        timestamp,
        data,
        signing_key.sign(transaction_hash.encode())
    )

    return transaction


def main(argv):
    """ Main function of the program.

    Provides a CLI for communication with the DDoS-blockchain node.

    Args:
        argv: Arguments from the command line.
    """

    signing_key, verify_key_hex, networker, blockchain_thread, gui_thread = init(
        *parse_args(argv))

    # User Interaction
    while True:

        print('Action: ')
        command = core.get_command()

        if command == 'help':
            help_str = (""" Available commands:
                help: prints commands
                ##STUFF##
                exit: exits program
                """)
            print(help_str)

        elif command == 'exit':
            core.receive_queue.put(('exit', '', 'local'))
            core.send_queue.put(None)
            blockchain_thread.join()
            networker.join()
            sys.exit()

        elif command == 'dump':
            core.receive_queue.put(('dump', '', 'local'))

        elif command == 'peers':
            core.networker_command_queue.put('print_peers')

        elif re.fullmatch(r'key \w+', command):
            try:
                t = command.split(' ')
                keystore.save_key(signing_key, t[1])
                print('Key saved successfully')
            except Exception as e:
                print('Could not save key')
                print(e)

        elif re.fullmatch(r'export \w+', command):
            try:
                print('Exporting public key')
                t = command.split(' ')
                keystore.save_key(verify_key_hex, t[1])
            except Exception as e:
                print('Could not export public key')
                print(e)
        elif re.fullmatch(r'blocked', command):
            core.receive_queue.put(('get_ips', '', 'local'))

        elif re.fullmatch(r'invite \w+', command):
            t = command.split(' ')
            timestamp = time.time()
            transaction = create_transaction(verify_key_hex, timestamp,
                                             DDosData('i',
                                                      t[1].encode('utf-8')),
                                             signing_key)
            core.receive_queue.put(('new_transaction',
                                    transaction,
                                    'local'
                                    ))

        elif re.fullmatch(r'uninvite \w+', command):
            t = command.split(' ')
            timestamp = time.time()
            transaction = create_transaction(verify_key_hex, timestamp,
                                             DDosData('ui',
                                                      t[1].encode('utf-8')),
                                             signing_key)
            core.receive_queue.put(('new_transaction',
                                    transaction,
                                    'local'
                                    ))

        elif re.fullmatch(r'block \d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',
                          command):
            t = command.split(' ')
            if not core.validate_ip(t[1]):
                print('Not a valid ip')
                continue
            timestamp = time.time()
            transaction = create_transaction(verify_key_hex, timestamp,
                                             DDosData('b', t[1]), signing_key)
            core.receive_queue.put(('new_transaction',
                                    transaction,
                                    'local'
                                    ))

        elif re.fullmatch(r'unblock \d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',
                          command):
            t = command.split(' ')
            if not core.validate_ip(t[1]):
                print('Not a valid ip')
                continue
            timestamp = time.time()
            transaction = create_transaction(verify_key_hex, timestamp,
                                             DDosData('ub', t[1]), signing_key)
            core.receive_queue.put(('new_transaction',
                                    transaction,
                                    'local'
                                    ))

        elif re.fullmatch(r'purge \w+', command):
            # Uninvite + unblock all ip's of user
            pass  # Create transaction
        elif re.fullmatch(r'children', command):
            core.receive_queue.put(('show_children',
                                    str(verify_key_hex),
                                    'local'))

        elif re.fullmatch(r'public', command):
            print(str(verify_key_hex))
        elif command == 'save':
            core.receive_queue.put(('save',
                                    '',
                                    'local'
                                    ))
        elif command == 'gui':
            gui_thread.start()
            core.gui_send_queue.put(('signing_key', signing_key, 'local'))


if __name__ == "__main__":
    main(sys.argv)
