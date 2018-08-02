""" Testing module for the core module of the blockchain client.
"""

import time

import core
import test_pow_chain


class TestCore():
    """ Testcase used to bundle all tests for the
    Core module of the blockchain client.

    """

    def setup(self):
        """ Setup for the tests.
        """
        self.test_obj = test_pow_chain.TestPOW()
        self.test_obj.setup()
        self.chain = self.test_obj.blockchain
        self.processor = self.chain.process_message()
        self.chain.send_queue = core.send_queue
        self.address = ('0.0.0.0', '2323')

    def test_new_block(self):
        """ Test receive message functionality for new_block.
        """

        block = self.chain.create_block(
            self.chain.create_proof(self.test_obj.sender_verify))
        core.receive_msg(
            'new_block',
            block,
            self.address,
            self.chain,
            self.processor
        )
        assert block.header in self.chain.chain
        assert self.chain.chain[block.header] == block.transactions
        assert not core.send_queue.empty()
        send_msg = core.send_queue.get(block=False)
        assert send_msg[0] == 'new_block'
        assert send_msg[1] == self.chain.latest_block()
        assert send_msg[2] == 'broadcast'

    def test_new_transaction(self):
        """ Test receive message functionality for new_transaction.

            ! Not implemented yet !
        """
        pass

    def test_mine(self):
        """ Test receive message functionality for mine.
        """
        core.receive_msg(
            'mine',
            self.test_obj.sender_verify,
            'local',
            self.chain,
            self.processor
        )
        assert not core.send_queue.empty()
        send_msg = core.send_queue.get(block=False)
        assert send_msg[0] == 'new_block'
        assert send_msg[1] == self.chain.latest_block()
        assert send_msg[2] == 'broadcast'
        assert self.chain.check_balance(
            self.test_obj.sender_verify, time.time) > 0

    def test_get_newest_block(self):
        """ Test receive message functionality for get_newest_block.
        """
        core.receive_msg(
            'get_newest_block',
            '',
            self.address,
            self.chain,
            self.processor
        )
        assert not core.send_queue.empty()
        send_msg = core.send_queue.get(block=False)
        assert send_msg[0] == 'new_block'
        assert send_msg[1] == self.chain.latest_block()
        assert send_msg[2] == self.address

    def test_get_chain_resolve_conflict(self):
        """ Test receive message functionality for get_chain.
        and resolve_conflict
        """
        # get_chain
        core.receive_msg(
            'get_chain',
            '',
            self.address,
            self.chain,
            self.processor
        )
        assert not core.send_queue.empty()
        send_msg = core.send_queue.get(block=False)
        assert send_msg[0] == 'resolve_conflict'
        assert send_msg[1] == self.chain.get_block_chain()
        assert send_msg[2] == self.address
        copied_chain = list(send_msg[1])

        # resolve_conflict
        core.receive_msg(
            'resolve_conflict',
            send_msg[1],
            self.address,
            self.chain,
            self.processor
        )
        assert self.chain.get_block_chain() == copied_chain

    def test_print_balance(self, capsys):
        """ Test receive message functionality for print_balance.
        """
        curr_time = time.time
        core.receive_msg(
            'print_balance',
            (self.test_obj.sender_verify, curr_time),
            'local',
            self.chain,
            self.processor
        )

        captured = capsys.readouterr()
        balance = self.chain.check_balance(
            self.test_obj.sender_verify, curr_time)

        assert captured.out.strip() ==\
            f'Current Balance: ' + f'{balance}'.strip()

    def test_commands(self):
        """ Test the command input of the core module.

        Currently unimplemented because commands
        are read in main().
        """
        pass
