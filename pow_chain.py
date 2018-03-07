import hashlib
import nacl.signing
import nacl.encoding

from nacl.exceptions import BadSignatureError

from blockchain import Block, Blockchain, Transaction


class PoW_Blockchain(Blockchain):
    def __init__(self, send_queue, difficulty):
        self._difficulty = difficulty
        super().__init__(send_queue)

    def new_block(self, block):
        if block.index > self.latest_block().index + 1:
            # block higher then current chain:
            # resolve conflict between chains
            self.send_queue.put(('get_chain', '', 'broadcast'))
            print('### DEBUG ### Chain out-of-date.')
            print('### DEBUG ### Updating...')
            return

        if self.validate_block(block, self.chain[-1]):
            # remove transactions in new block from own transaction pool
            for block_transaction in block.transactions:
                if block_transaction in self.transaction_pool:
                    self.transaction_pool.remove(block_transaction)
            self.send_queue.put(('new_block', block, 'broadcast'))
            self.chain.append(block)
        else:
            print('### DEBUG ### Invalid block')

    def validate_block(self, block, last_block):
        # check if the hash of the new block is valid
        if block.previous_hash != self.hash(last_block):
            return False
        # check if the proof of the new block is valid
        if not self.validate_proof(last_block.proof, block.proof):
            return False
        # validate all transactions
        for transaction in block.transactions:
            if not self.validate_transaction(transaction, mining=True):
                return False
        return True

    def validate_transaction(self, transaction, mining=False):
        if transaction in self.transaction_pool and not mining:
            return False
        # For testing purposes only, should be changed along with the way mining rewards are handled
        if transaction.sender == '0' and transaction.signature == '0':
            return True
        try:
            verify_key = nacl.signing.VerifyKey(transaction.sender, encoder=nacl.encoding.HexEncoder)
            transaction_hash = verify_key.verify(transaction.signature).decode()
            validate_hash = hashlib.sha256(
                (str(transaction.sender) + str(transaction.recipient) + str(transaction.amount) + str(transaction.timestamp)).encode()
            ).hexdigest()

            if validate_hash == transaction_hash:
                print('### DEBUG ### Signature OK')
                if self.check_balance(transaction.sender) >= transaction.amount:
                    print('### DEBUG ### Balance sufficient, transaction is valid')
                    return True
                else:
                    print('### DEBUG ### Balance insufficient, transaction is invalid')
                    return False
            else:
                print('### DEBUG ### Wrong Hash')
                return False

            # TODO: check if enough money

        except BadSignatureError:
            print('### DEBUG ### Bad Signature, Validation Failed')
            return False
        # return transaction not in self.transaction_pool
        # TODO: check if transaction is valid (e.g. signed + enough money)

    def create_proof(self):
        """ Create proof of work:
            Find a number that fullfills validate_proof()
            Can take some time, depending on blockchain difficulty

            Returns the proof
        """
        proof = 0
        while self.validate_proof(self.chain[-1].proof, proof) is False:
            proof += 1
        return proof

    def validate_proof(self, last_proof, proof):
        """ Check if a proof is valid:
            A proof is valid if the hash of the combination of it combined
            with the previous proof has as many leading 0 as set by the
            difficulty

            Returns validity(True/False)
        """
        test_proof = f'{last_proof}{proof}'.encode()
        test_hash = self.hash(test_proof)
        return test_hash[:self._difficulty] == '0' * self._difficulty

    def resolve_conflict(self, new_chain):
        print('### DEBUG ### Resolving conflict')
        if len(self.chain) < len(new_chain):
            # Validate new chain:
            last_block = new_chain[0]
            current_index = 1
            while current_index < len(new_chain):
                block = new_chain[current_index]
                if not self.validate_block(block, last_block):
                    print('### DEBUG ### Conflict resolved (old chain)')
                    return
                last_block = block
                current_index += 1
            self.chain = new_chain
            print('### DEBUG ### Conflict resolved (new chain)')
        else:
            print('### DEBUG ### Conflict resolved (old chain)')

    @property
    def difficulty(self):
        """ Get current difficulty of the blockchain
        """
        return self._difficulty

    @difficulty.setter
    def difficulty(self, difficulty):
        """ Change difficulty of the blockchain
        """
        self._difficulty = difficulty
