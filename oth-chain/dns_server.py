import getopt
import sys
import threading
import dnslib.server
import time

from dnslib import RR, DNSRecord, RCODE
from queue import Queue
from typing import Any
from chains import DNSBlockChain
from networking import Address, worker
from utils import print_debug_info, set_debug
import core

dns_queue: Queue = Queue()


class BlockchainResolver:

    def resolve(self, request, handler):
        reply = request.reply()
        qname = request.q.qname
        ip = self.get_ip(f'{qname}'[:-1])
        if ip:
            reply.add_answer(*RR.fromZone(f'{qname} 60 A {ip}'))
        else:
            reply.header.rcode = getattr(RCODE, 'NXDOMAIN')
        return reply

    @staticmethod
    def get_ip(name):
        core.receive_queue.put(('dns_lookup',
                                name,
                                'local'
                                ))
        ip = dns_queue.get()
        return ip


def receive_msg(msg_type: str, msg_data: Any, msg_address: Address,
                blockchain: DNSBlockChain, processor):
    """ Call blockchain functionality for received messages.

    Args:
        msg_type: String containing the type of the message.
        msg_data: Data contained by the message.
        msg_address: Address of message sender.
        blockchain: Blockchain that provides the functionality.
        processor: Processor that handles blockchain messages.
    """

    if msg_type == 'dns_lookup':
        if msg_address == 'local':
            ip = blockchain._resolve_domain_name(msg_data,time.time())[0]
            dns_queue.put(ip)
    else:
        core.receive_msg(msg_type, msg_data, msg_address,
                         blockchain, processor)


def blockchain_loop(blockchain: DNSBlockChain, processor):
    """ The main loop of the blockchain thread.

    Receives messages and processes them.

    Args:
        blockchain: The blockchain upon which to operate.
        processor: Processor used to handle blockchain messages.
    """
    while True:
        msg_type, msg_data, msg_address = core.receive_queue.get()
        print_debug_info('Processing: ' + msg_type)
        try:
            receive_msg(msg_type, msg_data, msg_address, blockchain, processor)
        except AssertionError as e:
            print_debug_info(
                f'Assertion Error on message\
                 {msg_type}:{msg_data}:{msg_address}')
            print_debug_info(e)


def parse_args(argv):
    port = 6666

    try:
        opts, _ = getopt.getopt(argv[1:], 'hdp=', [
                                'help', 'debug', 'port='])
        for o, a in opts:
            if o in ('-h', '--help'):
                print('-d/--debug to enable debug prints')
                print('-p/--port to change default port')
                sys.exit()
            if o in ('-d', '--debug'):
                set_debug()
            if o in ('-p', '--port'):
                try:
                    port = int(a)
                except ValueError:
                    print("Port was invalid (e.g. not an int)")

    except getopt.GetoptError as err:
        print('for help use --help')
        print(err)
        sys.exit()

    return port


def init(port):
    my_blockchain = DNSBlockChain(
        core.VERSION, core.send_queue, core.gui_send_queue)
    my_blockchain_processor = my_blockchain.get_message_processor()

    # Create networking thread
    networker = threading.Thread(
        target=worker,
        args=(core.send_queue,
              core.receive_queue,
              core.networker_command_queue,
              core.gui_send_queue,
              port))
    networker.start()

    # Main blockchain loop
    blockchain_thread = threading.Thread(
        target=blockchain_loop,
        args=(my_blockchain, my_blockchain_processor))
    blockchain_thread.start()

    # Update to newest chain
    core.send_queue.put(('get_newest_block', '', 'broadcast'))

    # Setup DNS server
    resolver = BlockchainResolver()

    tcp_server = dnslib.server.DNSServer(
        resolver, port=53, address='localhost', tcp=True)

    udp_server = dnslib.server.DNSServer(
        resolver, port=53, address='localhost')

    return networker, blockchain_thread, tcp_server, udp_server


def main(argv):
    networker, blockchain_thread, tcp_server, udp_server = init(
        parse_args(argv))

    tcp_server.start_thread()
    udp_server.start_thread()

    while udp_server.isAlive():
        try:
            addr = input()
            test(addr)
        except KeyboardInterrupt:
            print('Detected Keyboard interrupt, exiting program')
            core.receive_queue.put(('exit', '', 'local'))
            core.send_queue.put(None)
            blockchain_thread.join()
            networker.join()
            sys.exit()


def test(addr):
    q = dnslib.DNSRecord.question(addr)
    a = q.send("localhost", 53, tcp=True)
    print(DNSRecord.parse(a))


if __name__ == '__main__':
    main(sys.argv)
