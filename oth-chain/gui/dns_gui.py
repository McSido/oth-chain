from typing import Any, Tuple

from . import GUI

import hashlib
import sys
import threading
import time
import socket

import math

import nacl.encoding
import nacl.signing
import nacl.utils

from utils import Keystore, load_key, save_key
from chains import Block, DNS_Transaction, DNS_Data
from networking import Address

from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QApplication, QMainWindow, QSplitter, QWidget, QVBoxLayout, QTabWidget, QTreeWidget, \
    QScrollBar, QTreeWidgetItem, QListView, QPushButton, QLineEdit, QGroupBox, QFormLayout, QLabel, QHBoxLayout, \
    QFileDialog, QSpinBox, QComboBox, QRadioButton
from PyQt5 import QtCore, QtGui
from queue import Queue


def gui_loop(gui_queue: Queue, chain_queue: Queue, command_queue, keystore: Keystore):
    """ Main function of the GUI thread, creates the GUI, passes the queues to it, and
        starts the execution.
        Args:
            gui_queue: Queue for messages addressed to the GUI
            chain_queue: Queue for messages addressed to the blockchain
            command_queue: Queue for commands to the core thread.
            keystore: Keystore object, obtained from core
    """
    app = QApplication(sys.argv)
    ex = DNSChainGUI(keystore)
    ex.initUI(chain_queue, gui_queue, command_queue)

    sys.exit(app.exec_())
    

class DNSChainGUI(GUI.ChainGUI):
    """ Provides a GUI for the DNS-Chain. Provides the same functionality
        as the base class as well as additional functions specifically for
        the DNS-Chain.
    """

    def initUI(self, chain_queue: Queue, gui_queue: Queue, command_queue: Queue):
        """ Initialises the ui and sets the queues.
            Starts the thread for receiving messages.
            Args:
                chain_queue: Queue for messages addressed to the blockchain
                gui_queue: Queue for messages addressed to the GUI
                command_queue: Queue for commands to the core thread
        """
        self.splitter = QSplitter()
        self.chain_queue = chain_queue
        self.gui_queue = gui_queue
        self.command_queue = command_queue
        self.splitter.addWidget(TabWidget(self))
        self.splitter.addWidget(TransactionWidget(self))
        self.setCentralWidget(self.splitter)
        self.setWindowTitle('oth-chain')
        self.setGeometry(500, 200, 1000, 500)
        self.show()

        message_thread = threading.Thread(
            target=self.wait_for_message
        )
        message_thread.setDaemon(True)
        message_thread.start()
    
    def handle_message(self, msg_type: str, msg_data: Any, msg_address: Address):
        if msg_type == 'auction':
            self.splitter.widget(0).auction_tab.new_auction(*msg_data)
            self.splitter.widget(1).add_to_auction_list(msg_data[0][0].data.domain_name)
        elif msg_type == 'auction_expired':
            self.splitter.widget(0).auction_tab.auction_expired(msg_data)
            # remove from transaction widget
        elif msg_type == 'new_bid':
            self.splitter.widget(0).auction_tab.bid_placed(msg_data)
            # update transaction widget
        elif msg_type == 'resolved':
            self.splitter.widget(1).domain_resolved(msg_data)
        else:
            super(DNSChainGUI, self).handle_message(msg_type, msg_data, msg_address)


class TabWidget(QWidget):
    """ Widget that holds multiple tabs, for better overview.
        Args:
            parent: The parent widget.
    """

    def __init__(self, parent: QWidget):
        super(TabWidget, self).__init__(parent)
        self.layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.chain_tab = ChainHistoryWidget(self)
        self.peers_tab = GUI.PeerWidget(self)
        self.keystore_tab = GUI.KeystoreWidget(self)
        self.auction_tab = AuctionWidget(self)

        self.tabs.addTab(self.chain_tab, 'Chain history')
        self.tabs.addTab(self.peers_tab, 'Peers')
        self.tabs.addTab(self.keystore_tab, 'Keystore')
        self.tabs.addTab(self.auction_tab, 'Auctions')

        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)


class ChainHistoryWidget(GUI.ChainHistoryWidget):
    """ Widget that displays the blockchain in a treelike fashion.
    """

    @classmethod
    def create_transaction_item(cls, transaction: DNS_Transaction, number: int) -> QTreeWidgetItem:
        item = super(ChainHistoryWidget, cls).create_transaction_item(transaction, number)
        if not transaction.data == DNS_Data('', '', ''):
            data = QTreeWidgetItem()
            data.setText(0, 'DNS_Operation: ')
            operation, domain, ip = QTreeWidgetItem(), QTreeWidgetItem(), QTreeWidgetItem()
            operation.setText(0, 'Operation')
            operation.setText(1, transaction.data.type)
            domain.setText(0, 'Domain:')
            domain.setText(1, transaction.data.domain_name)
            ip.setText(0, 'IP-Address:')
            ip.setText(1, transaction.data.ip_address)
            item.addChild(data)
        return item


class AuctionWidget(QWidget):
    """ Provides a tree view to inspect ongoing auctions
        Args:
            parent: the parent widget
    """

    def __init__(self, parent: QWidget):
        super(AuctionWidget, self).__init__(parent)
        self.layout = QVBoxLayout()

        self.auctions = QTreeWidget()
        self.auctions.setColumnCount(2)
        self.auctions.setColumnWidth(0, 200)

        self.layout.addWidget(self.auctions)

        self.setLayout(self.layout)

    def new_auction(self, auction: Tuple[DNS_Transaction, DNS_Transaction],
                    expiration_block: str):
        """ Creates a new tree item for the auctions tree and appends it
            Args:
                auction: Tuple of transactions 1) the offered domain, 2) the initial bid
                expiration_block: The index of the block when the auction is resolved
        """
        offer, bid = auction
        offer_item = ChainHistoryWidget.create_transaction_item(offer, 0)
        offer_item.setText(0, 'Domain:')
        offer_item.setText(1, offer.data.domain_name)

        bid_item = ChainHistoryWidget.create_transaction_item(bid, 0)
        bid_item.setText(0, 'Highest Bid:')
        bid_item.setText(1, str(bid.amount))

        expiration_item = QTreeWidgetItem()
        expiration_item.setText(0, 'Expires in Block:')
        expiration_item.setText(1, expiration_block)

        offer_item.addChild(expiration_item)
        offer_item.addChild(bid_item)

        self.auctions.addTopLevelItem(offer_item)

    def auction_expired(self, offer: DNS_Transaction):
        """ Removes the latest auction from the tree
        """
        offer_item = self.auctions.findItems(offer.data.domain_name, QtCore.Qt.MatchExactly, column=1)[0]
        self.auctions.takeTopLevelItem(self.auctions.indexOfTopLevelItem(offer_item))

    def bid_placed(self, bid: DNS_Transaction):
        """ Removes the bid_item from the offer_item and replaces it
            with a new bid_item
            Args:
                bid: The new bid on the offer
        """
        # Replace the bid item within the offer item
        offer_item = self.auctions.findItems(bid.data.domain_name, QtCore.Qt.MatchExactly, column=1)[0]
        offer_item.takeChild(offer_item.childCount() - 1)

        bid_item = ChainHistoryWidget.create_transaction_item(bid, 0)
        bid_item.setText(0, 'Highest Bid:')
        bid_item.setText(1, bid.amount)

        offer_item.addChild(bid_item)


class TransactionWidget(GUI.TransactionWidget):
    """ Widget for interacting with the chain.
        Contains ways to change the current user, create transactions
        or start mining new blocks.
        Args:
            parent: the parent widget.
    """
    def __init__(self, parent):
        super(TransactionWidget, self).__init__(parent)

        self.current_operation = 'Register'

        self.dns_box = QGroupBox()

        self.dns_box_layout = QVBoxLayout()
        self.dns_box_form = QFormLayout()

        self.owned_domain_list = []
        self.owned_domains = QComboBox()

        self.auction_domain_list = []
        self.auctioned_domains = QComboBox()

        self.dns_recipient_edit = QLineEdit()
        self.domain_name_edit = QLineEdit()
        self.ip_address_edit = QLineEdit()

        self.bid_amount_edit = QSpinBox()

        self.resolve_edit = QLineEdit()
        self.resolve_button = QPushButton('Resolve domain name')
        self.resolve_label = QLabel()

        self.dns_send_button = QPushButton('Confirm')

        self.dns_error_label = QLabel()

        self.register_radio = QRadioButton('Register')
        self.transfer_radio = QRadioButton('Transfer')
        self.auction_radio = QRadioButton('Auction')
        self.bid_radio = QRadioButton('Bid')

        self.prepare_dns_form()

        self.chain_queue.put(('get_auctions', '', 'gui'))

    def prepare_dns_form(self):
        self.dns_box_form.addRow(QLabel('DNS Operations:'))
        self.register_radio.toggled.connect(lambda: self.operation_changed(self.register_radio))
        self.transfer_radio.toggled.connect(lambda: self.operation_changed(self.transfer_radio))
        self.auction_radio.toggled.connect(lambda: self.operation_changed(self.auction_radio))
        self.bid_radio.toggled.connect(lambda: self.operation_changed(self.bid_radio))

        radio_hbox = QHBoxLayout()
        radio_hbox.addWidget(self.register_radio)
        radio_hbox.addWidget(self.transfer_radio)
        radio_hbox.addWidget(self.auction_radio)
        radio_hbox.addWidget(self.bid_radio)
        self.register_radio.setChecked(True)

        self.dns_box_form.addRow(radio_hbox)

        self.domain_name_edit.setPlaceholderText('Domain name')
        self.ip_address_edit.setPlaceholderText('IP address')
        self.ip_address_edit.editingFinished.connect(self.valid_ip)

        domain_ip_hbox = QHBoxLayout()
        domain_ip_hbox.addWidget(self.domain_name_edit)
        domain_ip_hbox.addWidget(self.ip_address_edit)

        self.dns_box_form.addRow(domain_ip_hbox)

        selection_hbox = QHBoxLayout()
        selection_hbox.addWidget(QLabel('Owned Domains:'))
        selection_hbox.addWidget(self.owned_domains)
        selection_hbox.addWidget(QLabel('Auctioned Domains:'))
        selection_hbox.addWidget(self.auctioned_domains)

        self.dns_box_form.addRow(selection_hbox)

        self.dns_recipient_edit.setPlaceholderText('Recipient')

        recipient_amount_hbox = QHBoxLayout()
        recipient_amount_hbox.addWidget(self.dns_recipient_edit)
        recipient_amount_hbox.addWidget(self.bid_amount_edit)

        self.dns_box_form.addRow(recipient_amount_hbox)

        self.resolve_edit.setPlaceholderText('Domain name')
        self.resolve_button.clicked.connect(self.resolve)

        resolve_hbox = QHBoxLayout()
        resolve_hbox.addWidget(self.resolve_edit)
        resolve_hbox.addWidget(self.resolve_button)

        self.dns_box_form.addRow(resolve_hbox)
        self.dns_box_form.addRow(self.resolve_label)

        self.dns_box_form.addRow(self.dns_send_button)

        self.dns_box_form.addRow(self.dns_error_label)

        self.dns_box_layout.addLayout(self.dns_box_form)
        self.dns_box.setLayout(self.dns_box_layout)
        self.layout.addWidget(self.dns_box)

    def domain_resolved(self, result: Any):
        if type(result) == str:
            self.resolve_label.setText(result)
        else:
            self.resolve_label.setText(f'IP: {result[0]}, Owner: {str(result[1])}')

    def resolve(self):
        self.chain_queue.put(('dns_lookup', self.resolve_edit.text(), 'gui'))

    def add_to_auction_list(self, domain_name: str):
        self.auction_domain_list.append(domain_name)
        self.auctioned_domains.addItem(domain_name)

    def valid_ip(self):
        try:
            socket.inet_aton(self.ip_address_edit.text())
            self.dns_error_label.setText('')
        except OSError:
            self.dns_error_label.setText("Invalid IP Address!")

    def operation_changed(self, button: QRadioButton):
        if not button.isChecked():
            return
        for widget in [self.bid_amount_edit, self.dns_recipient_edit, self.owned_domains, self.auctioned_domains,
                       self.ip_address_edit, self.domain_name_edit]:
            widget.setEnabled(False)
        if button.text() == 'Register':
            self.domain_name_edit.setEnabled(True)
            self.ip_address_edit.setEnabled(True)
            self.current_operation = 'Register'
        elif button.text() == 'Transfer':
            self.owned_domains.setEnabled(True)
            self.dns_recipient_edit.setEnabled(True)
            self.current_operation = 'Transfer'
        elif button.text() == 'Auction':
            self.owned_domains.setEnabled(True)
            self.current_operation = 'Auction'
        elif button.text() == 'Bid':
            self.auctioned_domains.setEnabled(True)
            self.bid_amount_edit.setEnabled(True)
            self.current_operation = 'Bid'
