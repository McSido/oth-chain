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
        self.chain.process_message(('mine', self.sender_sign, 'local'))

        assert len(self.chain.chain) > 1

    def test_basic_transaction(self):
        pass
