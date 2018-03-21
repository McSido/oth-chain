""" Testing module for the Proof-Of-Work implementation
    of the blockchain client.
"""

from queue import Queue
import nacl.signing
import nacl.encoding
import time
import hashlib
import math

import pow_chain


class Test_POW():
    """ Testcase used to bundle all tests for the
        Proof-Of-Work blockchain
    """

    def setup(self):
        """ Setup of the blockchain for the tests
        """
        self.sends = Queue()
        self.blockchain = pow_chain.PoW_Blockchain(self.sends, 0)
        self.sender_sign = nacl.signing.SigningKey(seed=b'a'*32)
        self.sender_verify = self.sender_sign.verify_key.encode(
            nacl.encoding.HexEncoder)
        self.receiver_sign = nacl.signing.SigningKey(seed=b'b'*32)
        self.receiver_verify = self.receiver_sign.verify_key.encode(
            nacl.encoding.HexEncoder)

    def test_block(self):
        """ Test that the block creation works as intended
        """
        proof = self.blockchain.create_proof(self.sender_verify)
        block = self.blockchain.create_block(proof)
        mining_transaction = \
            pow_chain.Transaction(sender='0',
                                  recipient=self.sender_verify,
                                  amount=50,
                                  fee=0,
                                  timestamp=time.time(),
                                  signature='0')

        block.transactions.append(mining_transaction)

        self.blockchain.new_block(block)

        assert self.blockchain.latest_block() == block
        assert (mining_transaction in
                self.blockchain.latest_block().transactions)
        assert self.blockchain.check_balance(
            self.sender_verify, time.time()) == 50

    def test_transaction_invalid_balance(self):
        """ Test that the transactions with invalid balances are recognized and
            not added to the blockchain
        """
        amount = 10
        timestamp = time.time()

        fee = math.ceil(amount * 0.05)
        transaction_hash = hashlib.sha256(
            (str(self.sender_verify) + str(self.receiver_verify) +
             str(amount) + str(fee) + str(timestamp)).encode()
        ).hexdigest()

        transaction = pow_chain.Transaction(
            self.sender_verify,
            self.receiver_verify,
            amount,
            fee,
            timestamp,
            self.sender_sign.sign(transaction_hash.encode())
        )

        assert not self.blockchain.validate_transaction(transaction)

        self.blockchain.new_transaction(transaction)

        assert transaction not in self.blockchain.transaction_pool
        assert self.sends.empty()

    def test_transaction_invalid_signature(self):
        """ Test that the transactions with invalid signatures are recognized
            and not added to the blockchain
        """
        self.mine_block()

        amount = 10
        timestamp = time.time()

        fee = math.ceil(amount * 0.05)
        transaction_hash = hashlib.sha256(
            (str(self.sender_verify) + str(self.receiver_verify) +
             str(amount) + str(fee) + str(timestamp)).encode()
        ).hexdigest()

        transaction = pow_chain.Transaction(
            self.sender_verify,
            self.receiver_verify,
            amount,
            fee,
            timestamp,
            self.receiver_sign.sign(transaction_hash.encode())
        )

        assert not self.blockchain.validate_transaction(transaction)

        self.blockchain.new_transaction(transaction)

        assert transaction not in self.blockchain.transaction_pool
        assert self.sends.empty()

    def test_transaction_invalid_double(self):
        """ Test that the same transaction is not added twice to the blockchain
        """
        self.mine_block()

        amount = 10
        timestamp = time.time()

        fee = math.ceil(amount * 0.05)
        transaction_hash = hashlib.sha256(
            (str(self.sender_verify) + str(self.receiver_verify) +
             str(amount) + str(fee) + str(timestamp)).encode()
        ).hexdigest()

        transaction = pow_chain.Transaction(
            self.sender_verify,
            self.receiver_verify,
            amount,
            fee,
            timestamp,
            self.sender_sign.sign(transaction_hash.encode())
        )

        assert self.blockchain.validate_transaction(transaction)

        self.blockchain.new_transaction(transaction)

        assert transaction in self.blockchain.transaction_pool
        assert not self.sends.empty()

        assert not self.blockchain.validate_transaction(transaction)

    def test_transaction_valid(self):
        """ Test that a valid transaction is recognized and added to the
            blockchain
        """
        self.mine_block()

        amount = 10
        timestamp = time.time()

        fee = math.ceil(amount * 0.05)
        transaction_hash = hashlib.sha256(
            (str(self.sender_verify) + str(self.receiver_verify) +
             str(amount) + str(fee) + str(timestamp)).encode()
        ).hexdigest()

        transaction = pow_chain.Transaction(
            self.sender_verify,
            self.receiver_verify,
            amount,
            fee,
            timestamp,
            self.sender_sign.sign(transaction_hash.encode())
        )

        assert self.blockchain.validate_transaction(transaction)

        self.blockchain.new_transaction(transaction)

        assert transaction in self.blockchain.transaction_pool
        assert not self.sends.empty()

    def mine_block(self):
        """ Mine an initial block to add a balance to the test account
        """

        proof = self.blockchain.create_proof(self.sender_verify)
        block = self.blockchain.create_block(proof)
        block.transactions.append(
            pow_chain.Transaction(sender='0',
                                  recipient=self.sender_verify,
                                  amount=50,
                                  fee=0,
                                  timestamp=time.time(),
                                  signature='0'))
        self.blockchain.new_block(block)
        self.sends.get(timeout=1)  # Remove new_block message