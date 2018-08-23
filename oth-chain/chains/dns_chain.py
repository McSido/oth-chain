import hashlib
from queue import Queue

from nacl.exceptions import BadSignatureError

from .pow_chain import PoW_Blockchain
from .blockchain import Block, Transaction, Header
from typing import Any, Dict, Callable, Tuple, List
from networking import Address
from utils import print_debug_info
from pprint import pprint

from collections import namedtuple, OrderedDict

import nacl.encoding
import nacl.signing
import math
import time


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
    """ Implementation of a DNS-'Server' atop of a Proof-of-Work blockchain.
        Users can (given they have enough coins) register new domain -> ip address entries.
        A User can update an entry, provided he is the owner of said entry.
        Users can transfer domain names between one another (with a small fee),
        or give up domain names for auction, at which point every user can bid on this
        domain name, resulting in the domain being transferred to the highest bidder.
    """

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

    def check_auction(self, transaction: DNS_Transaction):
        if transaction.recipient == '0' and transaction.data.type == 't':
            self._auction(transaction)
        if transaction.recipient == '0' and transaction.data.type == 'b':
            self._bid(transaction)

    def validate_transaction(self, transaction: DNS_Transaction, mining: bool = False) -> bool:
        """ Validates a given transaction.
            Overwrites validate_transaction from pow_chain.py.
            Checks if a transaction is
            1.) either a resolved auction or bid, and thus previously validated
            2.) a valid domain operation (register, update, transfer, bid) or
            3.) a valid 'normal' transaction
        """
        normal_transaction = False
        valid_domain_operation = False

        # Resolved auctions, original auction as well as all bids are verified when first posted
        # Therefore we can simply accept these transactions
        if transaction.sender == '0' and transaction.signature == '1':
            return True

        if transaction.data.type == '':
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
                 str(transaction.timestamp) + str(transaction.data)).encode()
            ).hexdigest()

            if validate_hash == transaction_hash:
                print_debug_info('Signature OK')
                return self.validate_balance(transaction)
            print_debug_info('Wrong Hash')
            return False

        except BadSignatureError:
            print_debug_info('Bad Signature, Validation Failed')
            return False

    def process_message(self, message: Tuple[str, Any, Address]):
        """ Create processor for incoming blockchain messages.

                Returns:
                    Processor (function) that processes blockchain messages.
                """

        msg_type, msg_data, msg_address = message
        if msg_type == 'dns_lookup':
            ip = self._resolve_domain_name(msg_data)
            result = f'Domain name {msg_data} could not be found.' if not ip[0] else ip
            print(result)
            if self.gui_ready:
                self.gui_queue.put(('resolved', result, 'local'))
        elif msg_type == 'get_auctions':
            if msg_address == 'gui':
                for key, auction_list in self.auctions.items():
                    for auction in auction_list:
                        self.gui_queue.put(('auction', (auction, str(key)), 'local'))
            else:
                print(self.auctions)

        else:
            super(DNSBlockChain, self).process_message(message)

    def mine(self, msg_data: Any, msg_address: Address):
        """ Mines a new block.
            Args:
                msg_data: key for the sender.
                msg_address: -
        """
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

        self.new_block(self.prepare_new_block(block))

    def _resolve_domain_name(self, name: str) -> Tuple[Any, Any]:
        """ Resolves a given domain name to its' corresponding ip_address as well as its' owner.
            Returns an empty string for the ip if the domain_name is not yet registered,
            or was recently transferred to another owner.
            Args:
                name: The domain_name
        """
        for block_transaction in list(self.chain.values())[::-1]:
            for transaction in block_transaction[::-1]:
                if transaction.data.domain_name == name:
                    if transaction.data.type == 't':
                        return '', transaction.recipient
                    return transaction.data.ip_address, transaction.sender

        return '', ''

    def _is_valid_domain_transaction(self, transaction: DNS_Transaction) -> bool:
        """ Checks if a transaction is valid to perform considering already registered domain names
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

    def _auction(self, transaction: DNS_Transaction, index: int = 0):
        """ Places a transaction with recipient '0' and domain operation type 'transfer'
            into the auctions dict along with an initial 'bid', which returns the service fee
            as well as the domain back to the owner.
            Args:
                transaction: The transaction initiating the auction
        """
        # If no one bids on the transaction, the owner of the domain gets the fee and domain back
        bid_transaction = DNS_Transaction(
            '0', transaction.sender, transaction.fee, 1, time.time(), DNS_Data('', '', ''), '1'
        )
        # auctions are closed after MAX_AUCTION_TIME blocks are mined
        i = self.latest_header().index if index == 0 else index
        try:
            self.auctions[i + MAX_AUCTION_TIME]
        except KeyError:
            self.auctions[i + MAX_AUCTION_TIME] = []
        auction = (transaction, bid_transaction)
        self.auctions[i + MAX_AUCTION_TIME].append((transaction, bid_transaction))
        if self.gui_ready:
            self.gui_queue.put(('auction', (auction, str(i + MAX_AUCTION_TIME)), 'local'))

    def _resolve_auction(self, auction: Tuple[DNS_Transaction, DNS_Transaction]):
        """ Resolves an auction given through a  tuple of transactions by creating
            two transactions 1) the transfer of the domain to the highest bidder and
            2) the payment of the bid to the initiator of the auction.
            These transactions are directly appended to the block currently being mined.
            Args:
                auction: Tuple of transactions [0]: auction, [1]: highest bid
        """
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
        if self.gui_ready:
            self.gui_queue.put(('auction_expired', t1, 'local'))

        return [transfer_transaction, payment_transaction]

    def _bid(self, transaction: DNS_Transaction):
        """ Takes a bid, finds the corresponding auction and replaces the last bid.
            At this point it is already established that the new bid is higher than
            the last. Also reimburses the sender of the last bid, by sending back the
            amount of his bid.
            Args:
                transaction: The bid to be placed
        """
        reimburse_transaction = None
        for auction_list in self.auctions.values():
            for i, auction in enumerate(auction_list):
                if auction[0].data.domain_name == transaction.data.domain_name:
                    reimburse_transaction = auction[1]
                    auction_list[i] = (auction[0], transaction)
                    break
        if self.gui_ready:
            self.gui_queue.put(('new_bid', transaction, 'local'))

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

    def _sync_auctions(self):
        """Synchronizes the auctions dict after conflicts are resolved

        """
        for header, transaction_list in list(self.chain.items())[-MAX_AUCTION_TIME:]:
            print(header.index, transaction_list)
            for transaction in transaction_list:
                if transaction.recipient == '0' and transaction.data.type == 't':
                    self._auction(transaction, index=header.index)
                if transaction.recipient == '0' and transaction.data.type == 'b':
                    self._bid(transaction)
