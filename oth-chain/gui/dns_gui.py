from typing import Any, Tuple

from . import GUI

import hashlib
import sys
import threading
import time

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
    QFileDialog, QSpinBox
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
    
    def handle_message(self, msg_type: str, msg_data: Any, msg_address: Address):
        if msg_type == 'auction':
            self.splitter[0].auction_tab.new_auction(msg_data)
            # add to transaction widget
        elif msg_type == 'auction_expired':
            self.splitter[0].auction_tab.auction_expired(msg_data)
            # remove from transaction widget
        elif msg_type == 'new_bid':
            self.splitter[0].auction_tab.bid_placed(msg_data)
            # update transaction widget
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

    @staticmethod
    def create_transaction_item(transaction: DNS_Transaction, number: int) -> QTreeWidgetItem:
        item = super().create_transaction_item(transaction, number)
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
        bid_item.setText(1, bid.amount)

        expiration_item = QTreeWidgetItem()
        expiration_item.setText(0, 'Expires in Block:')
        expiration_item.setText(1, expiration_block)

        offer_item.addChild(expiration_item)
        offer_item.addChild(bid_item)

        self.auctions.addTopLevelItem(offer_item)

    def auction_expired(self):
        """ Removes the latest auction from the tree
        """
        self.auctions.takeTopLevelItem(0)

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
    pass

