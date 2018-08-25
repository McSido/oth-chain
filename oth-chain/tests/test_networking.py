""" Testing module for the networking module of the blockchain client.
"""

from queue import Queue

import pytest

import utils
from networking import (PEERS, SERVER, Address, ExtendedUDP, pack_msg,
                        process_incoming_msg, send_msg, unpack_msg, worker)

SERVER.setup(6666)

RECEIVER = ExtendedUDP()


def setup():
    """ Setup RECEIVER for tests.
    """
    RECEIVER.setup(6667)
    PEERS.setup(Queue(), Queue(), 6667)


def teardown():
    """ Teardown RECEIVER for tests.
    """
    RECEIVER.teardown()


def test_packing():
    """ Test the packing and unpacking functionality.
    """
    data = [{'a': (1, 2)}, {'b': (3, 4)}]
    packed = pack_msg(data)
    assert data == unpack_msg(packed)


def test_process_incoming(capsys):
    """ Test to determine that messages expected to be given to the blockchain
    are added to the receive_queue.
    """
    with capsys.disabled():
        msg = ('to-blockchain', 'msg-data')
        receive_queue = Queue()
        address = ('0.0.0.0', 1)

        process_incoming_msg(
            pack_msg(msg),
            address,
            receive_queue
        )

        assert receive_queue.get() == (msg[0], msg[1], address)

        n_address = ('123.123.123.123', 1)

        msg = ('N_new_peer', n_address)
        process_incoming_msg(
            pack_msg(msg),
            address,
            receive_queue
        )

        assert n_address in PEERS._peer_list

        msg = ('N_pong', '')
        process_incoming_msg(
            pack_msg(msg),
            n_address,
            receive_queue
        )

        assert n_address in PEERS.get_active_peers()

        msg = ('N_get_peers', '')
        process_incoming_msg(
            pack_msg(msg),
            ('127.0.0.1', 6667),
            receive_queue
        )

        for p in PEERS.get_all_peers():

            received = RECEIVER.receive_msg()

            assert p == unpack_msg(received[0])[1]

        msg = ('N_ping', '')
        process_incoming_msg(
            pack_msg(msg),
            ('127.0.0.1', 6667),
            receive_queue
        )

        received = RECEIVER.receive_msg()

        assert 'N_pong' == unpack_msg(received[0])[0]

    utils.set_debug()

    process_incoming_msg(pack_msg(''),
                         address,
                         receive_queue)

    captured = capsys.readouterr()

    assert captured.out.startswith('### DEBUG ### Received invalid message\n')


def test_unsplit_messaging():
    """ Test if the message sending and receiving work as expected.

    Test for unsplit messages. (msg < BUFFER_SIZE)
    """

    msg = ('test-msg', 'test-data')

    send_msg(msg[0], msg[1], ('127.0.0.1', 6667))

    received = RECEIVER.receive_msg()

    assert unpack_msg(received[0]) == (msg[0], msg[1])


def test_split_messaging_2():
    """ Test if the message sending and receiving work as expected.

    Test for split (2-parts) messages. (msg > BUFFER_SIZE)
    """

    msg = ('test-msg', b'1' * (SERVER.buffersize + 10))

    send_msg(msg[0], msg[1], ('127.0.0.1', 6667))

    received = RECEIVER.receive_msg()

    assert received is None

    received = RECEIVER.receive_msg()

    # Check content
    assert unpack_msg(received[0]) == (msg[0], msg[1])


def test_split_messaging_3():
    """ Test if the message sending and receiving work as expected.

    Test for split (3-parts) messages. (msg >> BUFFER_SIZE)
    """
    msg = ('test-msg', b'1' * (2 * SERVER.buffersize + 10))

    send_msg(msg[0], msg[1], ('127.0.0.1', 6667))

    received = RECEIVER.receive_msg()

    assert received is None

    received = RECEIVER.receive_msg()

    assert received is None

    received = RECEIVER.receive_msg()

    # Check content
    assert unpack_msg(received[0]) == (msg[0], msg[1])


def test_worker():
    """ Test to see if the worker processes incoming tasks as planned.

    Tests additionally if the closing of the worker(-thread) works.
    """
    send_queue = Queue()
    cmd_queue = Queue()
    send_queue.put(None)
    cmd_queue.put('print_peers')
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        worker(send_queue,
               Queue(),
               cmd_queue,
               Queue(),
               6668)
    assert pytest_wrapped_e.type == SystemExit
