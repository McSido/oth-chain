import hashlib
import time
import time
from queue import Queue

import nacl.encoding
import nacl.signing

import chains
import utils

VERSION = 0.7


class TestDDos(object):
    def setup(self):
        self.counter = 0

        self.sends = Queue()
        self.gui_queue = Queue()

        self.chain = chains.DDosChain(
            VERSION, self.sends, self.gui_queue)

        self.sender_sign = nacl.signing.SigningKey(
            '1973224f51c2e798f6ab3bcf5f8a2a28\
5b1832ea16439bae9c26d9da8256a7ef'.encode('utf-8'),
            nacl.encoding.HexEncoder)

        self.sender_verify = self.sender_sign.verify_key.encode(
            nacl.encoding.HexEncoder)
        self.receiver_sign = nacl.signing.SigningKey(seed=b'bb' * 16)
        self.receiver_verify = self.receiver_sign.verify_key.encode(
            nacl.encoding.HexEncoder)

    def test_ip_blocking(self, capsys):

        ips = ['1.1.1.1',
               '2.2.2.2',
               '3.3.3.3',
               '4.4.4.4',
               '5.5.5.5'
               ]
        for ip in ips:
            self.process_transaction(
                capsys, ip, 'b', self.sender_sign, self.sender_verify)

        self.chain.process_message(('get_ips', '', 'local'))
        captured = capsys.readouterr()
        assert captured.out == f'{ips}\n'

        for _ in range(3):
            ip = ips.pop()
            self.process_transaction(
                capsys, ip, 'ub', self.sender_sign, self.sender_verify)

        for ip in ['6.6.6.6', '7.7.7.7']:
            self.process_transaction(
                capsys, ip, 'b', self.sender_sign, self.sender_verify)
            ips.append(ip)

        self.chain.process_message(('get_ips', '', 'local'))
        captured = capsys.readouterr()
        assert captured.out == f'{ips}\n'

    def test_invites(self, capsys):
        self.process_transaction(
            capsys, self.receiver_verify, 'i',
            self.sender_sign, self.sender_verify)

        def inner(ip):
            self.fill_block(capsys, 4)

            self.process_transaction(
                capsys, ip, 'b',
                self.receiver_sign, self.receiver_verify)

            self.fill_block(capsys, 4)

        inner('1.1.1.1')

        self.chain.process_message(('get_ips', '', 'local'))
        captured = capsys.readouterr()
        assert '1.1.1.1' in captured.out

        self.process_transaction(
            capsys, self.receiver_verify, 'ui',
            self.sender_sign, self.sender_verify)

        inner('2.2.2.2')

        self.chain.process_message(('get_ips', '', 'local'))
        captured = capsys.readouterr()
        assert '2.2.2.2' not in captured.out

    def test_children(self, capsys):
        self.process_transaction(
            capsys, self.receiver_verify, 'i',
            self.sender_sign, self.sender_verify)

        self.fill_block(capsys, 4)

        self.chain.process_message(
            ('show_children', self.sender_verify, 'local'))
        captured = capsys.readouterr()

        assert self.sender_verify.decode('utf-8') in captured.out
        assert self.receiver_verify.decode('utf-8') in captured.out

    def test_purge(self, capsys):

        self.process_transaction(
            capsys, self.receiver_verify, 'i',
            self.sender_sign, self.sender_verify)

        self.fill_block(capsys, 4)

        self.process_transaction(
            capsys, '3.3.3.3', 'b',
            self.receiver_sign, self.receiver_verify)

        self.fill_block(capsys, 4)

        self.chain.process_message(('get_ips', '', 'local'))
        captured = capsys.readouterr()
        assert '3.3.3.3' in captured.out

        self.process_transaction(
            capsys, self.receiver_verify, 'p',
            self.sender_sign, self.sender_verify)

        self.fill_block(capsys, 4)

        self.chain.process_message(('get_ips', '', 'local'))
        captured = capsys.readouterr()
        assert '3.3.3.3' not in captured.out

    def test_ancestors(self, capsys):

        self.process_transaction(
            capsys, self.receiver_verify, 'i',
            self.sender_sign, self.sender_verify)

        self.fill_block(capsys, 4)

        self.process_transaction(
            capsys, '1.2.3.4', 'b',
            self.receiver_sign, self.receiver_verify)

        self.fill_block(capsys, 4)

        self.process_transaction(
            capsys, '1.2.3.4', 'b',
            self.sender_sign, self.sender_verify)

        self.fill_block(capsys, 4)

        self.chain.process_message(('get_ips', '', 'local'))
        captured = capsys.readouterr()
        assert '1.2.3.4' in captured.out

        self.process_transaction(
            capsys, '1.2.3.4', 'ub',
            self.receiver_sign, self.receiver_verify)

        self.fill_block(capsys, 4)

        self.chain.process_message(('get_ips', '', 'local'))
        captured = capsys.readouterr()
        assert '1.2.3.4' in captured.out

        self.process_transaction(
            capsys, '1.2.3.4', 'ub',
            self.sender_sign, self.sender_verify)

        self.fill_block(capsys, 4)

        self.chain.process_message(('get_ips', '', 'local'))
        captured = capsys.readouterr()
        assert '1.2.3.4' not in captured.out

    def test_invalid_transaction(self, capsys):
        utils.set_debug()

        self.process_transaction(
            capsys, self.receiver_verify, 'i',
            self.sender_sign, self.sender_verify)

        time.sleep(0.00000001)  # new timestamp

        self.process_transaction(
            capsys, self.receiver_verify, 'i',
            self.sender_sign, self.sender_verify, False)

        captured = capsys.readouterr()
        assert 'This operation is already in the pool' in captured.out

        self.fill_block(capsys, 4)

        self.process_transaction(
            capsys, self.receiver_verify, 'i',
            self.sender_sign, self.sender_verify, False)

        captured = capsys.readouterr()
        assert 'Client is already invited!' in captured.out

        self.process_transaction(
            capsys, 'Not a client', 'ui',
            self.sender_sign, self.sender_verify, False)

        captured = capsys.readouterr()
        assert 'Client could not be found!' in captured.out

        self.process_transaction(
            capsys, self.sender_verify, 'ui',
            self.receiver_sign, self.receiver_verify, False)

        captured = capsys.readouterr()
        assert 'No permission to delete this node!' in captured.out

        self.process_transaction(
            capsys, '66.77.88.99', 'ub',
            self.receiver_sign, self.receiver_verify, False)

        captured = capsys.readouterr()
        assert 'Trying to unblock IP that was not blocked' in captured.out

        self.process_transaction(
            capsys, '255.255.255.0', 'b',
            self.sender_sign, self.sender_verify, False)

        captured = capsys.readouterr()
        assert 'IP was already blocked' in captured.out

    # ####################### HELPER FUNCTIONS ###########################

    def fill_block(self, capsys, amount):
        for i in range(amount):
            self.process_transaction(
                capsys,
                f'255.255.255.{i+self.counter}',
                'b',
                self.sender_sign,
                self.sender_verify)

        self.counter += amount

    def process_transaction(self,
                            capsys,
                            data,
                            action,
                            s_sign,
                            s_ver,
                            disable_out=True):
        timestamp = time.time()

        transaction = self.create_transaction(s_ver,
                                              timestamp,
                                              chains.DDosData(
                                                  action, data),
                                              s_sign)
        if disable_out:
            with capsys.disabled():
                self.chain.process_message(('new_transaction',
                                            transaction,
                                            'local'
                                            ))
        else:
            self.chain.process_message(('new_transaction',
                                        transaction,
                                        'local'
                                        ))

    def create_transaction(self,
                           sender: str,
                           timestamp: int,
                           data: chains.DDosData,
                           signing_key: nacl.signing.SigningKey) \
            -> chains.DDosTransaction:
        hash_str = (str(sender) +
                    str(data) +
                    str(timestamp))
        transaction_hash = chains.DDosChain.hash(hash_str)

        transaction = chains.DDosTransaction(
            sender,
            timestamp,
            data,
            signing_key.sign(transaction_hash.encode())
        )

        return transaction
