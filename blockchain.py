import hashlib
from collections import namedtuple
from time import time

Transaction = namedtuple(
    'Transaction', ['sender', 'recipient', 'amount', 'timestamp'])
Block = namedtuple('Block', ['index', 'timestamp',
                             'transactions', 'proof', 'previous_hash'])


class Blockchain (object):
    """ Abstract class of a blockchain
    Arguments:
    broadcast_queue -> Queue for messages to other nodes
    """

    def __init__(self, broadcast_queue):
        self.chain = []
        self.transaction_pool = []
        self.broadcast_queue = broadcast_queue
        self.load_chain()

    def load_chain(self):
        # TODO: Load preexisting blockchain from file

        # If file doesn't exist / is empty:
        # Create genesis block
        self.chain.append(Block(0, 0, [], 0, 0))

    def new_transaction(self, transaction):
        """ Add a new transaction to the blockchain
        Arguments:
        transaction -> Type as namedtuple at the top of the file
        """
        if self.validate_transaction(transaction):
            self.transaction_pool.append(transaction)
            self.broadcast_queue.put(('new_transaction', transaction))
        else:
            print('### DEBUG ### Invalid transaction')

    def new_block(self, block):
        """ Add a new block to the blockchain
        Arguments:
        block -> Type as namedtuple at the top of the file
        """
        if self.validate_block(block):
            self.transaction_pool = []
            self.chain.append(block)
            self.broadcast_queue.put(('new_block', block))
        else:
            print('### DEBUG ### Invalid block')

    def validate_block(self, block):
        """ Validate a block
        Abstract function!
        Arguments:
        block -> Type as namedtuple at the top of the file
        """
        raise NotImplementedError

    def validate_transaction(self, transaction):
        """ Validate a transaction
        Abstract function!
        Arguments:
        transaction -> Type as namedtuple at the top of the file
        """
        raise NotImplementedError

    def create_block(self, proof):
        """ Create a new block
        Arguments:
        proof -> Proof for the new block

        Returns the create block
        """
        block = Block(len(self.chain) + 1,
                      time(),
                      self.transaction_pool,
                      proof,
                      self.hash(self.chain[-1])
                      )
        return block

    def create_proof(self):
        """ Create a proof for a new block
        Abstract function!

        Returns a proof
        """
        raise NotImplementedError

    def resolve_conflict(self):
        """ Resolve conflict between to blockchains/forks
        Abstract function!
        """
        raise NotImplementedError

    @staticmethod
    def hash(data):
        """ Create a sha256 hash of the argument
        Arguments:
        data -> Data that should be hashed

        Returns hash-value
        """
        return hashlib.sha256(str(data).encode()).hexdigest()
