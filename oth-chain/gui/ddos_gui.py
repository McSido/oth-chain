import hashlib
import sys
import threading
import time

import math
from typing import Tuple, Any

import nacl.encoding
import nacl.signing
import nacl.utils

from utils import Keystore, load_key, save_key, Node
from chains import Block, DDosTransaction, DDosHeader, DDosData
from networking import Address
from . import GUI

from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QApplication, QMainWindow, QSplitter, QWidget, QVBoxLayout, QTabWidget, QTreeWidget, \
    QScrollBar, QTreeWidgetItem, QListView, QPushButton, QLineEdit, QGroupBox, QFormLayout, QLabel, QHBoxLayout, \
    QFileDialog, QSpinBox, QRadioButton
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
    ex = DDOSChainGUI(None)
    ex.initUI(chain_queue, gui_queue, command_queue)

    sys.exit(app.exec_())


class DDOSChainGUI(GUI.ChainGUI):
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
        if True:
            pass
        else:
            super(DDOSChainGUI, self).handle_message(msg_type, msg_data, msg_address)


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
        self.client_tab = ClientWidget(self)

        self.tabs.addTab(self.chain_tab, 'Chain history')
        self.tabs.addTab(self.peers_tab, 'Peers')
        self.tabs.addTab(self.client_tab, 'Auctions')

        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)


class ChainHistoryWidget(GUI.ChainHistoryWidget):

    def add_tree_item(self, block: Block):
        item = QTreeWidgetItem()
        item.setText(0, 'Block')
        item.setText(1, '#' + str(block.header.index))
        self.history.insertTopLevelItem(1, item)
        timestamp = QTreeWidgetItem()
        timestamp.setText(0, 'Timestamp:')
        timestamp.setText(1, str(time.strftime("%d.%m.%Y %H:%M:%S %Z",
                                               time.gmtime(block.header.timestamp))))
        prev_hash = QTreeWidgetItem()
        prev_hash.setText(0, 'Previous hash:')
        prev_hash.setText(1, str(block.header.previous_hash))
        root_hash = QTreeWidgetItem()
        root_hash.setText(0, 'Root hash:')
        root_hash.setText(1, str(block.header.root_hash))
        item.addChild(timestamp)
        item.addChild(prev_hash)
        item.addChild(root_hash)
        transactions = QTreeWidgetItem()
        transactions.setText(0, 'Transactions:')
        item.addChild(transactions)
        for i, transaction in enumerate(block.transactions):
            t = self.create_transaction_item(transaction, i)
            transactions.addChild(t)

    @classmethod
    def create_transaction_item(cls, transaction: DDosTransaction, number: int) -> QTreeWidgetItem:
        item = QTreeWidgetItem()
        item.setText(0, 'Transaction')
        item.setText(1, '#' + str(number))
        sender = QTreeWidgetItem()
        sender.setText(0, 'Sender:')
        sender.setText(1, str(transaction.sender))
        t_timestamp = QTreeWidgetItem()
        t_timestamp.setText(0, 'Timestamp:')
        t_timestamp.setText(1, str(time.strftime("%d.%m.%Y %H:%M:%S %Z",
                                                 time.gmtime(transaction.timestamp))))
        signature = QTreeWidgetItem()
        signature.setText(0, 'Signature')
        signature.setText(1, str(transaction.signature))

        data = QTreeWidgetItem()
        data.setText(0, 'Data:')

        d_type = QTreeWidgetItem()
        d_type.setText(0, 'Type:')
        d_type.setText(1, transaction.data.type)

        d_data = QTreeWidgetItem()
        d_data.setText(0, 'Data:')
        d_data.setText(1, str(transaction.data.data))

        data.addChildren([d_type, d_data])

        item.addChildren([sender, t_timestamp, data, signature])
        return item

    def get_timestamp_from_child(self, child: QTreeWidgetItem):
        return child.child(1).text(1)


class ClientWidget(QWidget):

    def __init__(self, parent: QWidget):
        super(ClientWidget, self).__init__(parent)
        self.layout = QVBoxLayout()

        self.clients = QTreeWidget()
        self.clients.setColumnCount(2)
        self.clients.setColumnWidth(0, 200)

        self.root_item = QTreeWidgetItem()
        self.root_item.setText(0, 'Root')

        self.layout.addWidget(self.clients)

        self.setLayout(self.layout)

    def load_data_from_tree(self, tree: Node):
        pass

    def add_to_tree(self, node: Node):
        pass

    def remove_from_tree(self, node: Node):
        pass


class TransactionWidget(GUI.TransactionWidget):

    def __init__(self, parent: QWidget):
        self.ip_edit = QLineEdit()
        self.key_edit = QLineEdit()

        self.block_radio = QRadioButton('Block IP')
        self.unblock_radio = QRadioButton('Unblock IP')
        self.invite_radio = QRadioButton('Invite User')
        self.uninvite_radio = QRadioButton('Uninvite User')
        self.purge_radio = QRadioButton('Purge User')

        self.current_operation = 'b'

        super(TransactionWidget, self).__init__(parent)

    def prepare_transaction_form(self):
        radio_hbox = QHBoxLayout()

        self.block_radio.toggled.connect(lambda: self.change_operation(self.block_radio))
        self.unblock_radio.toggled.connect(lambda: self.change_operation(self.unblock_radio))
        self.invite_radio.toggled.connect(lambda: self.change_operation(self.invite_radio))
        self.uninvite_radio.toggled.connect(lambda: self.change_operation(self.uninvite_radio))
        self.purge_radio.toggled.connect(lambda: self.change_operation(self.purge_radio))

        radio_hbox.addWidget(self.block_radio)
        radio_hbox.addWidget(self.unblock_radio)
        radio_hbox.addWidget(self.invite_radio)
        radio_hbox.addWidget(self.uninvite_radio)
        radio_hbox.addWidget(self.purge_radio)

        self.transaction_group_box_form.addRow(radio_hbox)

        edit_hbox = QHBoxLayout()

        self.ip_edit.setPlaceholderText('IP')
        self.key_edit.setPlaceholderText('Public Key')

        edit_hbox.addWidget(self.ip_edit)
        edit_hbox.addWidget(self.key_edit)

        self.transaction_group_box_form.addRow(edit_hbox)

        self.transaction_group_box_form.addRow(self.send_button)

        self.transaction_group_box_form.addRow(self.error_label)

        self.transaction_group_box_layout.addLayout(self.transaction_group_box_form)
        self.transaction_group_box.setLayout(self.transaction_group_box_layout)
        self.layout.addWidget(self.transaction_group_box)

    def send_transaction(self):
        pass

    def change_operation(self, button: QRadioButton):
        if not button.isChecked():
            return
        self.ip_edit.setEnabled(False)
        self.key_edit.setEnabled(False)
        if button.text().startswith('Bl'):
            self.ip_edit.setEnabled(True)
            self.current_operation = 'b'
        elif button.text().startswith('Unb'):
            self.ip_edit.setEnabled(True)
            self.current_operation = 'ub'
        elif button.text().startswith('In'):
            self.key_edit.setEnabled(True)
            self.current_operation = 'i'
        elif button.text().startswith('Uni'):
            self.key_edit.setEnabled(True)
            self.current_operation = 'ui'
        elif button.text().startswith('P'):
            self.key_edit.setEnabled(True)
            self.current_operation = 'p'
