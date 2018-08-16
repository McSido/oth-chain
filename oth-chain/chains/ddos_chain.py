from .blockchain import Blockchain, Block
from collections import namedtuple
from typing import Any, List, Tuple, Callable
from queue import Queue

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

    def __init__(self, version: float, send_queue: Queue, gui_queue: Queue) -> None:
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

    def process_message(self) -> Callable:
        pass

    def validate_header(self, header: DDosHeader, last_header: DDosHeader) -> bool:
        pass
