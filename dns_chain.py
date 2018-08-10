import hashlib

from nacl.exceptions import BadSignatureError

from pow_chain import PoW_Blockchain
from blockchain import Block, Transaction, Header
from typing import Any, Dict, Callable, Tuple
from networking import Address
from pprint import pprint

from collections import namedtuple

import nacl.encoding
import nacl.signing
import math
import time

from utils import print_debug_info

DNS_Transaction = namedtuple('DNS_Transaction',
                             ['sender',
                              'recipient',
                              'amount',
                              'fee',
                              'timestamp',
                              'data',
                              'signature'])

DNS_Data = namedtuple('DNS_Data',
                      ['type',
                       'domain_name',
                       'ip_address'])


class DNSBlockChain(PoW_Blockchain):

    def validate_transaction(self, transaction: Transaction, mining: bool = False) -> bool:
        normal_transaction = False
        valid_domain_operation = False

        if transaction.data.type not in 'urt':
            normal_transaction = True
            if transaction.amount == 0:
                return False
        if not normal_transaction:
            valid_domain_operation = self._is_valid_domain_transaction(transaction)
            if not valid_domain_operation:
                return False

        if not mining:
            found = False
            for t in self.transaction_pool:
                if t == self.transaction_pool:
                    return False
                if normal_transaction:
                    continue
                if t.data.domain_name == transaction.data.domain_name:
                    found = True
                    if transaction.data.type == 'r':
                        return False
                    if transaction.data.type == 'u' and t.sender != transaction.sender:
                        return False
            if not found and transaction.data.type == 'u' and not valid_domain_operation:
                return False

        try:
            verify_key = nacl.signing.VerifyKey(
                transaction.sender, encoder=nacl.encoding.HexEncoder)
            transaction_hash = verify_key.verify(
                transaction.signature).decode()
            validate_hash = hashlib.sha256(
                (str(transaction.sender) + str(transaction.recipient) +
                 str(transaction.amount) + str(transaction.fee) +
                 str(transaction.data) + str(transaction.timestamp)).encode()
            ).hexdigest()

            if validate_hash == transaction_hash:
                print_debug_info('Signature OK')
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
            print_debug_info('Wrong Hash')
            return False

        except BadSignatureError:
            print_debug_info('Bad Signature, Validation Failed')
            return False

    def process_message(self) -> Callable[[str, Any, Address], Any]:
        """ Create processor for incoming blockchain messages.

                Returns:
                    Processor (function) that processes blockchain messages.
                """

        def new_block_inner(msg_data: Any, _: Address):
            assert isinstance(msg_data, Block)
            self.new_block(msg_data)

        def new_transaction_inner(msg_data: Any, _: Address):
            assert isinstance(msg_data, DNS_Transaction)
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
            mining_reward = 50 >> 2 ** reward_multiplier \
                if reward_multiplier >= 0 else 50
            block.transactions.append(
                DNS_Transaction(sender='0', recipient=msg_data,
                                amount=mining_reward + fee_sum, fee=0,
                                data=DNS_Data('', '', ''),
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
                self.gui_queue.put(('dump', (self.chain, self.transaction_pool), 'local'))
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

        def dns_lookup(msg_data: Any, msg_address: Address):
            if msg_address != 'local':
                return
            ip = self._resolve_domain_name(msg_data)[0]
            if ip:
                print(ip)
            else:
                print(f'Domain name {msg_data} could not be found.')

        commands: Dict[str, Callable[[Any, Address], Any]] = {
            'new_block': new_block_inner,
            'new_transaction': new_transaction_inner,
            'mine': mine,
            'resolve_conflict': resolve_conflict_inner,
            'print_balance': print_balance,
            'save': save_chain,
            'dump': dump_vars,
            'get_block': get_block_inner,
            'new_header': new_header_inner,
            'dns_lookup': dns_lookup,
        }

        def processor(msg_type: str, msg_data: Any,
                      msg_address: Address) -> Any:
            commands[msg_type](msg_data, msg_address)

        return processor

    def _resolve_domain_name(self, name: str) -> Tuple[Any, Any]:
        for block_transaction in list(self.chain.values())[::-1]:
            for transaction in block_transaction[::-1]:
                if transaction.data.domain_name == name:
                    if transaction.data.type == 't':
                        return '', transaction.recipient
                    return transaction.data.ip_address, transaction.sender

        return '', ''

    def _is_valid_domain_transaction(self, transaction: DNS_Transaction) -> bool:
        """
        Checks if a transaction is valid to perform considering already registered domain names
        Args:
            transaction: The transaction to be validated
        """
        ip, owner = self._resolve_domain_name(transaction.data.domain_name)
        if transaction.data.type == 'r' and ip:
            return False
        elif transaction.data.type in 'ut':
            if not ip or owner != transaction.sender:
                return False
        return True
