""" Core module of the blockchain client.

Contains the main function of the program,
as well as a target function for the blockchain thread.

Also contains various functions for private/public keys.
"""

import getopt
import hashlib
import math
import re
import socket
import sys
import threading
import time
from queue import Queue
from typing import Any

import nacl.encoding
import nacl.signing
import nacl.utils

from chains import Blockchain, DNSBlockChain, DNS_Transaction, DNS_Data, PoW_Blockchain, Transaction
from gui import gui_loop
from networking import Address, worker
from utils import Keystore, load_key, save_key, print_debug_info, set_debug

# Create queues for message transfer blockchain<->networking
# Every message on the send_queue should be sent to all connected
#  nodes
# Every message on the receive_queue should be worked on by the
#  blockchain
send_queue: Queue = Queue()
receive_queue: Queue = Queue()
networker_command_queue: Queue = Queue()
# queue for exchanging values between gui
gui_send_queue: Queue = Queue()
gui_receive_queue: Queue = Queue()

VERSION = 0.7


def receive_msg(msg_type: str, msg_data: Any, msg_address: Address,
                blockchain: Blockchain, processor):
    """ Call blockchain functionality for received messages.

    Args:
        msg_type: String containing the type of the message.
        msg_data: Data contained by the message.
        msg_address: Address of message sender.
        blockchain: Blockchain that provides the functionality.
        processor: Processor that handles blockchain messages.
    """

    if msg_type == 'get_newest_block':
        header = blockchain.latest_header()
        send_queue.put(('new_header', header, msg_address))
    elif msg_type == 'get_chain':
        send_queue.put(
            ('resolve_conflict', blockchain.get_header_chain(), msg_address))
    elif msg_type == 'exit' and msg_address == 'local':
        sys.exit()
    else:
        processor(msg_type, msg_data, msg_address)


def blockchain_loop(blockchain: Blockchain, processor):
    """ The main loop of the blockchain thread.

    Receives messages and processes them.

    Args:
        blockchain: The blockchain upon which to operate.
        processor: Processor used to handle blockchain messages.
    """
    while True:
        msg_type, msg_data, msg_address = receive_queue.get()
        print_debug_info('Processing: ' + msg_type)
        try:
            receive_msg(msg_type, msg_data, msg_address, blockchain, processor)
        except AssertionError as e:
            print_debug_info(
                f'Assertion Error on message\
                 {msg_type}:{msg_data}:{msg_address}')
            print_debug_info(e)


def create_transaction(dns: bool, sender: str, recipient: str, amount: int, fee: int,
                       timestamp: int, dns_data: DNS_Data, signing_key: nacl.signing.SigningKey):
    """ Creates a transaction from the given arguments:
        Args:
            dns: whether or not to create a DNS_Transaction
            sender: sender of the transaction
            recipient: recipient of the transaction
            amount: amount of coins sended
            fee: fee for the transaction
            timestamp: timestamp of the transaction
            dns_data: includes information on dns operations
            signing_key: key used to sign the hash
    """
    hash_str = (str(sender) +
                str(recipient) + str(amount)
                + str(fee) +
                str(timestamp))
    if not dns:
        transaction_hash = hashlib.sha256(hash_str.encode()).hexdigest()

        transaction = Transaction(sender,
                                  recipient,
                                  amount,
                                  fee,
                                  timestamp,
                                  signing_key.sign(
                                      transaction_hash.encode())
                                  )
        return transaction

    transaction_hash = hashlib.sha256((hash_str + str(dns_data)).encode()).hexdigest()
    transaction = DNS_Transaction(sender,
                                  recipient,
                                  amount,
                                  fee,
                                  timestamp,
                                  dns_data,
                                  signing_key.sign(
                                      transaction_hash.encode())
                                  )
    return transaction


def parse_args(argv):
    """ Parse command line arguments

    Args:
        argv: Arguments from the command line.
    """
    keystore_filename = 'keystore'
    port = 6666
    signing_key = None
    dns = False
    try:
        opts, _ = getopt.getopt(argv[1:], 'hdnp=k=s=', [
            'help', 'debug', 'dns', 'port=', 'key=', 'store='])
        for o, a in opts:
            if o in ('-h', '--help'):
                print('-d/--debug to enable debug prints')
                print('-n/--dns to start a dns chain')
                print('-p/--port to change default port')
                print('-k/--key to load a private key from a file')
                print('-s/--store to load a keystore from a file')
                sys.exit()
            if o in ('-d', '--debug'):
                set_debug()
            if o in ('-n', '--dns'):
                dns = True
            if o in ('-p', '--port'):
                try:
                    port = int(a)
                except ValueError:
                    print("Port was invalid (e.g. not an int)")
            elif o in ('-k', '--key'):
                try:
                    signing_key = load_key(filename=a)
                    print('Key successfully loaded')
                except Exception as e:
                    print('Could not load Key / Key is invalid')
                    print(e)
            elif o in ('-s', '--store'):
                keystore_filename = a
                print_debug_info(keystore_filename)

    except getopt.GetoptError as err:
        print('for help use --help')
        print(err)
        sys.exit()

    return keystore_filename, port, signing_key, dns


def init(keystore_filename: str, port: int, signing_key, dns: bool):
    """ Initialize the blockchain client.

    Args:
        keystore_filename: Filename of the keystore.
        port: Port used for networking.
        signing_key: Key of the current user
        dns: Indicates, whether the chain is a dns-chain or a normal pow-chain
    """
    # Create proof-of-work blockchain

    if dns:
        my_blockchain = DNSBlockChain(VERSION, send_queue, gui_send_queue)
    else:
        my_blockchain = PoW_Blockchain(VERSION, send_queue, gui_send_queue)
    my_blockchain_processor = my_blockchain.process_message()

    # Create networking thread
    networker = threading.Thread(
        target=worker,
        args=(send_queue, receive_queue, networker_command_queue, gui_send_queue, port))
    networker.start()

    # Main blockchain loop
    blockchain_thread = threading.Thread(
        target=blockchain_loop,
        args=(my_blockchain, my_blockchain_processor))
    blockchain_thread.start()

    # Update to newest chain
    send_queue.put(('get_newest_block', '', 'broadcast'))

    # Initialize signing (private) and verify (public) key
    if not signing_key:
        print('No key was detected, generating private key')
        signing_key = nacl.signing.SigningKey.generate()

    verify_key = signing_key.verify_key
    verify_key_hex = verify_key.encode(nacl.encoding.HexEncoder)

    # Initialize Keystore
    keystore = Keystore(keystore_filename)

    # gui thread
    gui_thread = threading.Thread(
        target=gui_loop,
        args=(gui_send_queue, receive_queue, gui_receive_queue, keystore), )  # daemon=True

    return keystore, signing_key, verify_key_hex, networker, blockchain_thread, gui_thread, dns


def main(argv):
    """ Main function of the program.

    Provides a CLI for communication with the blockchain node.

    Args:
        argv: Arguments from the command line.
    """
    keystore, signing_key, verify_key_hex, networker, blockchain_thread, gui_thread, dns = init(*parse_args(argv))

    # User Interaction
    while True:

        if gui_thread.is_alive():
            if not gui_receive_queue.empty():
                command = gui_receive_queue.get(block=True)
                print('Command from gui: {}'.format(command))
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

        # gui_send_queue.put(command)
        if command == 'help':
            help_str = (""" Available commands:
                help: prints commands
                transaction <to> <amount> : Create transaction
                mine: mine a new block
                balance [<name>]: Print balance (name optional)
                dump: print blockchain
                peers: print peers
                key <filename> : Save current key to <filename>
                import <key> <name> : Imports a public key associated with \
<name> from file <file> to the keystore
                deletekey <name> : Deletes key associated with <name> from\
keystore
                export <filename> : Exports one own public key to file\
<filename>
                save: Save blockchain to bc_file.txt
                exit: exits program
                """)
            print(help_str)
            if dns:
                dns_str = (""" DNS-only commands:
                register <domain> <ip> : Registers an available domain to an ip (costs 20 coins)
                update <domain> <ip> : Updates an existing already owned domain with a new ip (costs 20 coins)
                transfer <to> <domain> : Transfers an owned domain to another user (costs 1 coin)
                auction <domain> : Offers an owned domain for auction (costs 1 coin)
                bid <amount> <domain> : Places a bid of <amount> on the auctioned domain.
                resolve <domain> : Resolves the domain name and prints the ip (if the domain does not exist, prints '')
                """)
                print(dns_str)
            gui_send_queue.put(help_str)
        elif command == 'exit':
            receive_queue.put(('exit', '', 'local'))
            send_queue.put(None)
            keystore.save()
            blockchain_thread.join()
            networker.join()
            if gui_thread.is_alive():
                gui_thread.join()
            sys.exit()
        elif command == 'mine':
            receive_queue.put(('mine', verify_key_hex, 'local'))
        elif re.fullmatch(r'transaction \w+ \d+', command):
            t = command.split(' ')
            # Create new Transaction, sender = hex(public_key),
            # signature = signed hash of the transaction
            if int(t[2]) <= 0:
                print('Transactions must contain a amount greater than zero!')
                continue
            recipient = keystore.resolve_name(t[1])
            if recipient == 'Error':
                continue
            timestamp = time.time()
            # fee equals 5% of the transaction amount - at least 1
            fee = int(math.ceil(int(t[2]) * 0.05))
            transaction = create_transaction(dns, verify_key_hex, str(recipient),
                                             int(t[2]), fee, timestamp, DNS_Data('', '', ''), signing_key)

            receive_queue.put(('new_transaction',
                               transaction,
                               'local'
                               ))
        elif command == 'dump':
            # gui_send_queue.put(vars(my_blockchain))
            # pprint(vars(my_blockchain))
            receive_queue.put(('dump', '', 'local'))
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
                if keystore.resolve_name(t[2]):
                    keystore.update_key(t[2], t[1])
                else:
                    print('importing public key')
                    keystore.add_key(t[2], t[1])
            except Exception as e:
                print('Could not import key')
                print(e)
        elif re.fullmatch(r'deletekey \w+', command):
            try:
                t = command.split(' ')
                if keystore.resolve_name(t[1]):
                    keystore.update_key(t[1], '')
                else:
                    print(
                        f'Could not delete {t[1]} from keystore.',
                        ' Was it spelt right?')
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
            account = keystore.resolve_name(t[1])
            if account != 'Error':
                receive_queue.put(('print_balance',
                                   (account, time.time()),
                                   'local'
                                   ))
        elif re.fullmatch(r'resolve \w+\.\w+', command):
            if not dns:
                print('Command not supported!')
                continue
            t = command.split(' ')
            receive_queue.put(('dns_lookup',
                               t[1],
                               'local'
                               ))
        elif re.fullmatch(r'(register|update) \w+\.\w+ \d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', command):
            if not dns:
                print('Command not supported!')
                continue
            t = command.split(' ')
            valid_ip = True
            try:
                socket.inet_aton(t[2])
            except OSError:
                valid_ip = False
            if not valid_ip:
                print('Not a valid ip')
                continue
            recipient = '0'
            timestamp = time.time()
            # fee for domain registration equals 20
            fee = 20
            typ = t[0][0]
            data = DNS_Data(typ, t[1], t[2])
            transaction = create_transaction(dns, verify_key_hex, str(recipient), 0,
                                             fee, timestamp, data, signing_key)

            receive_queue.put(('new_transaction',
                               transaction,
                               'local'
                               ))
        elif re.fullmatch(r'transfer \w+ \w+\.\w+', command):
            if not dns:
                print('Command not supported!')
                continue
            t = command.split(' ')
            account = keystore.resolve_name(t[1])
            if account != 'Error':
                recipient = account
                timestamp = time.time()
                # fee for domain transfer equals 1
                fee = 1
                typ = 't'
                data = DNS_Data(typ, t[2], '')
                transaction = create_transaction(dns, verify_key_hex, str(recipient), 0,
                                                 fee, timestamp, data, signing_key)
                receive_queue.put(('new_transaction',
                                   transaction,
                                   'local'
                                   ))
        elif re.fullmatch(r'auction \w+\.\w+', command):
            if not dns:
                print('Command not supported!')
                continue
            t = command.split(' ')
            recipient = '0'
            timestamp = time.time()
            # fee for auction equals 1
            fee = 1
            typ = 't'
            data = DNS_Data(typ, t[1], '')
            transaction = create_transaction(dns, verify_key_hex, str(recipient), 0,
                                             fee, timestamp, data, signing_key)

            receive_queue.put(('new_transaction',
                               transaction,
                               'local'
                               ))
        elif re.fullmatch(r'bid \d+ \w+\.\w+', command):
            if not dns:
                print('Command not supported!')
                continue
            t = command.split(' ')
            recipient = '0'
            timestamp = time.time()
            # fee for bid equals 1
            fee = 1
            typ = 'b'
            amount = int(t[1])
            data = DNS_Data(typ, t[2], '')
            transaction = create_transaction(dns, verify_key_hex, str(recipient), amount,
                                             fee, timestamp, data, signing_key)
            receive_queue.put(('new_transaction',
                               transaction,
                               'local'
                               ))
        elif command == 'save':
            receive_queue.put(('save',
                               '',
                               'local'
                               ))
        elif command == 'gui':
            if dns:
                print('gui not yet supported for DNS Chain')
                continue
            print("open gui")
            gui_thread.start()
            gui_send_queue.put(('signing_key', signing_key, 'local'))

        else:
            print('Command not found!')


if __name__ == "__main__":
    main(sys.argv)
