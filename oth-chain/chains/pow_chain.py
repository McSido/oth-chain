""" Implementation of a Proof-of-Work blockchain.
"""

import hashlib
import math
import time
from pprint import pprint
from typing import Any, Callable, Dict, List, Tuple

import nacl.encoding
import nacl.signing
from nacl.exceptions import BadSignatureError
from collections import OrderedDict

from .blockchain import Block, Blockchain, Transaction, Header
from networking import Address
from utils import print_debug_info


class PoW_Blockchain(Blockchain):
    """ Implementation of a Proof-of-Work blockchain.

    Args:
        send_queue: Queue for messages to other nodes.
        gui_queue: Queue for interaction with the gui.
    """

    def validate_block(self,
                       block: Block,
                       last_block: Block,
                       new_chain: bool) -> bool:
        """ Validates a provided block.

        Takes the previous block in the chain into account
        by validating the hash of the previous block and
        all transactions in the new block.

        Args:
            block: The block to be validated.
            last_block: The last block of the chain,
                upon which validation of the hash is based.
            new_chain: Validate transaction for new chain?

        Returns:
            The validity (True/False) of the block
        """
        if not super().validate_block(block, last_block, new_chain):
            return False

        # check if the proof of the new block is valid
        mining_transaction = None
        mining_transaction_found = False
        # validate all transactions
        for transaction in block.transactions:
            if transaction.sender == '0' and transaction.signature == '0':
                if mining_transaction_found:
                    return False
                mining_transaction = transaction
                mining_transaction_found = True
                if not self.validate_proof(last_block, block.header.proof,
                                           mining_transaction.recipient):
                    return False
                fee_sum = 0
                for block_transaction in block.transactions:
                    fee_sum += block_transaction.fee
                reward_multiplicator = math.floor(block.header.index / 10) - 1

                mining_reward = 50 >> 2 ** reward_multiplicator \
                    if reward_multiplicator >= 0 else 50

                if not mining_reward + fee_sum == transaction.amount:
                    return False
            elif not self.validate_transaction(transaction,
                                               new_chain, mining=True):
                return False
        return True

    def validate_transaction(self,
                             transaction: Transaction,
                             new_chain: bool,
                             mining: bool = False) -> bool:
        """ Validates a single transaction.

        Validates the signature, the signed hash of the signature
        and checks if the transaction amount is covered by the users balance.

        Args:
            transaction: The transaction to be validated.
            new_chain: Validate transaction for new chain?
            mining: If False, the function invalidates transaction,
                        that are already in the transaction pool.
                    If True, the function checks all transactions in the block
                        being mined.

        Returns:
            The validity (True/False) of the transaction.
        """
        if not transaction.amount > 0:
            print_debug_info(
                'Received transaction with amount' +
                f' {transaction.amount} lower or equal to zero')

            return False
        if transaction in self.transaction_pool and not mining:
            return False
        # if transaction.sender == '0' and transaction.signature == '0':
        #    return True
        try:
            verify_key = nacl.signing.VerifyKey(
                transaction.sender, encoder=nacl.encoding.HexEncoder)
            transaction_hash = verify_key.verify(
                transaction.signature).decode()
            validate_hash = hashlib.sha256(
                (str(transaction.sender) + str(transaction.recipient) +
                 str(transaction.amount) + str(transaction.fee)
                 + str(transaction.timestamp)).encode()
            ).hexdigest()

            if validate_hash == transaction_hash:
                print_debug_info('Signature OK')
                return self.validate_balance(transaction)
            print_debug_info('Wrong Hash')
            return False

        except BadSignatureError:
            print_debug_info('Bad Signature, Validation Failed')
            return False

    def validate_balance(self, transaction: Transaction):
        balance = self.check_balance(
            transaction.sender, transaction.timestamp)
        if balance >= transaction.amount + transaction.fee:
            print_debug_info(
                'Balance sufficient, transaction is valid')
            return True
        print_debug_info(
            'Balance insufficient, transaction is invalid')
        print_debug_info(
            f'Transaction at fault: {transaction} ' +
            f'was not covered by balance: {balance}')
        return False

    def create_proof(self, miner_key: bytes) -> int:
        """ Create proof of work.

        Find a number that fullfills validate_proof().
        Can take some time, depending on blockchain difficulty.

        Args:
            miner_key: The (public) key of the miner.

        Returns:
            The calculated proof.
        """
        proof = 0
        last_block = self.latest_block()
        while self.validate_proof(last_block, proof, miner_key) is False:
            proof += 1
        return proof

    def validate_proof(self, last_block: Block,
                       proof: int, miner_key: bytes) -> bool:
        """ Check if a proof is valid.

        A proof is valid if the hash of the combination of it combined
        with the previous proof has as many leading 0 as set by the
        difficulty.

        Args:
            last_block: The last block of the chain.
            proof: The proof for the block being mined.
            miner_key: The (public) key of the miner.

        Returns:
            Validity(True/False) of the proof
        """
        difficulty = self.scale_difficulty(last_block)
        test_proof = f'{last_block.header.proof}{proof}{miner_key}'.encode()
        test_hash = self.hash(test_proof)
        return test_hash[:difficulty] == '0' * difficulty

    @staticmethod
    def scale_difficulty(last_block: Block) -> int:
        """ Example implementation of a scaling difficulty curve.

        Difficulty rises fast in the beginning and slower towards later blocks,
        reaching a difficulty of 4 at ~3k blocks
        and holding it until ~23k blocks

        Arguments:
            last_block: Difficulty is scaled upon the index of the last block.

        Returns:
            The difficulty for the current block.
        """
        try:
            difficulty = max(math.floor(
                math.log(last_block.header.index) / 2), 1)
        except ValueError:
            difficulty = 1
        return difficulty

    def process_message(self, message: Tuple[str, Any, Address]):
        """ Receives a message and interprets it
        """
        msg_type, msg_data, msg_address = message
        if msg_type == 'print_balance':
            balance = self.check_balance(msg_data[0], msg_data[1])
            if msg_address == 'gui':
                self.gui_queue.put(('balance', balance, 'local'))
            else:
                print(
                    'Current Balance: ' +
                    f'{balance}')
        elif msg_type == 'mine':
            self.mine(msg_data, msg_address)
        else:
            super(PoW_Blockchain, self).process_message(message)

    @property
    def difficulty(self) -> int:
        """ Get current difficulty of the blockchain.

        Returns:
            Difficulty of the current block.
        """
        return self.scale_difficulty(self.latest_block())

    def mine(self, msg_data: Any, msg_address: Address):
        """ Mines a new block.
            Args:
                msg_data: The key of the miner
                msg_address: -
        """
        if msg_address != 'local':
            return
        proof = self.create_proof(msg_data)
        block = self.create_block(proof)
        fee_sum = 0
        for transaction in block.transactions:
            fee_sum += transaction.fee
        reward_multiplier = math.floor(block.header.index / 10) - 1
        mining_reward = 50 >> 2 ** reward_multiplier \
            if reward_multiplier >= 0 else 50
        block.transactions.append(
            Transaction(sender='0', recipient=msg_data,
                        amount=mining_reward + fee_sum, fee=0,
                        timestamp=time.time(), signature='0'))
        self.new_block(self.prepare_new_block(block))

    def prepare_new_block(self, block: Block) -> Block:
        root_hash = self.create_merkle_root(block.transactions)
        real_header = Header(
            block.header.version,
            block.header.index,
            block.header.timestamp,
            block.header.previous_hash,
            root_hash,
            block.header.proof
        )
        real_block = Block(real_header, block.transactions)
        return real_block
