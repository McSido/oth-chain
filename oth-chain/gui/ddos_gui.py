import hashlib
import sys
import threading
import time

import math
from typing import Tuple, Any, Union

import nacl.encoding
import nacl.signing
import nacl.utils

from utils import load_key, save_key, Node
from chains import Block, DDosTransaction, DDosHeader, DDosData
from networking import Address
from . import GUI

from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QApplication, QMainWindow, QSplitter, QWidget, QVBoxLayout, QTabWidget, QTreeWidget, \
    QScrollBar, QTreeWidgetItem, QListView, QPushButton, QLineEdit, QGroupBox, QFormLayout, QLabel, QHBoxLayout, \
    QFileDialog, QSpinBox, QRadioButton, QComboBox
from PyQt5 import QtCore, QtGui
from queue import Queue


def gui_loop(gui_queue: Queue, chain_queue: Queue, command_queue):
    """ Main function of the GUI thread, creates the GUI, passes the queues to it, and
        starts the execution.
        Args:
            gui_queue: Queue for messages addressed to the GUI
            chain_queue: Queue for messages addressed to the blockchain
            command_queue: Queue for commands to the core thread.
    """
    app = QApplication(sys.argv)
    ex = DDOSChainGUI(None, chain_queue, gui_queue, command_queue)
    sys.exit(app.exec_())


class DDOSChainGUI(GUI.ChainGUI):
    """ Provides a GUI for the DDOS-Chain. Replaces the default transaction form
        with a DDoS chain specific transaction form.
    """

    def initUI(self):
        """ Initialises the ui.
            Starts the thread for receiving messages.
        """
        self.splitter.addWidget(TabWidget(self))
        self.splitter.addWidget(TransactionWidget(self))
        self.setCentralWidget(self.splitter)
        self.setWindowTitle('oth-chain (DDoS Chain)')
        self.setGeometry(500, 200, 1000, 500)
        self.show()

        self.start_message_thread()

    def handle_message(self, msg_type: str, msg_data: Any, msg_address: Address):
        """ Handles DDoS specific messages or delegates them to the superclass.
            Args:
                msg_type: Specifies the incoming message.
                msg_data: The data contained within the message.
                msg_address: From where the message was sent.
        """
        if msg_type == 'tree':
            if msg_data:
                self.splitter.widget(1).set_tree(msg_data)
                self.splitter.widget(0).client_tab.load_data_from_tree(msg_data)
        elif msg_type == 'operation':
            self.splitter.widget(1).react_to_operation(msg_data)
            self.splitter.widget(0).client_tab.react_to_operation(msg_data)
        else:
            super(DDOSChainGUI, self).handle_message(msg_type, msg_data, msg_address)


class TabWidget(QWidget):
    """ Widget that holds multiple tabs, for better overview.
        Overwritten from GUI.py to use DDoS specific widgets
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
        self.tabs.addTab(self.client_tab, 'Invited Clients')

        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)


class ChainHistoryWidget(GUI.ChainHistoryWidget):
    """ DDoS specific version of the ChainHistoryWidget
        Holds blocks and transactions and displays them
        in a tree like view.
    """

    def add_tree_item(self, block: Block):
        """ Builds a tree widget item from a given block and
            adds it to the tree view.
            Args:
                block: The block to build an item from.
        """
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
        """ Takes a DDosTransaction object and builds
            a tree widget item from it.
            Args:
                  transaction: The given transaction
                  number: Specifies the number of the
                    transaction in the current context
        """
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
        """ Returns the timestamp of a given tree widget item
            to identify specific items.
            Args:
                child: The item from which to get the timestamp
        """
        return child.child(1).text(1)


class ClientWidget(QWidget):
    """ Displays the descendants of the current user
        in the invitation tree of the chain and displays
        them in a tree like fashion.
        Args:
            parent: The parent widget
    """

    def __init__(self, parent: QWidget):
        super(ClientWidget, self).__init__(parent)
        self.layout = QVBoxLayout()

        self.clients = QTreeWidget()
        self.clients.setColumnCount(1)
        self.clients.setColumnWidth(0, 400)

        self.layout.addWidget(self.clients)

        self.setLayout(self.layout)

    def load_data_from_tree(self, tree: Node, parent_item: QTreeWidgetItem = None):
        """ Takes a node object and initializes the tree view with the contents
            of the nodes.
            Args:
                tree: the 'root' node of the given tree
                parent_item: Specifies the parent item to append new items to.
                    Used for recursive calls of the function
        """
        if parent_item is None:
            parent_item = QTreeWidgetItem()
            parent_item.setText(0, str(tree.content))
            self.clients.addTopLevelItem(parent_item)
        for child in tree.children:
            child_item = QTreeWidgetItem()
            child_item.setText(0, str(child.content))
            parent_item.addChild(child_item)
            self.load_data_from_tree(child, child_item)

    def add_to_tree(self, sender: str, key: str):
        """ Takes a key and adds it to the children of the item
            specified by a given sender.
            Args:
                sender: Specifies who invited the user
                key: public key of the invited user
        """
        parent = self.find_item(sender)
        item = QTreeWidgetItem()
        item.setText(0, key)
        parent.addChild(item)

    def remove_from_tree(self, key: str):
        """ Takes a key and removes it from the tree
            Args:
                key: public key of the uninvited user
        """
        item = self.find_item(key)
        parent = item.parent()
        for i in range(item.childCount()):
            child = item.child(i)
            parent.addChild(child)
        parent.removeChild(item)

    def find_item(self, key: str) -> QTreeWidgetItem:
        """ Takes a key and returns the item holding it
            Args:
                key: public key of some user.
        """
        item = self.clients.findItems(key, QtCore.Qt.MatchRecursive, 0)[0]
        return item

    def react_to_operation(self, transaction: DDosTransaction):
        """ Takes a transaction and reacts to it.
            Args:
                transaction: DDoSTransaction object.
                    If the transaction holds an (un-)invitation,
                    the respective functions are called.
        """
        if transaction.data.type == 'ui':
            self.remove_from_tree(str(transaction.data.data))
        elif transaction.data.type == 'i':
            self.add_to_tree(str(transaction.sender), str(transaction.data.data))


class TransactionWidget(GUI.TransactionWidget):
    """ Sub class of GUI.TransactionWidget.
        Changed to accommodate the needs of the DDoS chain.
        Args:
            parent: The parent widget
    """

    def __init__(self, parent: QWidget):
        self.ip_edit = QLineEdit()
        self.key_edit = QLineEdit()

        self.descendants = QComboBox()

        self.block_radio = QRadioButton('Block IP')
        self.unblock_radio = QRadioButton('Unblock IP')
        self.invite_radio = QRadioButton('Invite User')
        self.uninvite_radio = QRadioButton('Uninvite User')
        self.purge_radio = QRadioButton('Purge User')

        self.current_operation = 'b'

        self.tree = None

        super(TransactionWidget, self).__init__(parent)

        self.mine_button.hide()

    def prepare_transaction_form(self):
        """ Prepares the transaction form of this widget.
        """
        radio_hbox = QHBoxLayout()

        self.block_radio.toggled.connect(lambda: self.change_operation(self.block_radio))
        self.unblock_radio.toggled.connect(lambda: self.change_operation(self.unblock_radio))
        self.invite_radio.toggled.connect(lambda: self.change_operation(self.invite_radio))
        self.uninvite_radio.toggled.connect(lambda: self.change_operation(self.uninvite_radio))
        self.purge_radio.toggled.connect(lambda: self.change_operation(self.purge_radio))

        self.block_radio.toggle()

        radio_hbox.addWidget(self.block_radio)
        radio_hbox.addWidget(self.unblock_radio)
        radio_hbox.addWidget(self.invite_radio)
        radio_hbox.addWidget(self.uninvite_radio)
        radio_hbox.addWidget(self.purge_radio)

        self.transaction_group_box_form.addRow(radio_hbox)

        edit_hbox = QHBoxLayout()

        self.ip_edit.setFixedWidth(100)
        self.ip_edit.setPlaceholderText('IP')
        self.key_edit.setPlaceholderText('Public Key')

        edit_hbox.addWidget(self.ip_edit)
        edit_hbox.addWidget(self.key_edit)

        self.transaction_group_box_form.addRow(edit_hbox)

        self.transaction_group_box_form.addRow(QLabel('Invited Clients: '), self.descendants)

        self.send_button.clicked.connect(self.send_transaction)

        self.transaction_group_box_form.addRow(self.send_button)

        self.transaction_group_box_form.addRow(self.error_label)

        self.transaction_group_box_layout.addLayout(self.transaction_group_box_form)
        self.transaction_group_box.setLayout(self.transaction_group_box_layout)
        self.layout.addWidget(self.transaction_group_box)

    def send_transaction(self):
        """ Determines the DDoS Data object for the transaction
            calls a function to build the transaction and sends it.
        """
        if self.current_operation == 'b' or self.current_operation == 'ub':
            data = self.ip_edit.text()
        elif self.current_operation == 'i':
            data = self.key_edit.text()
        else:
            data = self.descendants.currentText()
        transaction = self.prep_transaction(DDosData(self.current_operation, data))
        self.chain_queue.put(('new_transaction', transaction, 'gui'))

    def prep_transaction(self, data: DDosData):
        """ Takes a DDoS Data object and builds
            a DDoSTransaction object from it.
            Args:
                data: The DDoS Data specifying a certain operation.
        """
        timestamp = time.time()
        hash_str = (str(self.verify_key_hex) +
                    str(data) +
                    str(timestamp))
        transaction_hash = hashlib.sha256(hash_str.encode()).hexdigest()

        transaction = DDosTransaction(
            self.verify_key_hex,
            timestamp,
            data,
            self.signing_key.sign(transaction_hash.encode())
        )

        return transaction

    def change_operation(self, button: QRadioButton):
        """ Dis-/Enables specific widgets, according to the
            selected radio button.
            Args:
                button: The button, that was toggled.
        """
        if not button.isChecked():
            return
        self.ip_edit.setEnabled(False)
        self.key_edit.setEnabled(False)
        self.descendants.setEnabled(False)
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
            self.descendants.setEnabled(True)
            self.current_operation = 'ui'
        elif button.text().startswith('P'):
            self.descendants.setEnabled(True)
            self.current_operation = 'p'

    def set_tree(self, tree: Node):
        """ Sets the invitation tree of this widget and
            adds the contents of the tree to a selection box.
            Args:
                tree: The invitation tree to accept.
        """
        self.tree = tree
        self.descendants.addItems(str(d.content) for d in tree.get_descendants())

    def react_to_operation(self, transaction: DDosTransaction):
        """ Takes a transaction and reacts to it, if
            a user is (un-)invited.
            Args:
                transaction: The transaction containing a certain operation.
        """
        if transaction.data.type == 'i':
            self.descendants.addItem(transaction.data.data)
        elif transaction.data.type == 'ui':
            index = self.descendants.findText(transaction.data.data)
            self.descendants.removeItem(index)
