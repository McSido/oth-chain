import hashlib
import sys
import threading
import time

import math
from typing import Tuple, Any

import nacl.encoding
import nacl.signing
import nacl.utils

from utils import Keystore, load_key, save_key
from chains import Block, Transaction
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
    ex = ChainGUI(keystore)
    ex.initUI(chain_queue, gui_queue, command_queue)

    sys.exit(app.exec_())


class ChainGUI(QMainWindow):
    """ Provides a graphical user interface for inspecting
        and interacting with the blockchain.
        Args:
            keystore: The keystore to manage public keys of other clients
    """

    def __init__(self, keystore: Keystore):
        super(ChainGUI, self).__init__()
        self.keystore = keystore

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

    def wait_for_message(self):
        """ Thread function for receiving messages from the gui_queue.
            Receives messages and calls the appropriate functions.
        """
        while True:
            self.handle_message(*self.gui_queue.get(block=True))

    def handle_message(self, msg_type: str, msg_data: Any, msg_address: Address):
        """ Gets a message and responds to it accordingly
        """
        if msg_type == 'new_block':
            self.splitter.widget(0).chain_tab.new_block(msg_data)
            self.splitter.widget(1).request_balance()
        elif msg_type == 'new_transaction':
            self.splitter.widget(0).chain_tab.add_transaction_pool_item(msg_data)
        elif msg_type == 'dump':
            self.splitter.widget(0).chain_tab.load_data(msg_data)
            self.splitter.widget(1).request_balance()
        elif msg_type == 'active_peer':
            self.splitter.widget(0).peers_tab.update_peers('active', msg_data)
        elif msg_type == 'inferred_peer':
            self.splitter.widget(0).peers_tab.update_peers('inferred', msg_data)
        elif msg_type == 'inactive_peer':
            self.splitter.widget(0).peers_tab.update_peers('inactive', msg_data)
        elif msg_type == 'signing_key':
            self.splitter.widget(1).update_signing_key(msg_data)
        elif msg_type == 'balance':
            self.splitter.widget(1).update_balance(msg_data)

    def closeEvent(self, a0: QtGui.QCloseEvent):
        """ Event that gets called on hitting the close-button of the GUI.
            Sends an exit command to the core, terminating the program.
        """
        self.command_queue.put('exit')
        a0.accept()


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
        self.peers_tab = PeerWidget(self)
        self.keystore_tab = KeystoreWidget(self)

        self.tabs.addTab(self.chain_tab, 'Chain history')
        self.tabs.addTab(self.peers_tab, 'Peers')
        self.tabs.addTab(self.keystore_tab, 'Keystore')

        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)


class ChainHistoryWidget(QWidget):
    """ Widget that displays the blockchain in a treelike fashion.
        Args:
            parent: The parent widget.
    """

    def __init__(self, parent: QWidget):
        super(ChainHistoryWidget, self).__init__(parent)
        self.layout = QVBoxLayout()
        self.chain_queue = self.parent().parent().chain_queue

        self.history = QTreeWidget()
        self.history.setVerticalScrollBar(QScrollBar(QtCore.Qt.Vertical))
        self.history.setHorizontalScrollBar(QScrollBar(QtCore.Qt.Horizontal))
        self.history.setColumnCount(2)
        self.history.setColumnWidth(0, 200)

        self.layout.addWidget(self.history)

        self.transaction_pool_item = QTreeWidgetItem()
        self.transaction_pool_item.setText(0, 'Transaction Pool')
        self.history.addTopLevelItem(self.transaction_pool_item)

        self.chain = []
        self.transaction_pool = []

        self.chain_queue.put(('dump', '', 'gui'))

        self.setLayout(self.layout)

    def load_data(self, data: tuple):
        """ Loads data (blocks, transactions) from a dump into the tree widget.
            Args:
                data: Tuple: [0] the chain dict, [1] the current transaction pool
        """

        self.chain = data[0]
        self.transaction_pool = data[1]

        for block, transactions in self.chain.items():
            self.add_tree_item(Block(block, transactions))
        for transaction in self.transaction_pool:
            self.add_transaction_pool_item(transaction)

    def add_tree_item(self, block: Block):
        """ Adds a new block to the tree widget.
            Args:
                block: The block to be added.
        """
        item = QTreeWidgetItem()
        item.setText(0, 'Block')
        item.setText(1, '#' + str(block.header.index))
        self.history.insertTopLevelItem(1, item)
        timestamp = QTreeWidgetItem()
        timestamp.setText(0, 'Timestamp:')
        timestamp.setText(1, str(time.strftime("%d.%m.%Y %H:%M:%S %Z",
                                               time.gmtime(block.header.timestamp))))
        proof = QTreeWidgetItem()
        proof.setText(0, 'Proof:')
        proof.setText(1, str(block.header.proof))
        prev_hash = QTreeWidgetItem()
        prev_hash.setText(0, 'Previous hash:')
        prev_hash.setText(1, str(block.header.previous_hash))
        root_hash = QTreeWidgetItem()
        root_hash.setText(0, 'Root hash:')
        root_hash.setText(1, str(block.header.root_hash))
        item.addChild(timestamp)
        item.addChild(proof)
        item.addChild(prev_hash)
        item.addChild(root_hash)
        transactions = QTreeWidgetItem()
        transactions.setText(0, 'Transactions:')
        item.addChild(transactions)
        for i, transaction in enumerate(block.transactions):
            t = self.create_transaction_item(transaction, i)
            transactions.addChild(t)

    def add_transaction_pool_item(self, transaction: Transaction):
        """ Adds a new transaction to the transaction pool.
            Args:
                transaction: the transaction to add.
        """
        item = self.create_transaction_item(transaction, self.transaction_pool_item.childCount())
        self.transaction_pool_item.insertChild(0, item)

    @classmethod
    def create_transaction_item(cls, transaction: Transaction, number: int) -> QTreeWidgetItem:
        """ Takes a transaction object and builds an item for the tree widget from it.
            Args:
                transaction: the transaction object.
                number: the index of the transaction.
        """
        item = QTreeWidgetItem()
        item.setText(0, 'Transaction')
        item.setText(1, '#' + str(number))
        sender = QTreeWidgetItem()
        sender.setText(0, 'Sender:')
        sender.setText(1, str(transaction.sender))
        recipient = QTreeWidgetItem()
        recipient.setText(0, 'Recipient:')
        recipient.setText(1, str(transaction.recipient))
        amount = QTreeWidgetItem()
        amount.setText(0, 'Amount:')
        amount.setText(1, str(transaction.amount))
        fee = QTreeWidgetItem()
        fee.setText(0, 'Fee:')
        fee.setText(1, str(transaction.fee))
        t_timestamp = QTreeWidgetItem()
        t_timestamp.setText(0, 'Timestamp:')
        t_timestamp.setText(1, str(time.strftime("%d.%m.%Y %H:%M:%S %Z",
                                                 time.gmtime(transaction.timestamp))))
        signature = QTreeWidgetItem()
        signature.setText(0, 'Signature')
        signature.setText(1, str(transaction.signature))
        item.addChildren([sender, recipient, amount, fee, t_timestamp, signature])
        return item

    def new_block(self, block: Block):
        """ Calls the functions to add a new block and clear the transaction pool.
            Args:
                block: the block to be added
        """
        self.add_tree_item(block)
        self.clear_transaction_pool(block.transactions)

    def clear_transaction_pool(self, transaction_list: list):
        """ Takes a list of transactions and removes all
            items in the list from the transaction pool.
            Args:
                transaction_list: list of transaction contained in the latest block.
        """
        items_to_delete = []
        for transaction in transaction_list:
            timestamp = time.strftime("%d.%m.%Y %H:%M:%S %Z",
                                      time.gmtime(transaction.timestamp))
            for i in range(self.transaction_pool_item.childCount()):
                if self.transaction_pool_item.child(i).child(4).text(1) == timestamp:
                    items_to_delete.append(self.transaction_pool_item.child(i))

        for item in items_to_delete:
            self.transaction_pool_item.removeChild(item)


class PeerWidget(QWidget):
    """ Widget that displays the peers of the network.
        Args:
            parent: The parent widget
    """

    def __init__(self, parent: QWidget):
        super(PeerWidget, self).__init__(parent)
        self.layout = QVBoxLayout()

        self.peers = QTreeWidget()
        self.peers.setColumnCount(2)
        self.peers.setColumnWidth(0, 200)
        self.active_peers = QTreeWidgetItem()
        self.active_peers.setText(0, 'Active Peers:')
        self.known_peers = QTreeWidgetItem()
        self.known_peers.setText(0, 'Known Peers:')
        self.inactive_peers = QTreeWidgetItem()
        self.inactive_peers.setText(0, 'Inactive Peers:')

        self.peers.addTopLevelItems([self.active_peers, self.known_peers, self.inactive_peers])

        self.layout.addWidget(self.peers)

        self.setLayout(self.layout)

    def update_peers(self, typ, address):
        """ Updates the tree widget of the peers.
            Args:
                typ: the type of change to the peer list.
                address: the ip address of the peer that has changed state.
        """
        if typ == 'inferred':
            item = QTreeWidgetItem()
            item.setText(0, 'Address:')
            item.setText(1, f'{str(address[0])}:{str(address[1])}')
            self.known_peers.addChild(item)
        elif typ == 'active':
            for i in range(self.inactive_peers.childCount()):
                if self.inactive_peers.child(i).text(1) == f'{str(address[0])}:{str(address[1])}':
                    item = self.inactive_peers.takeChild(i)
                    self.active_peers.addChild(item)
                    return
            for i in range(self.known_peers.childCount()):
                if self.known_peers.child(i).text(1) == f'{str(address[0])}:{str(address[1])}':
                    item = self.known_peers.takeChild(i)
                    self.active_peers.addChild(item)
                    return
            item = QTreeWidgetItem()
            item.setText(0, 'Address')
            item.setText(1, f'{str(address[0])}:{str(address[1])}')
            self.active_peers.addChild(item)
        elif typ == 'inactive':
            for i in range(self.active_peers.childCount()):
                if self.active_peers.child(i).text(1) == f'{str(address[0])}:{str(address[1])}':
                    item = self.active_peers.takeChild(i)
                    self.inactive_peers.addChild(item)
                    return
            for i in range(self.known_peers.childCount()):
                if self.known_peers.child(i).text(1) == f'{str(address[0])}:{str(address[1])}':
                    item = self.known_peers.takeChild(i)
                    self.inactive_peers.addChild(item)
                    return
            item = QTreeWidgetItem()
            item.setText(0, 'Address')
            item.setText(1, f'{str(address[0])}:{str(address[1])}')
            self.inactive_peers.addChild(item)


class KeystoreWidget(QWidget):
    """ Widget to display and manage the public keys
        of other clients in the network.
        Args:
            parent: the parent widget
    """

    def __init__(self, parent: QWidget):
        super(KeystoreWidget, self).__init__(parent)
        self.keystore = self.parent().parent().keystore
        self.layout = QVBoxLayout()
        self.key_list = QListView()
        self.key_list.setHorizontalScrollBar(QScrollBar(QtCore.Qt.Horizontal))
        self.key_list.setVerticalScrollBar(QScrollBar(QtCore.Qt.Vertical))
        self.model = QStandardItemModel(self.key_list)
        self.model.itemChanged.connect(self.set_item)
        self.checked_items = []
        self.load_data()

        self.key_list.setModel(self.model)
        self.layout.addWidget(self.key_list)

        self.delete_button = QPushButton('Delete selected keys')
        self.delete_button.clicked.connect(self.delete_keys)
        self.layout.addWidget(self.delete_button)

        self.import_key_button = QPushButton('Import key')
        self.import_key_button.clicked.connect(self.import_key)
        self.import_key_name_edit = QLineEdit()
        self.import_key_name_edit.setPlaceholderText('Name')
        self.import_key_file_explorer = QPushButton('Select file')
        self.import_key_file_explorer.clicked.connect(self.get_key_file)

        self.import_key_file_name = None

        self.import_key_group = QGroupBox()
        self.import_key_group.setLayout(QVBoxLayout())
        self.import_key_group_form = QFormLayout()
        self.import_key_group_form.addRow(QLabel('Import key:'))
        self.import_key_group_form.addRow(QLabel('Key file:'), self.import_key_file_explorer)
        hbox = QHBoxLayout()
        hbox.addWidget(self.import_key_name_edit)
        hbox.addWidget(self.import_key_button)
        self.import_key_group_form.addRow(hbox)
        self.import_key_group.layout().addLayout(self.import_key_group_form)
        self.layout.addWidget(self.import_key_group)

        self.setLayout(self.layout)

    def set_item(self, item: QStandardItem):
        """ Checks if an item is checked or not, and adds/removes it
            to/from the list of checked items
            Args:
                item: the item that changed its' state
        """
        if item.checkState() == QtCore.Qt.Checked:
            self.checked_items.append(item)
        elif item.checkState() == QtCore.Qt.Unchecked:
            try:
                self.checked_items.remove(item)
            except ValueError:
                pass

    def delete_keys(self):
        """ Deletes all checked items from the keystore.
        """
        self.checked_items.sort(key=lambda x: x.row())
        for item in self.checked_items[::-1]:
            key = item.text().split(':')[0]
            self.keystore.update_key(key, '')
            self.model.removeRow(item.row())
        self.checked_items = []

    def load_data(self):
        """ Loads all keys from the keystore, when initiated.
        """
        for key, value in self.keystore.store.items():
            item = QStandardItem(f'{key}: {str(value)}')
            item.setCheckable(True)
            self.model.appendRow(item)

    def get_key_file(self):
        """ Opens a file dialog to get the file name of a public key file
        """
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        self.import_key_file_name, _ = QFileDialog.getOpenFileName(self, 'Select key file', '',
                                                                   'All Files (*);;', options=options)
        self.import_key_file_explorer.setText(self.import_key_file_name)

    def import_key(self):
        """ Imports/Updates a key into the keystore
        """
        key_name = self.import_key_name_edit.text()
        key, success = self.keystore.add_key(key_name, self.import_key_file_name)
        if not success:
            old_key = self.keystore.update_key(key_name, self.import_key_file_name)
            item = self.model.findItems(f'{key_name}: {str(old_key)}')[0]
            row = item.row()
            self.model.removeRow(row)
            item = QStandardItem(f'{key_name}: {str(key)}')
            item.setCheckable(True)
            self.model.insertRow(row, item)
        else:
            item = QStandardItem(f'{key_name}: {str(key)}')
            item.setCheckable(True)
            self.model.appendRow(item)


class TransactionWidget(QWidget):
    """ Widget for interacting with the chain.
        Contains ways to change the current user, create transactions
        or start mining new blocks.
        Args:
            parent: the parent widget.
    """

    def __init__(self, parent: QWidget):
        super(TransactionWidget, self).__init__(parent)
        self.chain_queue = self.parent().chain_queue
        self.keystore = self.parent().keystore
        self.layout = QVBoxLayout(self)
        self.signing_key = None
        self.verify_key_hex = None

        self.user_group_box = QGroupBox()

        self.user_group_box_layout = QVBoxLayout()
        self.user_group_box_form = QFormLayout()

        self.load_key_button = QPushButton('Load private Key')
        self.export_key_button = QPushButton('Export public Key')
        self.save_key_button = QPushButton('Save private Key')
        self.user_field = QLineEdit()
        self.mine_button = QPushButton('Start Mining')

        self.transaction_group_box = QGroupBox()

        self.transaction_group_box_layout = QVBoxLayout()
        self.transaction_group_box_form = QFormLayout()

        self.balance_label = QLabel('Current Balance: 0')
        self.recipient_edit = QLineEdit()
        self.amount_edit = QSpinBox()
        self.send_button = QPushButton('Send')

        self.fee_label = QLabel('Fee: 1')
        self.error_label = QLabel()

        self.setLayout(self.layout)

        self.prepare_user_form()
        self.prepare_transaction_form()

    def prepare_user_form(self):
        """ Prepares the user form of this widget
        """
        self.load_key_button.clicked.connect(self.load_signing_key)
        key_hbox = QHBoxLayout()
        self.user_field.setEnabled(False)
        self.user_field.setPlaceholderText('Key')

        key_hbox.addWidget(self.save_key_button)
        key_hbox.addWidget(self.load_key_button)
        key_hbox.addWidget(self.export_key_button)

        self.save_key_button.clicked.connect(self.save_signing_key)
        self.export_key_button.clicked.connect(self.export_verify_key)

        self.user_group_box_form.addRow(QLabel('User:'), self.user_field)
        self.user_group_box_form.addRow(key_hbox)

        self.mine_button.clicked.connect(self.mine)
        self.user_group_box_form.addRow(self.mine_button)

        self.user_group_box_layout.addLayout(self.user_group_box_form)
        self.user_group_box.setLayout(self.user_group_box_layout)
        self.layout.addWidget(self.user_group_box)

    def prepare_transaction_form(self):
        """ Prepares the transaction form of this widget
        """
        self.transaction_group_box_form.addRow(QLabel('New Transaction:'))
        self.transaction_group_box_form.addRow(self.balance_label)

        self.recipient_edit.setPlaceholderText('Recipient')
        self.amount_edit.valueChanged.connect(self.update_fee)

        self.send_button.clicked.connect(self.send_transaction)

        transaction_hbox = QHBoxLayout()
        transaction_hbox.addWidget(self.amount_edit)
        transaction_hbox.addWidget(self.fee_label)

        self.amount_edit.setMinimum(1)
        self.amount_edit.setMaximum(9999)

        self.transaction_group_box_form.addRow(QLabel(), self.recipient_edit)
        self.transaction_group_box_form.addRow(QLabel('Amount'), transaction_hbox)
        self.transaction_group_box_form.addRow(QLabel(), self.send_button)

        self.transaction_group_box_layout.addLayout(self.transaction_group_box_form)
        self.transaction_group_box.setLayout(self.transaction_group_box_layout)
        self.layout.addWidget(self.transaction_group_box)

        self.error_label.hide()
        self.transaction_group_box_form.addRow(self.error_label)

    def mine(self):
        """ Send a mine message to the blockchain
        """
        self.chain_queue.put(('mine', self.verify_key_hex, 'local'))

    def update_fee(self):
        """ Updates the fee label based on the transaction amount
        """
        fee = math.ceil(self.amount_edit.value() * 0.05)
        self.fee_label.setText(f'Fee: {fee}')

    def send_transaction(self):
        """ Creates a transaction and sends a new_transaction message to the chain.
        """
        self.error_label.hide()
        recipient = self.keystore.resolve_name(self.recipient_edit.text())
        if recipient == 'Error':
            self.error_label.setText('Error: Recipient name could not be found in the keystore!')
            self.error_label.show()
            return
        amount = self.amount_edit.value()
        fee = math.ceil(amount * 0.05)

        if amount + fee > int(self.balance_label.text().split(': ')[1]):
            self.error_label.setText('Error: Current balance is not sufficient for this transaction!')
            self.error_label.show()
            return

        transaction = self.prepare_transaction(recipient, amount, fee, time.time())

        self.chain_queue.put(('new_transaction',
                              transaction,
                              'gui'
                              ))

    def prepare_transaction(self, recipient, amount, fee, timestamp):
        transaction_hash = hashlib. \
            sha256((str(self.verify_key_hex) +
                    str(recipient) + str(amount)
                    + str(fee) +
                    str(timestamp)).encode()).hexdigest()

        transaction = Transaction(self.verify_key_hex,
                                  recipient,
                                  amount,
                                  fee,
                                  timestamp,
                                  self.signing_key.sign(
                                      transaction_hash.encode())
                                  )
        return transaction

    def load_signing_key(self):
        """ Loads a private key, to change the current user.
        """
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, _ = QFileDialog.getOpenFileName(self, 'Select key file', '',
                                                   'All Files (*);;', options=options)
        if not file_name:
            return
        key = load_key(file_name)
        self.update_signing_key(key)

    def save_signing_key(self):
        """ Saves the private key to a file.
        """
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, _ = QFileDialog.getSaveFileName(self, 'Save key file', '',
                                                   'All Files (*);;', options=options)
        if not file_name:
            return
        save_key(self.signing_key, file_name)

    def export_verify_key(self):
        """ Exports the public key generated from the private key to a file.
        """
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, _ = QFileDialog.getSaveFileName(self, 'Save key file', '',
                                                   'All Files (*);;', options=options)
        if not file_name:
            return
        save_key(self.verify_key_hex, file_name)

    def update_signing_key(self, key: nacl.signing.SigningKey):
        """ Updates the private key with a key from a previously loaded file.
            Args:
                key: The new private key.
        """
        self.signing_key = key
        verify_key = self.signing_key.verify_key
        self.verify_key_hex = verify_key.encode(nacl.encoding.HexEncoder)
        self.user_field.setText(str(self.verify_key_hex))

    def update_balance(self, balance: int):
        """ Updates the balance when a new block is received.
            Args:
                balance: The new balance of the current user.
        """
        self.balance_label.setText(f'Current Balance: {balance}')

    def request_balance(self):
        """ Sends a print_balance message to the chain.
        """
        self.chain_queue.put(('print_balance',
                              (self.verify_key_hex, time.time()),
                              'gui'))
