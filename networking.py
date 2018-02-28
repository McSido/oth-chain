from blockchain import Transaction, Block


def send_msg(msg_type, msg_data):
    pass


def example_worker(broadcast_queue, receive_queue):
    # TODO: check broadcast_queue
    receive_queue.put(('new_transaction', Transaction("a", "b", 10)))
    receive_queue.put(('new_transaction', Transaction("a", "c", 50)))
    receive_queue.put(('mine', ''))


def worker(broadcast_queue, receive_queue):
    """ Takes care of the communication between nodes
    Arguments:
    broadcast_queue -> Queue for messages to other nodes
    receive_queue -> Queue for messages to the attached blockchain
    """
    # Example:
    # Find peers
    # Main loop:
    # - check broadcast_queue (send new messages)
    # - check incoming messages
    #   -- Networking message (e.g. new peer, get peers)
    #   -- Blockchain message: put on receive_queue

    example_worker(broadcast_queue, receive_queue)
