from pow_chain import PoW_Blockchain
from blockchain import Block, Transaction


class DNSBlockChain(PoW_Blockchain):

    def process_message(self):
        pass

    def validate_transaction(self, transaction: Transaction, mining: bool = False):
        pass
