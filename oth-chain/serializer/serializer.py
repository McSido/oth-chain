import json
from collections import OrderedDict, namedtuple
from pprint import pprint
from typing import Any, NamedTuple

import nacl.encoding
import nacl.signing

import chains


def create_dict_named(obj: namedtuple):
    data = {'__type__': type(obj).__name__,
            '__data__': create_dict(obj._asdict())
            }
    return data


def create_block_dict(h_dict, transactions):
    data = {
        '__type__': 'Block',
        '__header__': h_dict,
        '__transactions__': transactions}
    return data


def create_dict(obj: Any):
    if isinstance(obj, chains.Block):
        h_dict = create_dict(obj.header)
        transactions = create_dict(obj.transactions)
        data = create_block_dict(h_dict, transactions)

    elif isinstance(obj, (chains.Transaction,
                          chains.Header,
                          chains.DNS_Transaction,
                          chains.DNS_Data)):
        data = create_dict_named(obj)

    elif isinstance(obj, tuple):
        data = dict(
            (f'__{i}__', create_dict(d)) for (i, d) in enumerate(obj)
        )
        data['__type__'] = 'Tuple'

    elif isinstance(obj, list):
        data = dict(
            (f'__{i}__', create_dict(d)) for (i, d) in enumerate(obj)
        )
        data['__type__'] = 'List'

    elif isinstance(obj, (dict, OrderedDict)):
        data = dict(
            (k, create_dict(v)) for (k, v) in obj.items()
        )
        data['__type__'] = 'Dict'

    elif isinstance(obj, bytes):
        try:
            data = {
                '__type__': 'Bytes',
                '__encoding__': 'utf-8',
                '__data__': obj.decode('utf-8')
            }
        except UnicodeDecodeError:
            data = {
                '__type__': 'Hex-Bytes',
                '__encoding__': 'utf-8',
                '__data__': nacl.encoding.HexEncoder.
                encode(obj).decode('utf-8')
            }

    elif isinstance(obj, nacl.signing.SigningKey):
        data = {
            '__type__': 'SigningKey',
            '__encoding__': 'utf-8',
            '__seed__': obj.encode(nacl.encoding.HexEncoder).decode('utf-8')
        }

    else:
        data = {
            '__type__': type(obj).__name__,
            '__data__': obj
        }
    return data


def serialize(obj: Any):
    data = create_dict(obj)
    return json.dumps(data)


def create_object(data: dict):
    if isinstance(data, list):
        return [create_object(e) for e in data]

    if data['__type__'] == 'Transaction':
        return chains.Transaction(**create_object(data['__data__']))

    if data['__type__'] == 'Header':
        return chains.Header(**create_object(data['__data__']))

    if data['__type__'] == 'Block':
        return chains.Block(create_object(data['__header__']),
                            create_object(data['__transactions__']))

    if data['__type__'] == 'Tuple':
        return tuple(
            create_object(data[f'__{i}__']) for i in range(len(data)-1)
        )

    if data['__type__'] == 'List':
        return [create_object(data[f'__{i}__']) for i in range(len(data)-1)]

    if data['__type__'] == 'Dict':
        return dict(
            (k, create_object(v)) for (k, v) in data.items() if k != '__type__'
        )

    if data['__type__'] == 'Bytes':
        return data['__data__'].encode(data['__encoding__'])

    if data['__type__'] == 'Hex-Bytes':
        return nacl.encoding.HexEncoder.decode(
            data['__data__'].encode(data['__encoding__']))

    if data['__type__'] == 'SigningKey':
        return nacl.signing.SigningKey(
            data['__seed__'].encode(data['__encoding__']),
            nacl.encoding.HexEncoder)

    return data['__data__']


def deserialize(str_data: str):
    """ Deserializes the different objects of the blockchain

    Args:
        data: JSON representation of data

    Returns:
        blockchain object
    """
    data = json.loads(str_data)
    return create_object(data)
