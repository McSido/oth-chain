import hashlib
from queue import Queue

from nacl.exceptions import BadSignatureError

from pow_chain import PoW_Blockchain
from blockchain import Block, Transaction, Header
from typing import Any, Dict, Callable, Tuple, List
from networking import Address
from pprint import pprint

from collections import namedtuple, OrderedDict

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

# Number of mined blocks after which the auction is closed
MAX_AUCTION_TIME = 5


class DNSBlockChain(PoW_Blockchain):

    def __init__(self,
                 version: float,
                 send_queue: Queue,
                 gui_queue: Queue) -> None:
        super(DNSBlockChain, self).__init__(version, send_queue, gui_queue)
        self.chain: OrderedDict[Header, List[DNS_Transaction]] = OrderedDict()
        self.new_chain: OrderedDict[Header, List[DNS_Transaction]] = OrderedDict()
        self.transaction_pool: List[DNS_Transaction] = []
        self.load_chain()  # overwrite?
        self.auctions: OrderedDict[int, List[Tuple[DNS_Transaction, DNS_Transaction]]] = OrderedDict()

    def new_transaction(self, transaction: Transaction):
        """ Add a new transaction to the blockchain.
            If the receiver is 0, and the domain operation is 'transfer',
            an auction for that domain is started.

        Args:
            transaction: Transaction that should be added.
        """
        # Make sure, only one mining reward is granted per block
        for pool_transaction in self.transaction_pool:
            if pool_transaction.sender == '0' and \
                    pool_transaction.signature == '0':
                print_debug_info(
                    'This block already granted a mining transaction!')
                return
        if transaction in self.latest_block().transactions:
            return
        if self.validate_transaction(transaction):
            self.transaction_pool.append(transaction)
            self.send_queue.put(('new_transaction', transaction, 'broadcast'))
            if self.gui_ready:
                self.gui_queue.put(('new_transaction', transaction, 'local'))
            if transaction.recipient == '0' and transaction.data.type == 't':
                self._auction(transaction)
            if transaction.recipient == '0' and transaction.data.type == 'b':
                self._bid(transaction)
        else:
            print_debug_info('Invalid transaction')

    def validate_transaction(self, transaction: Transaction, mining: bool = False) -> bool:
        normal_transaction = False
        valid_domain_operation = False

        # Resolved auctions, original auction as well as all bids are verified when first posted
        # Therefore we can simply accept these transactions
        if transaction.sender == '0' and transaction.signature == '1':
            return True

        if transaction.data.type not in 'burt':
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
                if t == transaction:
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
            # Resolve possible auctions:
            try:
                auction_list = self.auctions[block.header.index]
                for auction in auction_list:
                    block.transactions.extend(self._resolve_auction(auction))
                self.auctions.pop(block.header.index)
            except KeyError:
                pass
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
        if transaction.data.type == 'b':
            for auction_list in self.auctions.values():
                for auction in auction_list:
                    if auction[0].data.domain_name == transaction.data.domain_name:
                        if transaction.amount > auction[1].amount:
                            return True
                        if transaction == auction[1]:
                            return True
                        return False
            return False
        ip, owner = self._resolve_domain_name(transaction.data.domain_name)
        if transaction.data.type == 'r' and ip:
            return False
        elif transaction.data.type in 'ut':
            if not ip or owner != transaction.sender:
                return False
        return True

    def _auction(self, transaction: DNS_Transaction):
        # If no one bids on the transaction, the owner of the domain gets the fee and domain back
        bid_transaction = DNS_Transaction(
            '0', transaction.sender, transaction.fee, 1, time.time(), DNS_Data('', '', ''), '1'
        )
        # auctions are closed after MAX_AUCTION_TIME blocks are mined
        try:
            self.auctions[self.latest_header().index + MAX_AUCTION_TIME]
        except KeyError:
            self.auctions[self.latest_header().index + MAX_AUCTION_TIME] = []
        self.auctions[self.latest_header().index + MAX_AUCTION_TIME].append((transaction, bid_transaction))

    def _resolve_auction(self, auction: Tuple[DNS_Transaction, DNS_Transaction]):
        t1 = auction[0]  # original auction
        t2 = auction[1]  # highest bid
        domain = t1.data.domain_name
        t_sender = '0'
        t_recipient = t2.sender if t2.sender != '0' else t1.sender
        t_amount = 0
        t_fee = 1
        t_timestamp = time.time()
        t_data = DNS_Data('t', domain, '')
        transfer_transaction = DNS_Transaction(t_sender, t_recipient, t_amount, t_fee, t_timestamp, t_data, '1')

        p_sender = '0'
        p_recipient = t1.sender
        p_amount = t2.amount
        p_fee = 1
        p_timestamp = time.time()
        p_data = DNS_Data('', '', '')
        payment_transaction = DNS_Transaction(p_sender, p_recipient, p_amount, p_fee, p_timestamp, p_data, '1')

        return [transfer_transaction, payment_transaction]

    def _bid(self, transaction: DNS_Transaction):
        reimburse_transaction = None
        for auction_list in self.auctions.values():
            for i, auction in enumerate(auction_list):
                if auction[0].data.domain_name == transaction.data.domain_name:
                    reimburse_transaction = auction[1]
                    auction_list[i] = (auction[0], transaction)

        if not reimburse_transaction.sender == '0':
            t = DNS_Transaction(
                '0',
                reimburse_transaction.sender,
                reimburse_transaction.amount,
                1,
                time.time(),
                DNS_Data('', '', ''),
                '1'
            )
            self.new_transaction(t)
