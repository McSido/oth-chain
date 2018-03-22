""" Testing module for the core module
    of the blockchain client.
"""

import time
from queue import Queue

import core
import test_pow_chain


def test_receive_msg(capsys):
    """ Test receive message functionality of the core module
    """
    test_obj = test_pow_chain.Test_POW()
    test_obj.setup()
    chain = test_obj.blockchain
    address = ('0.0.0.0', '2323')

    # New block
    block = chain.create_block(chain.create_proof(test_obj.sender_verify))
    core.receive_msg(
        'new_block',
        block,
        address,
        chain
    )
    assert block in chain.chain
    assert not chain.send_queue.empty()
    send_msg = chain.send_queue.get(block=False)
    assert send_msg[0] == 'new_block'
    assert send_msg[1] == chain.chain[-1]
    assert send_msg[2] == 'broadcast'

    # New transaction

    # mine
    core.receive_msg(
        'mine',
        test_obj.sender_verify,
        'local',
        chain
    )
    assert not chain.send_queue.empty()
    send_msg = chain.send_queue.get(block=False)
    assert send_msg[0] == 'new_block'
    assert send_msg[1] == chain.chain[-1]
    assert send_msg[2] == 'broadcast'
    assert chain.check_balance(test_obj.sender_verify, time.time) > 0

    # get_newest_block
    core.receive_msg(
        'get_newest_block',
        '',
        address,
        chain
    )
    assert not core.send_queue.empty()
    send_msg = core.send_queue.get(block=False)
    assert send_msg[0] == 'new_block'
    assert send_msg[1] == chain.chain[-1]
    assert send_msg[2] == address

    # get_chain
    core.receive_msg(
        'get_chain',
        '',
        address,
        chain
    )
    assert not core.send_queue.empty()
    send_msg = core.send_queue.get(block=False)
    assert send_msg[0] == 'resolve_conflict'
    assert send_msg[1] == chain.chain
    assert send_msg[2] == address
    copied_chain = list(send_msg[1])

    # resolve_conflict
    core.receive_msg(
        'resolve_conflict',
        send_msg[1],
        address,
        chain
    )
    assert chain.chain == copied_chain

    # print_balance
    curr_time = time.time
    core.receive_msg(
        'print_balance',
        (test_obj.sender_verify, curr_time),
        'local',
        chain
    )

    captured = capsys.readouterr()
    assert captured.out.strip() ==\
        f'Current Balance: ' + \
        f'{chain.check_balance(test_obj.sender_verify, curr_time)}'.strip()


def test_commands():
    """ Test the command input of the core module 

        Currently unimplemented because commands
        are read in main()
    """
    pass
