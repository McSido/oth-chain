import hashlib
from blockchain import Blockchain, Block, Transaction


class PoW_Blockchain(Blockchain):
    def __init__(self, broadcast_queue, difficulty):
        self._difficulty = difficulty
        super().__init__(broadcast_queue)

    def new_block(self, block):
        if self.validate_block(block, self.chain[-1]):
            self.transaction_pool = []
            # TODO: only remove transaction in new block
            self.broadcast_queue.put(('new_block', block))
            self.chain.append(block)
        else:
            print('Invalid block')

    def validate_block(self, block, last_block):
        if block.previous_hash != self.hash(last_block):
            return False
        if not self.validate_proof(last_block.proof, block.proof):
            return False
        # TODO: validate all transactions
        return True

    def validate_transaction(self, transaction):
        return True
        # TODO: check if transaction is valid (e.g. signed + enough money)

    def create_proof(self):
        proof = 0
        while self.validate_proof(self.chain[-1].proof, proof) is False:
            proof += 1
        return proof

    def validate_proof(self, last_proof, proof):
        test_proof = f'{last_proof}{proof}'.encode()
        test_hash = self.hash(test_proof)
        return test_hash[:self._difficulty] == '0' * self._difficulty

    @property
    def difficulty(self):
        return self._difficulty

    @difficulty.setter
    def difficulty(self, difficulty):
        self._difficulty = difficulty
