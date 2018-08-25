""" Testing module for the Proof-Of-Work implementation
of the blockchain client.
"""

import hashlib
import math
import time
from queue import Queue
from queue import Empty

import nacl.encoding
import nacl.signing

from chains import Transaction, Block, Header, PoW_Blockchain
import utils

VERSION = 0.7


class TestPOW(object):
    """ Testcase used to bundle all tests for the
    Proof-Of-Work blockchain
    """

    def setup(self):
        """ Setup of the blockchain for the tests.
        """
        utils.set_debug()

        self.sends = Queue()

        self.gui_queue = Queue()
        self.blockchain = PoW_Blockchain(VERSION, self.sends, self.gui_queue)

        self.sender_sign = nacl.signing.SigningKey(seed=b'a' * 32)
        self.sender_verify = self.sender_sign.verify_key.encode(
            nacl.encoding.HexEncoder)
        self.receiver_sign = nacl.signing.SigningKey(seed=b'b' * 32)
        self.receiver_verify = self.receiver_sign.verify_key.encode(
            nacl.encoding.HexEncoder)

    def test_block(self):
        """ Test that the block creation works as intended.
        """
        proof = self.blockchain.create_proof(self.sender_verify)
        block = self.blockchain.create_block(proof)
        mining_transaction = \
            Transaction(sender='0',
                        recipient=self.sender_verify,
                        amount=50,
                        fee=0,
                        timestamp=time.time(),
                        signature='0')

        block.transactions.append(mining_transaction)

        root_hash = self.blockchain.create_merkle_root(block.transactions)
        real_header = Header(
            block.header.version,
            block.header.index,
            block.header.timestamp,
            block.header.previous_hash,
            root_hash,
            block.header.proof
        )
        real_block = Block(real_header, block.transactions)

        self.blockchain.new_block(real_block)

        assert self.blockchain.latest_block() == real_block
        assert (mining_transaction in
                self.blockchain.latest_block().transactions)
        assert self.blockchain.check_balance(
            self.sender_verify, time.time()) == 50

    def test_transaction_invalid_balance(self):
        """ Test that the transactions with invalid balances are recognized and
        not added to the blockchain.
        """
        transaction = self.create_transaction()

        assert not self.blockchain.validate_transaction(transaction)

        self.blockchain.new_transaction(transaction)

        assert transaction not in self.blockchain.transaction_pool
        assert self.sends.empty()

    def test_transaction_invalid_signature(self):
        """ Test that the transactions with invalid signatures are recognized
        and not added to the blockchain.
        """
        self.mine_block(self.blockchain)

        transaction = self.create_transaction()
        transaction = Transaction(
            transaction.sender,
            transaction.recipient,
            transaction.amount,
            transaction.fee,
            transaction.timestamp,
            self.receiver_sign.sign(
                self.create_transaction_hash(
                    transaction.amount,
                    transaction.fee,
                    transaction.timestamp
                ).encode()
            )
        )

        assert not self.blockchain.validate_transaction(transaction)

        self.blockchain.new_transaction(transaction)

        assert transaction not in self.blockchain.transaction_pool
        assert self.sends.empty()

    def test_transaction_invalid_double(self):
        """ Test that the same transaction is not added twice to the blockchain.
        """
        self.mine_block(self.blockchain)

        transaction = self.create_transaction()

        assert self.blockchain.validate_transaction(transaction)

        self.blockchain.new_transaction(transaction)

        assert transaction in self.blockchain.transaction_pool
        assert not self.sends.empty()

        assert not self.blockchain.validate_transaction(transaction)

    def test_transaction_valid(self):
        """ Test that a valid transaction is recognized and added to the
        blockchain.
        """
        self.mine_block(self.blockchain)

        transaction = self.create_transaction()

        assert self.blockchain.validate_transaction(transaction)

        self.blockchain.new_transaction(transaction)

        assert transaction in self.blockchain.transaction_pool
        assert not self.sends.empty()

    def test_new_header(self, capsys):
        """ Test that a new incoming header is processed accordingly.
        """

        with capsys.disabled():
            proof = self.blockchain.create_proof(self.sender_verify)
            last_header = self.blockchain.latest_header()

            # Valid

            new_header = Header(0,
                                1,
                                time.time(),
                                last_header.root_hash,
                                123,
                                proof
                                )

            self.blockchain.process_message(('new_header',
                                             new_header,
                                             ''))

            assert self.sends.get() == ('get_block', new_header, 'broadcast')

        # Invalid

        new_header = Header(0,
                            1,
                            time.time(),
                            321,
                            123,
                            proof
                            )

        self.blockchain.process_message(('new_header',
                                         new_header,
                                         ''))

        captured = capsys.readouterr()
        assert captured.out == '### DEBUG ### Invalid header\n'

        # Farther away
        new_header = Header(0,
                            123,
                            time.time(),
                            321,
                            last_header.root_hash,
                            proof
                            )

        self.blockchain.process_message(('new_header',
                                         new_header,
                                         ''))

        assert self.sends.get() == ('get_chain', '', 'broadcast')

    def test_get_block(self):
        """ Test that get_block works.

        Uses latest_block for comparison.
        """
        b = self.blockchain.latest_block()

        assert b == self.blockchain.get_block(b.header)

        # Invalid header -> return None

        assert not self.blockchain.get_block('')

    def test_send_block(self):
        """ Test that send_block works.
        """
        self.mine_block(self.blockchain)
        b = self.blockchain.latest_block()

        self.blockchain.send_block(b.header, '123')

        assert self.sends.get() == ('new_block', b, '123')

    def test_merkle_root(self):
        """ Test that Merkle root is independent of transaction order.

        Only factor for the Merkle root should be timestamp of the transaction.
        """
        t = [self.create_transaction() for i in range(15)]

        assert self.blockchain.create_merkle_root(t) == \
            self.blockchain.create_merkle_root(list(reversed(t)))

    def test_msg_transaction(self):
        """ Test that the process message can process new transactions
        """

        self.mine_block(self.blockchain)

        t = self.create_transaction()
        self.blockchain.process_message(('new_transaction', t, ''))

        assert t in self.blockchain.transaction_pool

    def test_resolve_conflict(self):
        """ Test that resolve conflict works
        """

        # Initial chain

        self.mine_block(self.blockchain)

        t = self.create_transaction()

        self.blockchain.new_transaction(t)
        self.mine_block(self.blockchain)

        # Secondary chain

        bchain2 = PoW_Blockchain(VERSION,
                                 Queue(),
                                 Queue()
                                 )

        # Fill secondary chain

        for _ in range(3):
            self.mine_block(bchain2)

        bchain2.new_transaction(t)
        bchain2.process_message(('mine', self.sender_verify, 'local'))

        # Check new_chain of the initial blockchain

        self.blockchain.resolve_conflict(bchain2.get_header_chain())

        assert bchain2.latest_header() == self.blockchain.nc_latest_header()

        # Add to secondary chain, to test "pre-filling" of new_chain

        for _ in range(3):
            self.mine_block(bchain2)
        self.blockchain.resolve_conflict(bchain2.get_header_chain())
        assert bchain2.latest_header() == self.blockchain.nc_latest_header()

        # Chain exchange

        for b in bchain2.get_block_chain():
            self.blockchain.new_block(b)

        assert bchain2.latest_block() == self.blockchain.latest_block()

    # ####################### HELPER FUNCTIONS ###########################

    def mine_block(self, chain):
        """ Mine an initial block to add a balance to the test account.

        Args:
            chain: Chain to mine on
        """

        proof = chain.create_proof(self.sender_verify)
        block = chain.create_block(proof)
        block.transactions.append(
            Transaction(sender='0',
                        recipient=self.sender_verify,
                        amount=50,
                        fee=0,
                        timestamp=time.time(),
                        signature='0'))

        root_hash = chain.create_merkle_root(block.transactions)
        real_header = Header(
            block.header.version,
            block.header.index,
            block.header.timestamp,
            block.header.previous_hash,
            root_hash,
            block.header.proof
        )
        real_block = Block(real_header, block.transactions)

        chain.new_block(real_block)
        try:
            self.sends.get(block=False)  # Remove new_block message
        except Empty:
            pass

    def create_transaction(self):
        """ Create simple transaction used in tests.

        Returns:
            A new transaction.
        """

        amount = 10
        timestamp = time.time()
        fee = math.ceil(amount * 0.05)

        transaction_hash = self.create_transaction_hash(amount, fee, timestamp)

        return Transaction(
            self.sender_verify,
            self.receiver_verify,
            amount,
            fee,
            timestamp,
            self.sender_sign.sign(transaction_hash.encode())
        )

    def create_transaction_hash(self, amount, fee, timestamp):
        """ Creates the transaction-hash used in tests.

        Args:
            amount: Amount of coins for transaction.
            fee: Fee for the transaction.
            timestamp: Time of the transaction.

        Returns:
            Hash for the given transaction data
        """
        return hashlib.sha256(
            (str(self.sender_verify) + str(self.receiver_verify) +
             str(amount) + str(fee) + str(timestamp)).encode()
        ).hexdigest()
