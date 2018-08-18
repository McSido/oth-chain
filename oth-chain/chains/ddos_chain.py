from nacl.exceptions import BadSignatureError

from .blockchain import Blockchain, Block, Address
from utils import Node, print_debug_info
from collections import namedtuple
from typing import Any, List, Tuple, Callable, Dict
from queue import Queue
from pprint import pprint
from time import time

import nacl.signing
import nacl.encoding

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
        # TODO: load from file

        self.chain[DDosHeader(0, 0, 768894480, 0, 0)] = []

    def process_transaction(self, transaction: DDosTransaction):
                # INVITE
        if transaction.data.type == 'i':
            if str(transaction.data.data) in self.tree:
                return
            new_node = Node(str(transaction.data.data))
            parent = self.tree.get_node_by_content(str(transaction.sender))
            parent.add_child(new_node)

        # UNINVITE
        elif transaction.data.type == 'ui':
            if str(transaction.data.data) not in self.tree:
                return
            node_to_remove = self.tree.get_node_by_content(
                str(transaction.data.data))
            sender_node = self.tree.get_node_by_content(
                str(transaction.sender))
            if node_to_remove.content not in sender_node:
                print_debug_info('No permission to delete this node!')
                return
            self.tree.remove_node(node_to_remove, False)

        # BLOCK IP
        elif transaction.data.type == 'b':
            if transaction.data.data in self.blocked_ips:
                ancestors = self.blocked_ips[transaction.data.data].\
                    get_ancestors()
                if (str(transaction.sender) in [a.content for a in ancestors]):
                    # Escalate blocked-IP to ancestor
                    for a in ancestors:
                        if a.content == str(transaction.sender):
                            self.blocked_ips[transaction.data.data] = a
                            break
                else:
                    print_debug_info('IP was already blocked')
                    return
            else:
                self.blocked_ips[transaction.data.data] =\
                    self.tree.get_node_by_content(
                    str(transaction.sender))

        # UNBLOCK IP
        elif transaction.data.type == 'ub':
            if transaction.data.data in self.blocked_ips:
                if str(transaction.sender) ==\
                        self.blocked_ips[transaction.data.data].content:
                    del(self.blocked_ips[transaction.data.data])
                    return

                ancestors = self.blocked_ips[transaction.data.data].\
                    get_ancestors()
                if (str(transaction.sender) in [a.content for a in ancestors]):
                    # IP blocked from descendant
                    del(self.blocked_ips[transaction.data.data])
                    return
                else:
                    print_debug_info('IP was already blocked')
                    return

            else:
                print_debug_info('Trying to unblock IP that was not blocked')
                return
        # PURGE
        elif transaction.data.type == 'p':
            if str(transaction.data.data) not in self.tree:
                return
            node_to_remove = self.tree.get_node_by_content(
                str(transaction.data.data))
            sender_node = self.tree.get_node_by_content(
                str(transaction.sender))
            if node_to_remove.content not in sender_node:
                print_debug_info('No permission to delete this node!')
                return
            self.tree.remove_node(node_to_remove, False)
            index_list = []
            # Remove all ips blocked from this client
            for i, t in enumerate(self.blocked_ips.items()):
                blocker = t[1]
                if blocker == node_to_remove.content:
                    index_list.append(i)
            for index in index_list:
                del(self.blocked_ips[index])

    def new_transaction(self, transaction: DDosTransaction):
        if not self.validate_transaction(transaction):
            print_debug_info('Invalid transaction')
            return

        if transaction in self.transaction_pool:
            print_debug_info('Transaction already in pool')
            return

        self.transaction_pool.append(transaction)
        self.send_queue.put(('new_transaction', transaction, 'broadcast'))
        if len(self.transaction_pool) >= 5:
            self.new_block(self.create_block(self.create_proof(b'0')))

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

    def validate_block(self, block: Block, last_block: Block) -> bool:
        if not super().validate_block(block, last_block):
            return False

        return all(self.validate_transaction(t) for t in block.transactions)

    def validate_transaction(self, transaction: DDosTransaction):
        if not str(transaction.sender) in self.tree:
            print_debug_info('Sender could not be found in invited clients.')
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

            # Validate right management

            if validate_hash == transaction_hash:
                print_debug_info('Signature OK')
                return True
            print_debug_info('Wrong Hash')
            return False

        except BadSignatureError:
            print_debug_info('Bad Signature, Validation Failed')
            return False

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

    def resolve_conflict(self, new_chain: List[DDosHeader]):
        pass

    def process_message(self) -> Callable[[str, Any, Address], Any]:
        """ Create processor for incoming blockchain messages.

        Returns:
            Processor (function) that processes blockchain messages.
        """

        # Blockchain

        def new_block_inner(msg_data: Any, _: Address):
            assert isinstance(msg_data, Block)
            self.new_block(msg_data)

        def new_transaction_inner(msg_data: Any, _: Address):
            assert isinstance(msg_data, DDosTransaction)
            if msg_data.sender != '0':
                self.new_transaction(msg_data)

        def resolve_conflict_inner(msg_data: Any, _: Address):
            assert isinstance(msg_data, list)
            assert all(isinstance(header, DDosHeader) for header in msg_data)
            self.resolve_conflict(msg_data)

        def get_block_inner(msg_data: Any, msg_address: Address):
            assert isinstance(msg_data, DDosHeader)
            self.send_block(msg_data, msg_address)

        def new_header_inner(msg_data: Any, _: Address):
            assert isinstance(msg_data, DDosHeader)
            self.new_header(msg_data)

        def save_chain(_: Any, msg_address: Address):
            if msg_address != 'local':
                return
            self.save_chain()

        # Utils

        def dump_vars(_: Any, msg_address: Address):
            if msg_address == 'gui':
                self.gui_queue.put(
                    ('dump', (self.chain, self.transaction_pool), 'local'))
                self.gui_ready = True
                return
            if msg_address != 'local':
                return
            pprint(vars(self))

        # DDOS

        def get_ips_inner(msg_data: Any, msg_address: Address):
            if msg_address == 'local':
                pprint(self.get_ips())
            elif msg_address == 'daemon':
                self.save_ips_to_file()
            else:
                return

        def show_children(msg_data: Any, msg_address: Address):
            if not msg_address == 'local':
                return
            node = self.tree.get_node_by_content(str(msg_data))
            node.print()

        commands: Dict[str, Callable[[Any, Address], Any]] = {
            'new_block': new_block_inner,
            'new_transaction': new_transaction_inner,
            'resolve_conflict': resolve_conflict_inner,
            'save': save_chain,
            'dump': dump_vars,
            'get_block': get_block_inner,
            'new_header': new_header_inner,
            'get_ips': get_ips_inner,
            'show_children': show_children
        }

        def processor(msg_type: str, msg_data: Any,
                      msg_address: Address) -> Any:
            commands[msg_type](msg_data, msg_address)

        return processor
