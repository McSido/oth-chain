""" Extended UDP module for the blockchain client
    Allows for sending and receiving of messages
    that are bigger than the buffersize

    Does not handle out-of-order messages
"""

import socket


class ExtendedUDP():
    """ Implementation of an extended UDP socket
        Can send/receive messages that are bigger
        than the buffersize

        Does not handle out-of-order messages

        Call setup() before use and
        teardown() after use

        Arguments:
            buffersize -> Buffersize of the socket (default=1024)
    """

    def __init__(self, buffersize=1024):
        self.buffersize = buffersize
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.received_data = {}
        self.port = 6666

    def setup(self, port):
        """ Setup socket

            Arguments:
                port -> Port of the socket
        """
        if isinstance(self.socket, socket.socket):
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('', port))
        self.socket.settimeout(0.1)
        self.port = port
        self.received_data.clear()

    def send_msg(self, msg, address):
        """ Send message to the address

            Arguments:
                msg -> Message to send (byte-array)
                address -> Address to send the message to
        """
        if len(msg) < self.buffersize:
            # Simple message
            self.socket.sendto(b'0' + msg, address)
        else:
            # Longer message (maybe take bytes_send into consideration?)
            index = (self.buffersize - 1) - 1
            # Send first part
            self.socket.sendto(b'1' + msg[0:index], address)
            # Send intermediate parts
            while index + (self.buffersize - 1) < len(msg):
                self.socket.sendto(
                    b'2' + msg[index:index + (self.buffersize - 1)], address)
                index += (self.buffersize - 1)
            # Send last part
            self.socket.sendto(b'3' + msg[index:], address)

    def teardown(self):
        """ Closes socket
        """
        self.socket.close()

    def receive_msg(self):
        """ Try to receive message

            Returns:
                None if no new message
                (Message, Address) if new message
        """
        try:
            msg_in, address = self.socket.recvfrom(self.buffersize)
            if msg_in[0:1] == b'0':
                # unsplit message
                self.received_data[address] = (True, msg_in[1:])
            elif msg_in[0:1] == b'1':
                # beginning of split message
                if address in self.received_data.keys():
                    # remove old unfinished message
                    self.received_data.pop(address)
                self.received_data[address] = (False, msg_in[1:])
            elif msg_in[0:1] == b'2':
                # middle of split message
                if (address in self.received_data.keys() and
                        self.received_data[address][0] is False):
                    self.received_data[address] = (
                        False, self.received_data[address][1] + msg_in[1:])
            elif msg_in[0:1] == b'3':
                # end of split message
                if (address in self.received_data.keys() and
                        self.received_data[address][0] is False):
                    self.received_data[address] = (
                        True, self.received_data[address][1] + msg_in[1:])
            else:
                # No useful message
                if address in self.received_data.keys():
                    # remove old unfinished message
                    self.received_data.pop(address)

            # check for finished message
            for addr, (finished, msg) in self.received_data.items():
                if finished:
                    self.received_data.pop(addr)
                    return(msg, addr)

        except socket.error:
            return None
        else:
            return None
