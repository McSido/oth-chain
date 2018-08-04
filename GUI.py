import sys
import threading
import time
from functools import partial

from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import *
from PyQt5 import QtGui, QtCore
from queue import Queue

lineQueue = Queue()


def gui_loop(gui_queue, chain_queue, keystore):
    app = QApplication(sys.argv)
    ex = ChainGUI(keystore)
    ex.initUI(chain_queue, gui_queue)

    sys.exit(app.exec_())


class ChainGUI(QMainWindow):

    def __init__(self, keystore):
        super(ChainGUI, self).__init__()
        self.lineEditHistory = list()
        self.lineHistoryCounter = len(self.lineEditHistory)
        self.keystore = keystore

    def initUI(self, chain_queue, gui_queue):
        self.splitter = QSplitter()
        self.chain_queue = chain_queue
        self.gui_queue = gui_queue
        self.splitter.addWidget(TabWidget(self))
        self.splitter.addWidget(TransactionWidget(self))
        self.setCentralWidget(self.splitter)
        self.setWindowTitle('OTH-Chain')
        self.show()

        message_thread = threading.Thread(
            target=self.wait_for_message
        )
        message_thread.setDaemon(True)
        message_thread.start()

    def wait_for_message(self):
        while True:
            msg_type, msg_data, msg_address = self.gui_queue.get(block=True)
            if msg_type == 'new_block':
                self.splitter.widget(0).chain_tab.add_tree_item(msg_data)



class TabWidget(QWidget):

    def __init__(self, parent):
        super(TabWidget, self).__init__(parent)
        self.layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.chain_tab = ChainHistoryWidget(self)
        self.peers_tab = QWidget()
        self.keystore_tab = KeystoreWidget(self)

        self.tabs.addTab(self.chain_tab, 'Chain history')
        self.tabs.addTab(self.peers_tab, 'Peers')
        self.tabs.addTab(self.keystore_tab, 'Keystore')

        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)


class ChainHistoryWidget(QWidget):

    def __init__(self, parent):
        super(ChainHistoryWidget, self).__init__(parent)
        self.layout = QVBoxLayout()
        self.chain_queue = self.parent().parent().chain_queue
        self.gui_queue = self.parent().parent().gui_queue

        self.history = QTreeWidget()
        self.history.setVerticalScrollBar(QScrollBar(QtCore.Qt.Vertical))
        self.history.setHorizontalScrollBar(QScrollBar(QtCore.Qt.Horizontal))
        self.history.setColumnCount(2)

        self.layout.addWidget(self.history)

        self.transaction_pool_item = QTreeWidgetItem()
        self.transaction_pool_item.setText(0, 'Transaction Pool')
        self.history.addTopLevelItem(self.transaction_pool_item)

        self.chain = []
        self.transaction_pool = []

        self.load_data()

        self.setLayout(self.layout)

    def load_data(self):
        self.chain_queue.put(('dump', '', 'gui'))
        data = self.gui_queue.get(block=True)[1]
        self.chain = data[0]
        self.transaction_pool = data[1]
        print(self.chain)
        for block in self.chain:
            self.add_tree_item(block)
        for transaction in self.transaction_pool:
            self.add_transaction_pool_item(transaction)

    def add_tree_item(self, block):
        item = QTreeWidgetItem()
        item.setText(0, 'Block')
        item.setText(1, '#' + str(block.index))
        self.history.insertTopLevelItem(1, item)
        timestamp = QTreeWidgetItem()
        timestamp.setText(0, 'Timestamp:')
        timestamp.setText(1, str(time.strftime("%d.%m.%Y %H:%M:%S %Z",
                                               time.gmtime(block.timestamp))))
        proof = QTreeWidgetItem()
        proof.setText(0, 'Proof:')
        proof.setText(1, str(block.proof))
        prev_hash = QTreeWidgetItem()
        prev_hash.setText(0, 'Previous hash:')
        prev_hash.setText(1, str(block.previous_hash))
        item.addChild(timestamp)
        item.addChild(proof)
        item.addChild(prev_hash)
        transactions = QTreeWidgetItem()
        transactions.setText(0, 'Transactions:')
        item.addChild(transactions)
        for i, transaction in enumerate(block.transactions):
            t = QTreeWidgetItem()
            t.setText(0, 'Transaction')
            t.setText(1, '#' + str(i))
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
            t.addChildren([sender, recipient, amount, fee, t_timestamp, signature])
            transactions.addChild(t)

    def add_transaction_pool_item(self, transaction):
        item = QTreeWidgetItem()
        item.setText(0, 'Transaction')
        item.setText(1, '#' + str(self.transaction_pool_item.childCount()))
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
        t_timestamp.setText(1, str(transaction.timestamp))
        signature = QTreeWidgetItem()
        signature.setText(0, 'Signature')
        signature.setText(1, str(time.strftime("%d.%m.%Y %H:%M:%S %Z",
                                               time.gmtime(transaction.timestamp))))
        item.addChildren([sender, recipient, amount, fee, t_timestamp, signature])
        self.transaction_pool_item.addChild(item)


class KeystoreWidget(QWidget):

    def __init__(self, parent):
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

    def set_item(self, item):
        if item.checkState() == QtCore.Qt.Checked:
            self.checked_items.append(item)
        elif item.checkState() == QtCore.Qt.Unchecked:
            try:
                self.checked_items.remove(item)
            except ValueError:
                pass

    def delete_keys(self):
        self.checked_items.sort(key=lambda x: x.row())
        for item in self.checked_items[::-1]:
            key = item.text().split(':')[0]
            self.keystore.update_key(key, '')
            self.model.removeRow(item.row())
        self.checked_items = []

    def load_data(self):
        for key, value in self.keystore.store.items():
            item = QStandardItem(f'{key}: {str(value)}')
            item.setCheckable(True)
            self.model.appendRow(item)

    def get_key_file(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        self.import_key_file_name, _ = QFileDialog.getOpenFileName(self, 'Select key file', '',
                                                                   'All Files (*);;', options=options)
        self.import_key_file_explorer.setText(self.import_key_file_name)

    def import_key(self):
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

    def __init__(self, parent):
        super(TransactionWidget, self).__init__(parent)
        self.layout = QVBoxLayout(self)

        self.user_group_box = QGroupBox()

        self.user_group_box_layout = QVBoxLayout()
        self.user_group_box_form = QFormLayout()

        self.load_key_button = QPushButton('Load private Key')
        self.export_key_button = QPushButton('Export public Key')
        user_hbox = QHBoxLayout()
        self.user_field = QLineEdit()
        self.user_field.setEnabled(False)
        self.user_field.setPlaceholderText('Key')
        user_hbox.addWidget(self.user_field)
        user_hbox.addWidget(self.load_key_button)
        user_hbox.addWidget(self.export_key_button)

        self.user_group_box_form.addRow(QLabel('User:'), user_hbox)

        self.user_group_box_layout.addLayout(self.user_group_box_form)
        self.user_group_box.setLayout(self.user_group_box_layout)
        self.layout.addWidget(self.user_group_box)

        self.transaction_group_box = QGroupBox()

        self.transaction_group_box_layout = QVBoxLayout()
        self.transaction_group_box_form = QFormLayout()

        self.transaction_group_box_form.addRow(QLabel('New Transaction:'))
        self.recipient_edit = QLineEdit()
        self.recipient_edit.setPlaceholderText('Recipient')
        self.amount_edit = QSpinBox()
        self.amount_edit.setMaximum(9999)
        self.send_button = QPushButton('Send')

        self.transaction_group_box_form.addRow(QLabel(), self.recipient_edit)
        self.transaction_group_box_form.addRow(QLabel('Amount'), self.amount_edit)
        self.transaction_group_box_form.addRow(QLabel(), self.send_button)

        self.transaction_group_box_layout.addLayout(self.transaction_group_box_form)
        self.transaction_group_box.setLayout(self.transaction_group_box_layout)
        self.layout.addWidget(self.transaction_group_box)

        self.setLayout(self.layout)
