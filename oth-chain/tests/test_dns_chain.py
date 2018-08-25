import hashlib
import time
from queue import Queue

import nacl.encoding
import nacl.signing

import chains

VERSION = 0.7


class TestDDos(object):
    def setup(self):

        self.sends = Queue()
        self.gui_queue = Queue()

        self.chain = chains.DNSBlockChain(
            VERSION, self.sends, self.gui_queue)

        self.sender_sign = nacl.signing.SigningKey(seed=b'aa' * 16)
        self.sender_verify = self.sender_sign.verify_key.encode(
            nacl.encoding.HexEncoder)
        self.receiver_sign = nacl.signing.SigningKey(seed=b'bb' * 16)
        self.receiver_verify = self.receiver_sign.verify_key.encode(
            nacl.encoding.HexEncoder)

    def test_mine(self):
        self.chain.process_message(('mine', self.sender_verify, 'local'))

        assert len(self.chain.chain) > 1

    def test_basic_transaction(self):
        self.chain.process_message(('mine', self.sender_verify, 'local'))

        t = self.create_transaction(chains.DNS_Data('', '', ''), 1, 1)
        self.chain.new_transaction(t)

        assert t in self.chain.transaction_pool

        t2 = self.create_transaction(chains.DNS_Data('', '', ''), 1, 1)
        self.chain.new_transaction(t2)

        assert t2 in self.chain.transaction_pool

    def test_register(self, capsys):
        with capsys.disabled():
            self.basic_creation()

        self.chain.process_message(('dns_lookup', 'seclab.oth', 'local'))

        captured = capsys.readouterr()
        assert captured.out == '127.0.0.1\n'

    def test_update(self, capsys):
        with capsys.disabled():
            self.basic_creation()

            t = self.create_transaction(chains.DNS_Data('u',
                                                        'seclab.oth',
                                                        '127.0.0.2'),
                                        0,
                                        20
                                        )
            self.chain.new_transaction(t)
            self.chain.process_message(('mine', self.sender_verify, 'local'))

        self.chain.process_message(('dns_lookup', 'seclab.oth', 'local'))

        captured = capsys.readouterr()
        assert captured.out == '127.0.0.2\n'

    def test_transfer(self, capsys):
        with capsys.disabled():
            self.basic_creation()

            t = self.create_transaction(chains.DNS_Data('t',
                                                        'seclab.oth',
                                                        ''),
                                        0,
                                        1
                                        )

            self.chain.new_transaction(t)
            self.chain.process_message(('mine', self.sender_verify, 'local'))

            t = self.create_transaction(chains.DNS_Data('u',
                                                        'seclab.oth',
                                                        '127.0.0.2'),
                                        0,
                                        20
                                        )

            assert not self.chain.validate_transaction(t)

            self.sender_verify = self.receiver_verify
            self.sender_sign = self.receiver_sign

            self.chain.process_message(('mine', self.sender_verify, 'local'))

            t = self.create_transaction(chains.DNS_Data('u',
                                                        'seclab.oth',
                                                        '127.0.0.3'),
                                        0,
                                        20,
                                        )

            assert self.chain.validate_transaction(t)

    def test_auction(self, capsys):
        with capsys.disabled():
            self.basic_creation()

            t = self.create_transaction(chains.DNS_Data('t',
                                                        'seclab.oth',
                                                        ''),
                                        0,
                                        5,
                                        '0'
                                        )

            self.chain.new_transaction(t)
            self.chain.process_message(('mine', self.sender_verify, 'local'))

            self.sender_verify = self.receiver_verify
            self.sender_sign = self.receiver_sign

            t = self.create_transaction(chains.DNS_Data('b',
                                                        'seclab.oth',
                                                        ''),
                                        5,
                                        1,
                                        '0'
                                        )

            self.chain.new_transaction(t)
            self.chain.process_message(('mine', self.sender_verify,
                                        'local'))

            t = self.create_transaction(chains.DNS_Data('b',
                                                        'seclab.oth',
                                                        ''),
                                        9,
                                        1,
                                        '0'
                                        )

            self.chain.new_transaction(t)

            for _ in range(5):
                self.chain.process_message(('mine', self.sender_verify,
                                            'local'))

            t = self.create_transaction(chains.DNS_Data('u',
                                                        'seclab.oth',
                                                        '127.0.0.3'),
                                        0,
                                        20,
                                        )

            assert self.chain.validate_transaction(t)

    def test_resolve_conflict(self):
        self.basic_creation()

        bchain2 = chains.DNSBlockChain(VERSION,
                                       Queue(),
                                       Queue()
                                       )

        bchain2.process_message(('mine', self.sender_verify, 'local'))

        t = self.create_transaction(chains.DNS_Data('r',
                                                    'seclab.oth',
                                                    '127.0.0.1'),
                                    0,
                                    20
                                    )

        bchain2.new_transaction(t)

        for _ in range(5):
            bchain2.process_message(('mine', self.sender_verify, 'local'))

        t = self.create_transaction(chains.DNS_Data('t',
                                                    'seclab.oth',
                                                    ''),
                                    0,
                                    5,
                                    '0'
                                    )

        bchain2.new_transaction(t)

        bchain2.process_message(('mine', self.sender_verify, 'local'))

        self.chain.resolve_conflict(bchain2.get_header_chain())

        assert bchain2.latest_header() == self.chain.nc_latest_header()

        for _ in range(3):
            bchain2.process_message(('mine', self.sender_verify, 'local'))

        self.chain.resolve_conflict(bchain2.get_header_chain())
        assert bchain2.latest_header() == self.chain.nc_latest_header()

        # Chain exchange

        for b in bchain2.get_block_chain():
            self.chain.new_block(b)

        assert bchain2.latest_block() == self.chain.latest_block()

    # ####################### HELPER FUNCTIONS ###########################

    def basic_creation(self):

        self.chain.process_message(('mine', self.sender_verify, 'local'))

        t = self.create_transaction(chains.DNS_Data('r',
                                                    'seclab.oth',
                                                    '127.0.0.1'),
                                    0,
                                    20
                                    )
        self.chain.new_transaction(t)

        self.chain.process_message(('mine', self.sender_verify, 'local'))

    def create_transaction(self,
                           dns_data,
                           amount,
                           fee,
                           receiver_verify=None):
        if not receiver_verify:
            receiver_verify = self.receiver_verify

        timestamp = time.time()

        hash_str = (str(self.sender_verify) + str(receiver_verify) +
                    str(amount) + str(fee) + str(timestamp))

        transaction_hash = hashlib.sha256(
            (hash_str + str(dns_data)).encode()).hexdigest()
        transaction = chains.DNS_Transaction(self.sender_verify,
                                             receiver_verify,
                                             amount,
                                             fee,
                                             timestamp,
                                             dns_data,
                                             self.sender_sign.sign(
                                                 transaction_hash.encode())
                                             )
        return transaction
