import os
from collections import namedtuple, OrderedDict
from pathlib import Path
from pprint import pprint
from queue import Queue
from time import time
from typing import Any, List, Callable, Dict, Tuple

import nacl.encoding
import nacl.signing
import serializer
from nacl.exceptions import BadSignatureError
from utils import Node, print_debug_info

from .blockchain import Blockchain, Block, Address

DDosHeader = namedtuple('DDosHeader',
                        ['version',
                         'index',
                         'timestamp',
                         'previous_hash',
                         'root_hash'])

DDosTransaction = namedtuple('DDosTransaction',
                             ['sender',
                              'timestamp',
                              'data',
                              'signature'])

DDosData = namedtuple('DDosData',
                      ['type',
                       'data'])

IP_LIST_FILE_NAME = 'Blacklist.txt'


class DDosChain(Blockchain):

    def __init__(self,
                 version: float,
                 send_queue: Queue,
                 gui_queue: Queue) -> None:
        super(DDosChain, self).__init__(version, send_queue, gui_queue)
        self.tree = Node('Root')
        self.tree.add_child(Node(str(
            "ab2a248087095ef9e84a900337fac41cf2d588e9017b345f1c90a4bb0844ed28".encode('utf-8'))))
        self.blocked_ips: Dict[str, Node] = {}

    def get_ips(self):
        return list(self.blocked_ips.keys())

    def save_ips_to_file(self):
        with open(IP_LIST_FILE_NAME, 'w') as f:
            f.writelines(self.blocked_ips.keys())

    def load_chain(self):
        if os.path.exists('ddos_bc_file.txt') and \
                os.stat('ddos_bc_file.txt').st_size != 0 and \
                Path('ddos_bc_file.txt').is_file():
            print_debug_info(
                'Load existing blockchain from file')
            with open('ddos_bc_file.txt', 'r') as bc_file:
                self.chain = serializer.deserialize(bc_file.read())
        else:
            self.chain[DDosHeader(0, 0, 768894480, 0, 0)] = []

    def save_chain(self):
        """ Save the current chain to the hard drive.
        """
        pprint('saving to file named bc_file.txt')
        with open('ddos_bc_file.txt', 'w') as output:
            output.write(serializer.serialize(self.chain))

    def process_transaction(self, transaction: DDosTransaction):
        # INVITE
        if transaction.data.type == 'i':
            new_node = Node(str(transaction.data.data))
            parent = self.tree.get_node_by_content(str(transaction.sender))
            parent.add_child(new_node)

        # UNINVITE
        elif transaction.data.type == 'ui':
            node_to_remove = self.tree.get_node_by_content(
                str(transaction.data.data))
            self.tree.remove_node(node_to_remove, False)

        # BLOCK IP
        elif transaction.data.type == 'b':
            if transaction.data.data in self.blocked_ips:
                ancestors = self.blocked_ips[transaction.data.data].\
                    get_ancestors()
                if str(transaction.sender) in [a.content for a in ancestors]:
                    # Escalate blocked-IP to ancestor
                    for a in ancestors:
                        if a.content == str(transaction.sender):
                            self.blocked_ips[transaction.data.data] = a
                            break
            else:
                self.blocked_ips[transaction.data.data] =\
                    self.tree.get_node_by_content(
                    str(transaction.sender))

        # UNBLOCK IP
        elif transaction.data.type == 'ub':
            del(self.blocked_ips[transaction.data.data])
        # PURGE
        elif transaction.data.type == 'p':
            node_to_remove = self.tree.get_node_by_content(
                str(transaction.data.data))
            self.tree.remove_node(node_to_remove, False)
            index_list = []
            # Remove all ips blocked from this client
            for i, t in enumerate(self.blocked_ips.items()):
                blocker = t[1]
                if blocker == node_to_remove.content:
                    index_list.append(i)
            for index in index_list:
                del(self.blocked_ips[index])

    def valid_operation(self, transaction: DDosTransaction):
        # Invite
        if transaction.data.type == 'i':
            if str(transaction.data.data) in self.tree:
                print_debug_info('Client is already invited!')
                return False
        # Uninvite / Purge
        elif transaction.data.type == 'ui' or transaction.data.type == 'p':
            if str(transaction.data.data) not in self.tree:
                print_debug_info('Client could not be found!')
                return False
            node_to_remove = self.tree.get_node_by_content(
                str(transaction.data.data))
            sender_node = self.tree.get_node_by_content(
                str(transaction.sender))
            if node_to_remove.content not in sender_node:
                print_debug_info('No permission to delete this node!')
                return False
        # Block IP-Address
        elif transaction.data.type == 'b':
            if transaction.data.data in self.blocked_ips:
                ancestors = self.blocked_ips[transaction.data.data].\
                    get_ancestors()
                if not str(transaction.sender) in [a.content for a in ancestors]:
                    print_debug_info('IP was already blocked')
                    return False
        # Unblock IP-Address
        elif transaction.data.type == 'ub':
            if transaction.data.data in self.blocked_ips:
                if str(transaction.sender) ==\
                        self.blocked_ips[transaction.data.data].content:
                    return True
                ancestors = self.blocked_ips[transaction.data.data].\
                    get_ancestors()
                if str(transaction.sender) in [a.content for a in ancestors]:
                    # IP blocked from descendant
                    return True
                print_debug_info('IP was already blocked')
                return False
            else:
                print_debug_info('Trying to unblock IP that was not blocked')
                return False
        return True

    def new_transaction(self, transaction: DDosTransaction):
        if not self.validate_transaction(transaction):
            print_debug_info('Invalid transaction')
            return

        for pool_transaction in self.transaction_pool:
            if transaction == pool_transaction:
                print_debug_info('Transaction already in pool')
                return
            if transaction.data == pool_transaction.data:
                print_debug_info('This operation is already in the pool')
                return

        self.transaction_pool.append(transaction)
        self.send_queue.put(('new_transaction', transaction, 'broadcast'))
        if len(self.transaction_pool) >= 5:
            self.create_m_blocks()

    def process_block(self, block: Block):
        for transaction in block.transactions:
            self.process_transaction(transaction)
            # Remove from pool
            try:
                self.transaction_pool.remove(transaction)
            except ValueError:
                pass

    def new_block(self, block: Block):
        # Main chain
        if self.validate_block(block, self.latest_block()):
            self.process_block(block)
            self.chain[block.header] = block.transactions
            self.send_queue.put(('new_block', block, 'broadcast'))
        else:
            print_debug_info('Block not for main chain')

        self.check_new_chain(block)

    def validate_block(self, block: Block, last_block: Block) -> bool:
        if not super().validate_block(block, last_block):
            return False

        return all(self.validate_transaction(t) for t in block.transactions)

    def validate_transaction(self, transaction: DDosTransaction):
        if not str(transaction.sender) in self.tree:
            print_debug_info('Sender could not be found in invited clients.')
            return False

        if not self.valid_operation(transaction):
            return False

        try:
            verify_key = nacl.signing.VerifyKey(
                transaction.sender, encoder=nacl.encoding.HexEncoder)
            transaction_hash = verify_key.verify(
                transaction.signature).decode()
            hash_str = (str(transaction.sender) +
                        str(transaction.data) +
                        str(transaction.timestamp))
            validate_hash = self.hash(hash_str)

            if validate_hash == transaction_hash:
                print_debug_info('Signature OK')
                return True
            print_debug_info('Wrong Hash')
            return False

        except BadSignatureError:
            print_debug_info('Bad Signature, Validation Failed')
            return False

    def create_m_blocks(self):
        t_amount = len(self.transaction_pool)
        for i in range(0, t_amount, 5):
            if i+5 > t_amount:
                break
            header = DDosHeader(self.version,
                                len(self.chain),
                                time(),
                                self.latest_block().header.root_hash,
                                self.create_merkle_root(
                                    self.transaction_pool[i:i+5]
                                ))
            block = Block(header,
                          list(self.transaction_pool[i:i+5]))
            self.new_block(block)

    def create_block(self, proof: Any) -> Block:
        header = DDosHeader(self.version,
                            len(self.chain),
                            time(),
                            self.latest_block().header.root_hash,
                            self.create_merkle_root(self.transaction_pool)
                            )

        block = Block(header,
                      list(self.transaction_pool))

        return block

    def create_proof(self, miner_key: bytes) -> Any:
        return 0

    def process_message(self, message: Tuple[str, Any, Address]):
        """ Create processor for incoming blockchain messages.

        Returns:
            Processor (function) that processes blockchain messages.
        """
        
        msg_type, msg_data, msg_address = message
        if msg_type == 'get_ips':
            if msg_address == 'local':
                pprint(self.get_ips())
            elif msg_address == 'daemon':
                self.save_ips_to_file()
            else:
                return
        elif msg_type == 'show_children':
            if not msg_address == 'local':
                return
            node = self.tree.get_node_by_content(str(msg_data))
            node.print()
        else:
            super(DDosChain, self).process_message(message)
