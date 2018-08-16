from nacl.exceptions import BadSignatureError

from .blockchain import Blockchain, Block, Address
from utils import Node, print_debug_info
from collections import namedtuple
from typing import Any, List, Tuple, Callable, Dict
from queue import Queue
from pprint import pprint

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

    def load_chain(self):
        pass

    def new_transaction(self, transaction: DDosTransaction):
        if not self.validate_transaction(transaction):
            print_debug_info('Invalid transaction')
            return

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
            pass

        self.transaction_pool.append(transaction)
        self.send_queue.put(('new_transaction', transaction, 'broadcast'))

    def new_block(self, block: Block):
        pass

    def validate_block(self, block: Block, last_block: Block) -> bool:
        pass

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

            if validate_hash == transaction_hash:
                print_debug_info('Signature OK')
                return True
            print_debug_info('Wrong Hash')
            return False

        except BadSignatureError:
            print_debug_info('Bad Signature, Validation Failed')
            return False

    def create_block(self, proof: Any) -> Block:
        pass

    def create_proof(self, miner_key: bytes) -> Any:
        pass

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
                # Write to disk
                pass
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

    def validate_header(self,
                        header: DDosHeader,
                        last_header: DDosHeader) -> bool:
        pass
