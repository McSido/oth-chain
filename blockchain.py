""" Abstract implementation of a blockchain
"""
import hashlib
import os
import pickle
from collections import namedtuple
from pathlib import Path
from pprint import pprint
from time import time

from utils import print_debug_info

Transaction = namedtuple(
    'Transaction',
    ['sender', 'recipient', 'amount', 'fee', 'timestamp', 'signature'])

Block = namedtuple('Block', ['index', 'timestamp',
                             'transactions', 'proof', 'previous_hash'])


class Blockchain(object):
    """ Abstract class of a blockchain

    Args:
        send_queue: Queue for messages to other nodes
    """

    def __init__(self, send_queue):
        self.chain = []
        self.transaction_pool = []
        self.send_queue = send_queue
        self.load_chain()

    def check_balance(self, key, timestamp):
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
        for block in self.chain:
            for transaction in block.transactions:
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
            self.chain.append(Block(0, 768894480, [], 0, 0))

    def save_chain(self):
        """ Save the current chain to the hard drive.
        """
        pprint('saving to file named bc_file.txt')
        with open('bc_file.txt', 'wb') as output:
            pickle.dump(self.chain, output,
                        pickle.HIGHEST_PROTOCOL)

    def new_transaction(self, transaction):
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

    def new_block(self, block):
        """ Add a new block to the blockchain.

        Args:
            block: Block that sould be added.
        """
        if block.index > self.latest_block().index + 1:
            # block higher then current chain:
            # resolve conflict between chains
            self.send_queue(('resolve_conflict', self.chain, 'broadcast'))

        if self.validate_block(block, self.chain[:-1]):
            for block_transaction in block.transactions:
                if block_transaction in self.transaction_pool:
                    self.transaction_pool.remove(block_transaction)
            self.chain.append(block)
            self.send_queue.put(('new_block', block, 'broadcast'))
        else:
            print_debug_info('Invalid block')

    def validate_block(self, block, last_block):
        """ Validate a block.

        Abstract function!

        Args:
            block: Block that should be validated
            last_block: Current last block.
        """
        raise NotImplementedError

    def validate_transaction(self, transaction):
        """ Validate a transaction.

        Abstract function!

        Args:
            transaction: Transaction that should be validated
        """
        raise NotImplementedError

    def create_block(self, proof):
        """ Create a new block.

        Args:
            proof: Proof for the new block.

        Returns:
            The created block.
        """
        block = Block(len(self.chain),
                      time(),
                      list(self.transaction_pool),
                      proof,
                      self.hash(self.chain[-1])
                      )
        return block

    def create_proof(self, miner_key):
        """ Create a proof for a new block.

        Abstract function!

        Args:
            miner_key: Key of the current miner.

        Returns:
            A proof
        """
        raise NotImplementedError

    def resolve_conflict(self, new_chain):
        """ Resolve conflict between to blockchains/forks.

        Abstract function!

        Arguments:
            new_chain: Other blockchain to compare against the current.
        """
        raise NotImplementedError

    def process_message(self):
        """ Currently does nothing
        """
        raise NotImplementedError

    def latest_block(self):
        """ Get the latest block.

        Returns:
            The latest block on the chain.
        """
        return self.chain[-1]

    @staticmethod
    def hash(data):
        """ Create a sha256 hash of the argument.

        Args:
            data: Data that should be hashed.

        Returns:
            A hash of the data.
        """
        return hashlib.sha256(str(data).encode()).hexdigest()
