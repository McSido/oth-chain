""" Testing module for the networking module of the blockchain client.
"""

from queue import Queue

import networking
from ext_udp import ExtendedUDP

networking.SERVER.setup(6666)

RECEIVER = ExtendedUDP()


def setup():
    """ Setup RECEIVER for tests.
    """
    RECEIVER.setup(6667)
    networking.PEERS.setup(Queue(), Queue(), 6667)


def teardown():
    """ Teardown RECEIVER for tests.
    """
    RECEIVER.teardown()


def test_packing():
    """ Test the packing and unpacking functionality.
    """
    data = [{'a': (1, 2)}, {'b': (3, 4)}]
    packed = networking.pack_msg(data)
    assert data == networking.unpack_msg(packed)


def test_process_incoming():
    """ Test to determine that messages expected to be given to the blockchain
    are added to the receive_queue.
    """
    msg = ('to-blockchain', 'msg-data')
    receive_queue = Queue()
    address = ('0.0.0.0', '1')

    networking.process_incoming_msg(
        networking.pack_msg(msg),
        address,
        receive_queue
    )

    assert receive_queue.get() == (msg[0], msg[1], address)


def test_unsplit_messaging():
    """ Test if the message sending and receiving work as expected.

    Test for unsplit messages. (msg < BUFFER_SIZE)
    """

    msg = ('test-msg', 'test-data')

    networking.send_msg(msg[0], msg[1], ('127.0.0.1', 6667))

    received = RECEIVER.receive_msg()

    assert networking.unpack_msg(received[0]) == (msg[0], msg[1])


def test_split_messaging_2():
    """ Test if the message sending and receiving work as expected.

    Test for split (2-parts) messages. (msg > BUFFER_SIZE)
    """

    msg = ('test-msg', b'1' * (networking.SERVER.buffersize + 10))

    networking.send_msg(msg[0], msg[1], ('127.0.0.1', 6667))

    received = RECEIVER.receive_msg()

    assert received is None

    received = RECEIVER.receive_msg()

    # Check content
    assert networking.unpack_msg(received[0]) == (msg[0], msg[1])


def test_split_messaging_3():
    """ Test if the message sending and receiving work as expected.

    Test for split (3-parts) messages. (msg >> BUFFER_SIZE)
    """
    msg = ('test-msg', b'1' * (2 * networking.SERVER.buffersize + 10))

    networking.send_msg(msg[0], msg[1], ('127.0.0.1', 6667))

    received = RECEIVER.receive_msg()

    assert received is None

    received = RECEIVER.receive_msg()

    assert received is None

    received = RECEIVER.receive_msg()

    # Check content
    assert networking.unpack_msg(received[0]) == (msg[0], msg[1])
