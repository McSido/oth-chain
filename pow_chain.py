import hashlib
import nacl.signing
import nacl.encoding
import math

from nacl.exceptions import BadSignatureError

from blockchain import Block, Blockchain, Transaction
from utils import print_debug_info


class PoW_Blockchain(Blockchain):
    def __init__(self, send_queue, difficulty):
        self._difficulty = difficulty
        super().__init__(send_queue)

    def new_block(self, block):
        if block.index > self.latest_block().index + 1:
            # block higher then current chain:
            # resolve conflict between chains
            self.send_queue.put(('get_chain', '', 'broadcast'))
            print_debug_info('### DEBUG ### Chain out-of-date.')
            print_debug_info('### DEBUG ### Updating...')
            return

        if self.validate_block(block, self.chain[-1]):
            # remove transactions in new block from own transaction pool
            for block_transaction in block.transactions:
                if block_transaction in self.transaction_pool:
                    self.transaction_pool.remove(block_transaction)
            self.send_queue.put(('new_block', block, 'broadcast'))
            self.chain.append(block)
        else:
            print_debug_info('### DEBUG ### Invalid block')

    def validate_block(self, block, last_block):
        # check if the hash of the new block is valid
        if block.previous_hash != self.hash(last_block):
            return False
        # check if the proof of the new block is valid
        mining_transaction = None
        for transaction in block.transactions:
            if transaction.sender == '0' and transaction.signature == '0':
                mining_transaction = transaction
                break
        if not self.validate_proof(last_block, block.proof, mining_transaction.recipient):
            return False
        # validate all transactions
        for transaction in block.transactions:
            if not self.validate_transaction(transaction, mining=True):
                return False
        return True

    def validate_transaction(self, transaction, mining=False):
        if not transaction.amount > 0:
            print_debug_info(f'### DEBUG ### Received transaction with amount {transaction.amount} lower or equal to zero')
            return False
        if transaction in self.transaction_pool and not mining:
            return False
        if transaction.sender == '0' and transaction.signature == '0':
            return True
        try:
            verify_key = nacl.signing.VerifyKey(transaction.sender, encoder=nacl.encoding.HexEncoder)
            transaction_hash = verify_key.verify(transaction.signature).decode()
            validate_hash = hashlib.sha256(
                (str(transaction.sender) + str(transaction.recipient) + str(transaction.amount) + str(transaction.fee)
                 + str(transaction.timestamp)).encode()
            ).hexdigest()

            if validate_hash == transaction_hash:
                print_debug_info('### DEBUG ### Signature OK')
                balance = self.check_balance(transaction.sender, transaction.timestamp)
                if balance >= transaction.amount + transaction.fee:
                    print_debug_info('### DEBUG ### Balance sufficient, transaction is valid')
                    return True
                else:
                    print_debug_info('### DEBUG ### Balance insufficient, transaction is invalid')
                    print_debug_info(f'Transaction at fault: {transaction} was not covered by balance: {balance}')
                    return False
            else:
                print_debug_info('### DEBUG ### Wrong Hash')
                return False

        except BadSignatureError:
            print_debug_info('### DEBUG ### Bad Signature, Validation Failed')
            return False

    def create_proof(self, miner_key):
        """ Create proof of work:
            Find a number that fullfills validate_proof()
            Can take some time, depending on blockchain difficulty

            Returns the proof
        """
        proof = 0
        last_block = self.chain[-1]
        while self.validate_proof(last_block, proof, miner_key) is False:
            proof += 1
        return proof

    def validate_proof(self, last_block, proof, miner_key):
        """ Check if a proof is valid:
            A proof is valid if the hash of the combination of it combined
            with the previous proof has as many leading 0 as set by the
            difficulty

            Returns validity(True/False)
        """
        difficulty = self.scale_difficulty(last_block)
        test_proof = f'{last_block.proof}{proof}{miner_key}'.encode()
        test_hash = self.hash(test_proof)
        return test_hash[:difficulty] == '0' * difficulty

    def resolve_conflict(self, new_chain):
        print_debug_info('### DEBUG ### Resolving conflict')
        if len(self.chain) < len(new_chain):
            # Validate new chain:
            # store old chain, and set self.chain to new_chain (needed for check_balance)
            old_chain = list(self.chain)
            self.chain = new_chain
            last_block = new_chain[0]
            current_index = 1
            while current_index < len(new_chain):
                block = new_chain[current_index]
                if not self.validate_block(block, last_block):
                    print_debug_info('### DEBUG ### Conflict resolved (old chain)')
                    self.chain = old_chain
                    return
                last_block = block
                current_index += 1
            # self.chain = new_chain
            print_debug_info('### DEBUG ### Conflict resolved (new chain)')
        else:
            print_debug_info('### DEBUG ### Conflict resolved (old chain)')

    def scale_difficulty(self, last_block):
        """ Example implementation of a scaling difficulty curve
            Difficulty rises fast in the beginning and slower towards later blocks
            reaching a difficulty of 4 at ~3k blocks and holding it until ~23k blocks
            Arguments:
                last_block -> difficulty is scaled upon the index of the last block
        """
        try:
            difficulty = max(math.floor(math.log(last_block.index)/2), 1)
        except ValueError:
            difficulty = 1
        return difficulty

    @property
    def difficulty(self):
        """ Get current difficulty of the blockchain
        """
        return self.scale_difficulty(self.chain[-1])

    @difficulty.setter
    def difficulty(self, difficulty):
        """ Change difficulty of the blockchain
        """
        self._difficulty = difficulty
