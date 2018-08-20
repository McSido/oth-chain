""" Implementation of a Proof-of-Work blockchain.
"""

import hashlib
import math
import time
from pprint import pprint
from typing import Any, Callable, Dict, List

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

    def validate_block(self, block: Block, last_block: Block) -> bool:
        """ Validates a provided block.

        Takes the previous block in the chain into account
        by validating the hash of the previous block and
        all transactions in the new block.

        Args:
            block: The block to be validated.
            last_block: The last block of the chain,
                upon which validation of the hash is based.

        Returns:
            The validity (True/False) of the block
        """
        if not super().validate_block(block, last_block):
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
            elif not self.validate_transaction(transaction, mining=True):
                return False
        return True

    def validate_transaction(self,
                             transaction: Transaction,
                             mining: bool = False) -> bool:
        """ Validates a single transaction.

        Validates the signature, the signed hash of the signature
        and checks if the transaction amount is covered by the users balance.

        Args:
            transaction: The transaction to be validated.
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

    def resolve_conflict(self, new_chain: List[Header]):
        """ Resolves any conflicts that occur with different/outdated chains.

        Conflicts are resolved by accepting the longest valid chain.

        Args:
            new_chain: The chain to be validated,
                received from other nodes in the network.
        """
        print_debug_info('Resolving conflict')
        if len(self.chain) < len(new_chain):
            if len(self.new_chain) < len(new_chain):
                # Validate new_chain
                old_header = new_chain[0]
                for header in new_chain[1:]:
                    if self.validate_header(header, old_header):
                        old_header = header
                    else:
                        print_debug_info('Conflict resolved (old chain)')
                        return

                # Clear intermediate transactions
                self.intermediate_transactions.clear()

                # Create blockchain from new_chain
                new_bchain: OrderedDict[Header, List[Transaction]] = \
                    OrderedDict([(h, None) for h in new_chain])

                # Add known blocks
                for h, t in self.chain.items():
                    if h in new_bchain:
                        new_bchain[h] = t
                    else:
                        # Update intermediate transactions
                        self.intermediate_transactions += t

                for h, t in self.new_chain.items():
                    if h in new_bchain:
                        new_bchain[h] = t
                        if t:
                            for i_t in t:
                                try:
                                    # Remove processed transactions
                                    self.intermediate_transactions.remove(i_t)
                                except ValueError:
                                    pass

                self.new_chain = new_bchain
                print_debug_info('Conflict (Header) resolved (new chain)')

                # Ask for missing blocks
                for h, t in self.new_chain.items():
                    if t is None:
                        self.send_queue.put(('get_block', h, 'broadcast'))

        else:
            print_debug_info('Conflict resolved (old chain)')

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

    def process_message(self) -> Callable[[str, Any, Address], Any]:
        """ Create processor for incoming blockchain messages.

        Returns:
            Processor (function) that processes blockchain messages.
        """

        def new_block_inner(msg_data: Any, _: Address):
            assert isinstance(msg_data, Block)
            self.new_block(msg_data)

        def new_transaction_inner(msg_data: Any, _: Address):
            assert isinstance(msg_data, Transaction)
            if msg_data.sender != '0':
                self.new_transaction(msg_data)

        def mine(msg_data: Any, msg_address: Address):
            if msg_address != 'local':
                return
            proof = self.create_proof(msg_data)
            block = self.create_block(proof)
            fee_sum = 0
            for transaction in block.transactions:
                fee_sum += transaction.fee
            reward_multiplier = math.floor(block.header.index / 10) - 1
            mining_reward = 50 >> 2**reward_multiplier\
                if reward_multiplier >= 0 else 50
            block.transactions.append(
                Transaction(sender='0', recipient=msg_data,
                            amount=mining_reward + fee_sum, fee=0,
                            timestamp=time.time(), signature='0'))

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
            self.new_block(real_block)

        def resolve_conflict_inner(msg_data: Any, _: Address):
            assert isinstance(msg_data, list)
            assert all(isinstance(header, Header) for header in msg_data)
            self.resolve_conflict(msg_data)

        def print_balance(msg_data: Any, msg_address: Address):
            balance = self.check_balance(msg_data[0], msg_data[1])
            if msg_address == 'gui':
                self.gui_queue.put(('balance', balance, 'local'))
            else:
                print(
                    'Current Balance: ' +
                    f'{balance}')

        def save_chain(_: Any, msg_address: Address):
            if msg_address != 'local':
                return
            self.save_chain()

        def dump_vars(_: Any, msg_address: Address):
            if msg_address == 'gui':
                self.gui_queue.put(
                    ('dump', (self.chain, self.transaction_pool), 'local'))
                self.gui_ready = True
                return
            if msg_address != 'local':
                return
            pprint(vars(self))

        def get_block_inner(msg_data: Any, msg_address: Address):
            assert isinstance(msg_data, Header)
            self.send_block(msg_data, msg_address)

        def new_header_inner(msg_data: Any, _: Address):
            assert isinstance(msg_data, Header)
            self.new_header(msg_data)

        commands: Dict[str, Callable[[Any, Address], Any]] = {
            'new_block': new_block_inner,
            'new_transaction': new_transaction_inner,
            'mine': mine,
            'resolve_conflict': resolve_conflict_inner,
            'print_balance': print_balance,
            'save': save_chain,
            'dump': dump_vars,
            'get_block': get_block_inner,
            'new_header': new_header_inner
        }

        def processor(msg_type: str, msg_data: Any,
                      msg_address: Address) -> Any:
            commands[msg_type](msg_data, msg_address)

        return processor

    @property
    def difficulty(self) -> int:
        """ Get current difficulty of the blockchain.

        Returns:
            Difficulty of the current block.
        """
        return self.scale_difficulty(self.latest_block())
