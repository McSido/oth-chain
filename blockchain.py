""" Abstract implementation of a blockchain
"""
import hashlib
import math
import os
import pickle
from collections import OrderedDict, namedtuple
from pathlib import Path
from pprint import pprint
from queue import Queue
from time import time
from typing import Any, Callable, List

from networking import Address
from utils import print_debug_info

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

    def __init__(self, version: float, send_queue: Queue) -> None:
        self.chain: OrderedDict[Header, List[Transaction]] = OrderedDict()
        self.new_chain: OrderedDict[Header, List[Transaction]] = OrderedDict()
        self.transaction_pool: List[Transaction] = []
        self.send_queue = send_queue
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
            with open('bc_file.txt', 'rb') as bc_file:
                self.chain = pickle.load(bc_file)
        else:
            # If file doesn't exist / is empty:
            # Create genesis block

            self.chain[Header(0, 0, 768894480, 0, 0, 0)] = []

    def save_chain(self):
        """ Save the current chain to the hard drive.
        """
        pprint('saving to file named bc_file.txt')
        with open('bc_file.txt', 'wb') as output:
            pickle.dump(self.chain, output,
                        pickle.HIGHEST_PROTOCOL)

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
        else:
            print_debug_info('Invalid transaction')

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
            else:
                print_debug_info('Block not for current chain')

        if block.header in self.new_chain:
            if self.validate_block(block, self.nc_latest_block()):
                # Validate transactions only after full chain
                self.new_chain[block.header] = block.transactions

                # Check if new chain is finished
                if not any(t is None for t in self.new_chain.values()):
                    self.send_queue.put(
                        ('new_header', self.nc_latest_header(), 'broadcast'))
                    self.chain = OrderedDict(self.new_chain)
                    self.new_chain.clear()

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
        """ Validate a header.

        Abstract function!

        Args:
            header: Header that should be validated
            last_header: Header of current last block.
        """
        raise NotImplementedError

    def validate_block(self, block: Block, last_block: Block) -> bool:
        """ Validate a block.

        Abstract function!

        Args:
            block: Block that should be validated
            last_block: Current last block.
        """
        raise NotImplementedError

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

    def process_message(self) -> Callable:
        """ Currently does nothing
        """
        raise NotImplementedError

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

    def get_block(self, header: Header) -> Block:
        """ Get the block corresponding to the header

        Args:
            header: Header of the block

        Returns:
            The block corresponding to the header
        """
        return Block(header, self.chain[header])

    def send_block(self, header: Header, address: Address):
        """ Send block corresponding to the header to the address

        Args:
            header: Header of the block
            address: Address of the receiver
        """
        self.send_queue.put(('new_block', self.get_block(header), address))

    @staticmethod
    def create_merkle_root(transactions: List[Transaction]) -> str:
        """ Calculate the merkle root of the transactions.


        Args:
            transaction: List of transactions

        Returns:
            Merkle root of transactions.
        """

        # Hash empty transaction list
        # Should only exist in Genesis Block
        if not transactions:
            return Blockchain.hash(transactions)

        # Create leaf-hash

        hash_list = list(map(
            lambda t: Blockchain.hash(t),
            sorted(transactions, key=lambda i_t: i_t.timestamp)))

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
            print(hash_list)
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
