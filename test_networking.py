from queue import Queue
import socket

import networking

networking.server_socket.bind(('', 6666))
networking.server_socket.settimeout(0.01)


def test_packing():
    data = [{'a': (1, 2)}, {'b': (3, 4)}]
    packed = networking.pack_msg(data)
    assert data == networking.unpack_msg(packed)


def test_process_incoming():
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

    receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receive_socket.bind(('', 6667))

    msg = ('test-msg', 'test-data')

    networking.send_msg(msg[0], msg[1], ('127.0.0.1', 6667))

    received = receive_socket.recv(networking.BUFFER_SIZE)

    # Check unsplit message
    assert received[0:1] == b'0'
    # Check content
    assert networking.unpack_msg(received[1:]) == (msg[0], msg[1])


def test_split_messaging_2():

    receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receive_socket.bind(('', 6667))

    msg = ('test-msg', b'1' * (networking.BUFFER_SIZE + 10))

    networking.send_msg(msg[0], msg[1], ('127.0.0.1', 6667))

    # Check first part

    received = receive_socket.recv(networking.BUFFER_SIZE)

    assert received[0:1] == b'1'

    received_msg = received[1:]

    # Check second/last part

    received = receive_socket.recv(networking.BUFFER_SIZE)

    assert received[0:1] == b'3'

    received_msg = received_msg + received[1:]

    # Check content
    assert networking.unpack_msg(received_msg) == (msg[0], msg[1])


def test_split_messaging_3():

    receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receive_socket.bind(('', 6667))

    msg = ('test-msg', b'1' * (2 * networking.BUFFER_SIZE + 10))

    networking.send_msg(msg[0], msg[1], ('127.0.0.1', 6667))

    # Check first part

    received = receive_socket.recv(networking.BUFFER_SIZE)

    assert received[0:1] == b'1'

    received_msg = received[1:]

    # Check second part

    received = receive_socket.recv(networking.BUFFER_SIZE)

    assert received[0:1] == b'2'

    received_msg = received_msg + received[1:]

    # Check last part

    received = receive_socket.recv(networking.BUFFER_SIZE)

    assert received[0:1] == b'3'

    received_msg = received_msg + received[1:]

    # Check content
    assert networking.unpack_msg(received_msg) == (msg[0], msg[1])
