""" Testing module for the DDoS implementation
of the blockchain client.
"""

import hashlib
import time
from queue import Queue

import nacl.encoding
import nacl.signing

import chains
import utils

VERSION = 0.7


class TestDDos(object):
    """ Testcase used to bundle all tests for the
    DDoS blockchain
    """

    def setup(self):
        """ Setup of the blockchain for the tests.
        """
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
        """ Test that blocking and unblocking of IPs works.
        """
        # Initial IPs

        ips = ['1.1.1.1',
               '2.2.2.2',
               '3.3.3.3',
               '4.4.4.4',
               '5.5.5.5'
               ]

        # Block IPs

        for ip in ips:
            self.process_transaction(
                capsys, ip, 'b', self.sender_sign, self.sender_verify)

        self.chain.process_message(('get_ips', '', 'local'))
        captured = capsys.readouterr()
        assert captured.out == f'{ips}\n'

        # Unblock the last 3 IPs

        for _ in range(3):
            ip = ips.pop()
            self.process_transaction(
                capsys, ip, 'ub', self.sender_sign, self.sender_verify)

        # Add 2 new IPs

        for ip in ['6.6.6.6', '7.7.7.7']:
            self.process_transaction(
                capsys, ip, 'b', self.sender_sign, self.sender_verify)
            ips.append(ip)

        self.chain.process_message(('get_ips', '', 'local'))
        captured = capsys.readouterr()
        assert captured.out == f'{ips}\n'

    def test_invites(self, capsys):
        """ Test that invites and uninvites of users works.
        """

        # Invite

        self.process_transaction(
            capsys, self.receiver_verify, 'i',
            self.sender_sign, self.sender_verify)

        def inner(ip):
            """ Block IP

            Args:
                ip: IP that should be blocked
            """
            self.fill_block(capsys, 4)

            self.process_transaction(
                capsys, ip, 'b',
                self.receiver_sign, self.receiver_verify)

            self.fill_block(capsys, 4)

        # Verify that new user can block IPs

        inner('1.1.1.1')

        self.chain.process_message(('get_ips', '', 'local'))
        captured = capsys.readouterr()
        assert '1.1.1.1' in captured.out

        # Uninvite user

        self.process_transaction(
            capsys, self.receiver_verify, 'ui',
            self.sender_sign, self.sender_verify)

        # Verify that uninvited user can no longer block IPs

        inner('2.2.2.2')

        self.chain.process_message(('get_ips', '', 'local'))
        captured = capsys.readouterr()
        assert '2.2.2.2' not in captured.out

    def test_children(self, capsys):
        """ Test the user hierarchy
        """
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
        """ Test the purging of a user-account
        """

        # Invite

        self.process_transaction(
            capsys, self.receiver_verify, 'i',
            self.sender_sign, self.sender_verify)

        self.fill_block(capsys, 4)

        # Verify that new user can block IPs

        self.process_transaction(
            capsys, '3.3.3.3', 'b',
            self.receiver_sign, self.receiver_verify)

        self.fill_block(capsys, 4)

        self.chain.process_message(('get_ips', '', 'local'))
        captured = capsys.readouterr()
        assert '3.3.3.3' in captured.out

        # Purge new user

        self.process_transaction(
            capsys, self.receiver_verify, 'p',
            self.sender_sign, self.sender_verify)

        self.fill_block(capsys, 4)

        # Verify that IPs are now unblocked

        self.chain.process_message(('get_ips', '', 'local'))
        captured = capsys.readouterr()
        assert '3.3.3.3' not in captured.out

    def test_ancestors(self, capsys):
        """ Test blocking/unblocking of IPs through ancestors
        """

        # Invite

        self.process_transaction(
            capsys, self.receiver_verify, 'i',
            self.sender_sign, self.sender_verify)

        self.fill_block(capsys, 4)

        # New user blocks IP

        self.process_transaction(
            capsys, '1.2.3.4', 'b',
            self.receiver_sign, self.receiver_verify)

        self.fill_block(capsys, 4)

        # Ancestor(initial user) takes over block

        self.process_transaction(
            capsys, '1.2.3.4', 'b',
            self.sender_sign, self.sender_verify)

        self.fill_block(capsys, 4)

        # Verify IP is blocked

        self.chain.process_message(('get_ips', '', 'local'))
        captured = capsys.readouterr()
        assert '1.2.3.4' in captured.out

        # Try unblocking with new user

        self.process_transaction(
            capsys, '1.2.3.4', 'ub',
            self.receiver_sign, self.receiver_verify)

        self.fill_block(capsys, 4)

        # Verify that new user cannot unblock the IP of ancestor

        self.chain.process_message(('get_ips', '', 'local'))
        captured = capsys.readouterr()
        assert '1.2.3.4' in captured.out

        # Unblock IP from ancestor (initial user)

        self.process_transaction(
            capsys, '1.2.3.4', 'ub',
            self.sender_sign, self.sender_verify)

        self.fill_block(capsys, 4)

        # Verify that IP is now unblocked

        self.chain.process_message(('get_ips', '', 'local'))
        captured = capsys.readouterr()
        assert '1.2.3.4' not in captured.out

    def test_invalid_transaction(self, capsys):
        """ Test that the chain rejects invalid transaction
        """
        utils.set_debug()

        # Verify rejection of duplicate transaction

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

        # Verify rejection of invite for members of the blockchain

        self.process_transaction(
            capsys, self.receiver_verify, 'i',
            self.sender_sign, self.sender_verify, False)

        captured = capsys.readouterr()
        assert 'Client is already invited!' in captured.out

        # Verify rejection for uninvite of someone that is not a member

        self.process_transaction(
            capsys, 'Not a client', 'ui',
            self.sender_sign, self.sender_verify, False)

        captured = capsys.readouterr()
        assert 'Client could not be found!' in captured.out

        # Verify rejection of not-permissioned uninvites

        self.process_transaction(
            capsys, self.sender_verify, 'ui',
            self.receiver_sign, self.receiver_verify, False)

        captured = capsys.readouterr()
        assert 'No permission to delete this node!' in captured.out

        # Verify rejection of unblocking of not-blocked IPs

        self.process_transaction(
            capsys, '66.77.88.99', 'ub',
            self.receiver_sign, self.receiver_verify, False)

        captured = capsys.readouterr()
        assert 'Trying to unblock IP that was not blocked' in captured.out

        # Verify rejection of blocking of already blocked IPs

        self.process_transaction(
            capsys, '255.255.255.0', 'b',
            self.sender_sign, self.sender_verify, False)

        captured = capsys.readouterr()
        assert 'IP was already blocked' in captured.out

    # ####################### HELPER FUNCTIONS ###########################

    def fill_block(self, capsys, amount):
        """ Fill block with additional transactions

        This is needed because the DDoS-chain creates
        a new block every 5 transactions.

        The transactions are blocking-transactions of IPs with this format:
        255.255.255.X
        with X increasing over time and is never the same.
        Uses self.counter for this.

        This works only for up to 255 transactions,
        if more are needed change the function.

        Args:
            amount: Number of transactions missing to 5
        """
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
        """ Create + Process a transaction.

        Args:
            capsys: capsys of caller.
            data: DDos data (e.g. IP, key)
            action: DDos action (e.g. 'b', 'ui')
            s_sign: Signing key of sender
            s_ver: Verify key of sender
            disabled_out: Disable output (default: True)
        """

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
        """ Create a transaction.

        Args:
            sender: Verify key of sender.
            timestamp: Timestamp of transaction.
            data: DDoS data (action, data)
            signing_key: Signing key of sender

        Returns:
            Created transaction
        """
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
