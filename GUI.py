import sys
import threading
import datetime
from functools import partial

from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import *
from PyQt5 import QtGui, QtCore
from queue import Queue

lineQueue = Queue()


def gui_loop(gui_send_queue, gui_receive_queue, keystore):
    app = QApplication(sys.argv)
    ex = ChainGUI(keystore)
    ex.initUI(gui_receive_queue)

    sys.exit(app.exec_())


class ChainGUI(QMainWindow):

    def __init__(self, keystore):
        super(ChainGUI, self).__init__()
        self.lineEditHistory = list()
        self.lineHistoryCounter = len(self.lineEditHistory)
        self.keystore = keystore

    def initUI(self, receive_queue):
        self.splitter = QSplitter()
        self.splitter.addWidget(TabWidget(self))
        self.splitter.addWidget(TransactionWidget(self))
        self.setCentralWidget(self.splitter)
        self.show()


class TabWidget(QWidget):

    def __init__(self, parent):
        super(TabWidget, self).__init__(parent)
        self.layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.chain_tab = QWidget()
        self.peers_tab = QWidget()
        self.keystore_tab = KeystoreWidget(self)

        self.tabs.addTab(self.chain_tab, 'Chain history')
        self.tabs.addTab(self.peers_tab, 'Peers')
        self.tabs.addTab(self.keystore_tab, 'Keystore')

        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)


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
            self.checked_items.remove(item)

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
            item.setText(f'{key_name}: {str(key)}')
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
