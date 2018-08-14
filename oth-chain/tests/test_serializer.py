import json
from time import time

import nacl.encoding
import nacl.signing
import nacl.utils

from chains import Block, Header, Transaction
from serializer import deserialize, serialize


def rebuild_obj(obj):
    """ Help function to serialize and deserialize an object

    Args:
        obj: Object to (de)serialize

    Returns:
        New object
    """
    s = serialize(obj)
    d = deserialize(s)
    return d


def test_transaction():
    """ Test serialization and deserialization of a Transaction.
    """
    t = Transaction('send', 'rec', 50, 5, time(), 'Sign')
    assert t == rebuild_obj(t)


def test_header():
    """ Test serialization and deserialization of a Header.
    """
    h = Header(1, 0, time(), 0, 0, 123)
    assert h == rebuild_obj(h)


def test_block():
    """ Test serialization and deserialization of a Block.
    """
    h = Header(1, 0, time(), 0, 0, 123)
    t = Transaction('send', 'rec', 50, 5, time(), 'Sign')
    b = Block(h, [t])
    assert b == rebuild_obj(b)


def test_tuple():
    """ Test serialization and deserialization of a Tuple.
    """
    t = (1, 'ABC', Header(1, 0, time(), 0, 0, 123))
    assert t == rebuild_obj(t)


def test_mix():
    """ Test serialization and deserialization of a mix of collections.
    """
    m = [{'a': (1, 2)}, {'b': (3, 4)}]
    assert m == rebuild_obj(m)


def test_nacl():
    """ Test serialization and deserialization of all used NaCl keys.
    """
    signing_key = nacl.signing.SigningKey.generate()
    verify_key = signing_key.verify_key
    verify_key_hex = verify_key.encode(nacl.encoding.HexEncoder)

    assert signing_key == rebuild_obj(signing_key)
    assert verify_key_hex == rebuild_obj(verify_key_hex)

    text = b'Sign me!'
    signed = signing_key.sign(text)

    assert signed == rebuild_obj(signed)
