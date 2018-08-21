""" Abstract implementation of a blockchain
"""
import hashlib
import math
import os
from collections import OrderedDict, namedtuple
from pathlib import Path
from pprint import pprint
from queue import Queue
from time import time
from typing import Any, Callable, List, Optional, Tuple

from utils import print_debug_info
from networking import Address

import serializer

Transaction = namedtuple('Transaction',
                         ['sender',
                          'recipient',
                          'amount',
                          'fee',
                          'timestamp',
                          'signature'])

Block = namedtuple('Block',
                   ['header',
                    'transactions'])

Header = namedtuple('Header',
                    ['version',
                     'index',
                     'timestamp',
                     'previous_hash',
                     'root_hash',
                     'proof'])


class Blockchain(object):
    """ Abstract class of a blockchain

    Args:
        send_queue: Queue for messages to other nodes
    """

    def __init__(self,
                 version: float,
                 send_queue: Queue,
                 gui_queue: Queue) -> None:
        self.chain: OrderedDict[Header, List[Transaction]] = OrderedDict()
        self.new_chain: OrderedDict[Header, List[Transaction]] = OrderedDict()
        self.transaction_pool: List[Transaction] = []
        self.intermediate_transactions: List[Transaction] = []
        self.send_queue = send_queue
        self.gui_ready = False
        self.gui_queue = gui_queue
        self.load_chain()
        self.version = version

    def check_balance(self, key: bytes, timestamp: float) -> int:
        """ Checks the amount of coins a certain user (identified by key) has.

            Calculates balance by iterating through the chain and checking the
            amounts of money the user sent or received before the timestamp.

        Args:
            key: Key that identifies the user.
            timestamp: Limits until what point the balance is calculated.

        Returns:
            The balance of the user at the given timestamp.
        """
        balance = 0
        for block_transactions in self.chain.values():
            for transaction in block_transactions:
                if transaction.sender == key:
                    balance -= transaction.amount + transaction.fee
                if transaction.recipient == key:
                    balance += transaction.amount
        for transaction in self.transaction_pool:
            if transaction.sender == key and transaction.timestamp < timestamp:
                balance -= transaction.amount + transaction.fee
            if transaction.recipient == key and \
                    transaction.timestamp < timestamp:
                balance += transaction.amount
        return balance

    def load_chain(self):
        """ Loads Blockchain from the hard drive.
        """
        if os.path.exists('bc_file.txt') and \
                os.stat('bc_file.txt').st_size != 0 and \
                Path('bc_file.txt').is_file():
            print_debug_info(
                'Load existing blockchain from file')
            with open('bc_file.txt', 'r') as bc_file:
                self.chain = serializer.deserialize(bc_file.read())
        else:
            # If file doesn't exist / is empty:
            # Create genesis block

            self.chain[Header(0, 0, 768894480, 0, 0, 0)] = []

    def save_chain(self):
        """ Save the current chain to the hard drive.
        """
        pprint('saving to file named bc_file.txt')
        with open('bc_file.txt', 'w') as output:
            output.write(serializer.serialize(self.chain))

    def new_transaction(self, transaction: Transaction):
        """ Add a new transaction to the blockchain.

        Args:
            transaction: Transaction that should be added.
        """
        # Make sure, only one mining reward is granted per block
        for pool_transaction in self.transaction_pool:
            if pool_transaction.sender == '0' and \
                    pool_transaction.signature == '0':
                print_debug_info(
                    'This block already granted a mining transaction!')
                return
        if transaction in self.latest_block().transactions:
            return
        if self.validate_transaction(transaction):
            self.transaction_pool.append(transaction)
            self.send_queue.put(('new_transaction', transaction, 'broadcast'))
            if self.gui_ready:
                self.gui_queue.put(('new_transaction', transaction, 'local'))
            self.check_auction(transaction)
        else:
            print_debug_info('Invalid transaction')

    def check_auction(self, transaction: Transaction):
        pass

    def new_block(self, block: Block):
        """ Adds a provided block to the chain after checking it for validity.

        Args:
            block: The block to be added to the chain.
        """

        # Check current chain

        if block.header.index == self.latest_block().header.index + 1:
            if self.validate_block(block, self.latest_block()):
                # remove transactions in new block from own transaction pool
                for block_transaction in block.transactions:
                    if block_transaction in self.transaction_pool:
                        self.transaction_pool.remove(block_transaction)
                self.send_queue.put(('new_header', block.header, 'broadcast'))
                self.chain[block.header] = block.transactions
                if self.gui_ready:
                    self.gui_queue.put(('new_block', block, 'local'))
            else:
                print_debug_info('Block not for current chain')

        self.check_new_chain(block)

    def check_new_chain(self, block):
        if block.header in self.new_chain:
            if block.header.root_hash ==\
                    self.create_merkle_root(block.transactions):
                # Validate transactions<->header
                self.new_chain[block.header] = block.transactions

                for t in block.transactions:
                    try:
                        # Remove processed transactions
                        self.intermediate_transactions.remove(t)
                    except ValueError:
                        pass

                # Check if new chain is finished
                if not any(t is None for t in self.new_chain.values()):
                    # Validate transactions
                    old_data = next(iter(self.new_chain.items()))
                    for h, t in self.new_chain.items():
                        if h == old_data[0]:
                            continue
                        if self.validate_block(
                                Block(h, t), Block(old_data[0], old_data[1])):
                            old_data = (h, t)
                        else:
                            print_debug_info(
                                'Invalid transaction in new chain')
                            self.new_chain.clear()
                            self.intermediate_transactions.clear()

                    self.send_queue.put(
                        ('new_header', self.nc_latest_header(), 'broadcast'))
                    self.chain = OrderedDict(self.new_chain)
                    self.new_chain.clear()
                    # Remove mining transactions
                    not_processed_transactions = [
                        t for t in self.intermediate_transactions
                        if t.sender != '0']
                    self.transaction_pool = list(not_processed_transactions)
                    self.intermediate_transactions.clear()

                    # DNS specific
                    try:
                        self._sync_auctions()  # type: ignore
                    except AttributeError:
                        pass

            else:
                print_debug_info('Block not for new chain')

    def new_header(self, header: Header):
        """ Check if new header is valid and ask for the corresponding block

        Args:
            header: New block-header
        """

        if header.index > self.latest_header().index + 1:
            # block higher then current chain:
            # resolve conflict between chains
            self.send_queue.put(('get_chain', '', 'broadcast'))
            print_debug_info('Chain out-of-date.')
            print_debug_info('Updating...')
            return

        if self.validate_header(header, self.latest_header()):
            self.send_queue.put(('get_block', header, 'broadcast'))
            print_debug_info('Valid header, asked for full block')
        else:
            print_debug_info('Invalid header')

    def validate_header(self, header: Header, last_header: Header) -> bool:
        """ Validates a block-header.

        Args:
            header: Header that should be validated
            last_header: Header of current last block.
        """

        # check if previous block == last_block
        if header.previous_hash != last_header.root_hash:
            return False

        # check order of time
        if header.timestamp < last_header.timestamp:
            return False

        # Check that version of the block can be processed
        if header.version > self.version:
            print_debug_info(f'Received block with version {header.version},' +
                             ' but your current version is {self.version}.\n' +
                             'Check if there is a newer version available.')
            return False

        return True

    def validate_block(self, block: Block, last_block: Block) -> bool:
        """ Validate a block.

        Does only validate basic things.
        Override this function if needed

        Args:
            block: Block that should be validated
            last_block: Current last block.

        Returns:
            The validity (True/False) of the block
        """
        # check if the header of the block is valid
        if not self.validate_header(block.header, last_block.header):
            return False

        # Check if hash is valid
        if not self.create_merkle_root(block.transactions) ==\
                block.header.root_hash:
            return False

        return True

    def validate_transaction(self, transaction: Transaction):
        """ Validate a transaction.

        Abstract function!

        Args:
            transaction: Transaction that should be validated
        """
        raise NotImplementedError

    def create_block(self, proof: Any) -> Block:
        """ Create a new block.

        Args:
            proof: Proof for the new block.

        Returns:
            The created block.
        """
        header = Header(
            self.version,
            len(self.chain),
            time(),
            self.latest_block().header.root_hash,
            self.create_merkle_root(self.transaction_pool),
            proof
        )

        block = Block(header,
                      list(self.transaction_pool)
                      )
        return block

    def create_proof(self, miner_key: bytes) -> Any:
        """ Create a proof for a new block.

        Abstract function!

        Args:
            miner_key: Key of the current miner.

        Returns:
            A proof
        """
        raise NotImplementedError

    def resolve_conflict(self, new_chain: List[Header]):
        """ Resolve conflict between to blockchains/forks.

        Abstract function!

        Arguments:
            new_chain: Other blockchain to compare against the current.
        """
        raise NotImplementedError

    def process_message(self, message: Tuple[str, Any, Address]):
        """ Create processor for incoming blockchain messages.

        Returns:
            Processor (function) that processes blockchain messages.
        """

        msg_type, msg_data, msg_address = message
        if msg_type == 'new_block':
            assert isinstance(msg_data, Block)
            self.new_block(msg_data)
        elif msg_type == 'new_transaction':
            # assert isinstance(msg_data, Transaction)
            if msg_data.sender != '0':
                self.new_transaction(msg_data)
        elif msg_type == 'resolve_conflict':
            assert isinstance(msg_data, list)
            # assert all(isinstance(header, Header) for header in msg_data)
            self.resolve_conflict(msg_data)
        elif msg_type == 'save':
            if msg_address != 'local':
                return
            self.save_chain()
        elif msg_type == 'dump':
            if msg_address == 'gui':
                self.gui_queue.put(
                    ('dump', (self.chain, self.transaction_pool), 'local'))
                self.gui_ready = True
                return
            if msg_address != 'local':
                return
            pprint(vars(self))
        elif msg_type == 'get_block':
            # assert isinstance(msg_data, Header)
            self.send_block(msg_data, msg_address)
        elif msg_type == 'new_header':
            # assert isinstance(msg_data, Header)
            self.new_header(msg_data)

    def latest_block(self) -> Block:
        """ Get the latest block.

        Returns:
            The latest block on the chain.
        """
        return Block(self.latest_header(), self.chain[self.latest_header()])

    def latest_header(self) -> Header:
        """ Get the latest block-header.

        Returns:
            The header of the latest block on the chain.
        """
        return next(reversed(self.chain))

    def nc_latest_block(self) -> Block:
        """ Get the latest block of the new chain.

        Returns:
            The latest block on the new chain.
        """
        return Block(self.nc_latest_header(),
                     self.new_chain[self.nc_latest_header()])

    def nc_latest_header(self) -> Header:
        """ Get the latest block-header of the new chain.

        Returns:
            The header of the latest block on the new chain.
        """
        return next(reversed(self.new_chain))

    def get_header_chain(self) -> List[Header]:
        """ Get all the headers of the current chain

        Returns:
            The headers of the current chain (in order)
        """
        return list(self.chain.keys())

    def get_block_chain(self) -> List[Block]:
        """ Get all the blocks in the chain

        Returns:
            The blocks in the blockchain (in order)
        """
        return [Block(h, t) for h, t in self.chain.items()]

    def get_block(self, header: Header) -> Optional[Block]:
        """ Get the block corresponding to the header

        Args:
            header: Header of the block

        Returns:
            The block corresponding to the header
        """
        try:
            return Block(header, self.chain[header])
        except KeyError:
            return None

    def send_block(self, header: Header, address: Address):
        """ Send block corresponding to the header to the address

        Args:
            header: Header of the block
            address: Address of the receiver
        """
        s_block = self.get_block(header)
        if s_block and s_block.transactions:
            self.send_queue.put(('new_block', s_block, address))

    @staticmethod
    def create_merkle_root(transactions: List[Transaction]) -> str:
        """ Calculate the Merkle root of the transactions.


        Args:
            transactions: List of transactions

        Returns:
            Merkle root of transactions.
        """

        # Hash empty transaction list
        # Should only exist in Genesis Block
        if not transactions:
            return Blockchain.hash(transactions)

        # Create leaf-hash

        hash_list = [Blockchain.hash(t) for t in sorted(
            transactions, key=lambda i_t: i_t.timestamp)]

        # Make perfect full binary tree

        for h in range(len(hash_list)):  # Artificial max length
            if h < math.log2(len(hash_list)):
                continue
            while h != math.log2(len(hash_list)):
                hash_list.append(hash_list[-1])
            break

        # Create Merkle-tree

        t_hash: List[Any] = []

        while len(hash_list) != 1:
            t_hash.clear()
            for i in range(0, len(hash_list), 2):
                t_hash.append(Blockchain.hash(
                    hash_list[i] +
                    hash_list[i+1]
                ))
            hash_list = list(t_hash)

        return hash_list[0]

    @staticmethod
    def hash(data: Any) -> str:
        """ Create a sha256 hash of the argument.

        Args:
            data: Data that should be hashed.

        Returns:
            A hash of the data.
        """
        return hashlib.sha256(str(data).encode()).hexdigest()

    def get_message_processor(self):
        """ Returns a message processor callable"""
        def processor(message: Tuple[str, Any, Address]):
            self.process_message(message)

        return processor
