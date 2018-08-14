import json
from time import time

import nacl.encoding
import nacl.signing
import nacl.utils

from chains import Block, Header, Transaction
from serializer import deserialize, serialize


def rebuild_obj(obj):
    s = serialize(obj)
    d = deserialize(s)
    return d


def test_transaction():
    t = Transaction('send', 'rec', 50, 5, time(), 'Sign')
    assert t == rebuild_obj(t)


def test_header():
    h = Header(1, 0, time(), 0, 0, 123)
    assert h == rebuild_obj(h)


def test_block():
    h = Header(1, 0, time(), 0, 0, 123)
    t = Transaction('send', 'rec', 50, 5, time(), 'Sign')
    b = Block(h, [t])
    assert b == rebuild_obj(b)


def test_tuple():
    t = (1, 'ABC', Header(1, 0, time(), 0, 0, 123))
    assert t == rebuild_obj(t)


def test_mix():
    m = [{'a': (1, 2)}, {'b': (3, 4)}]
    assert m == rebuild_obj(m)


def test__nacl():
    signing_key = nacl.signing.SigningKey.generate()
    verify_key = signing_key.verify_key
    verify_key_hex = verify_key.encode(nacl.encoding.HexEncoder)

    assert signing_key == rebuild_obj(signing_key)
    assert verify_key_hex == rebuild_obj(verify_key_hex)

    text = b'Sign me!'
    signed = signing_key.sign(text)

    assert signed == rebuild_obj(signed)
