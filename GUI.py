import sys
import threading
import datetime
from functools import partial
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
        self.keystore_tab = QWidget()

        self.keystore_tab_layout = QVBoxLayout()
        self.keystore_tab_key_group = QGroupBox()
        self.keystore_tab_key_group_layout = QVBoxLayout()
        # TODO: Make dedicated classes for the tabs
        for key, value in self.parent().keystore.store.items():
            delete_button = QPushButton('Delete')
            hbox = QHBoxLayout()
            hbox.addWidget(QLabel(key))
            hbox.addWidget(QLabel(str(value)))
            hbox.addWidget(delete_button)
            self.keystore_tab_key_group_layout.addLayout(hbox)
        self.keystore_tab_key_group.setLayout(self.keystore_tab_key_group_layout)
        self.keystore_tab_layout.addWidget(self.keystore_tab_key_group)
        self.keystore_tab.setLayout(self.keystore_tab_layout)


        self.tabs.addTab(self.chain_tab, 'Chain history')
        self.tabs.addTab(self.peers_tab, 'Peers')
        self.tabs.addTab(self.keystore_tab, 'Keystore')

        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)


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

