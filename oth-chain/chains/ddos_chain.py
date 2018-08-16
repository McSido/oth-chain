from .blockchain import Blockchain, Block, Address
from collections import namedtuple
from typing import Any, List, Tuple, Callable, Dict
from queue import Queue
from pprint import pprint

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

    def get_ips(self):
        pass

    def load_chain(self):
        pass

    def new_transaction(self, transaction: DDosTransaction):
        pass

    def new_block(self, block: Block):
        pass

    def validate_block(self, block: Block, last_block: Block) -> bool:
        pass

    def validate_transaction(self, transaction: DDosTransaction):
        pass

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
            pass

        def show_children(msg_data: Any, msg_address: Address):
            pass

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
