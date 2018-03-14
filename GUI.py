import sys
import threading
from functools import partial
from PyQt5.QtWidgets import *


def gui_loop(gui_send_queue, gui_receive_queue):
    app = QApplication(sys.argv)
    ex = ChainGUI()

    textBrowser = QTextBrowser()
    ex.initUI(textBrowser, gui_receive_queue)
    read_thread = threading.Thread(
        target=read_from_queue,
        args=(gui_send_queue, textBrowser,), daemon=True)
    read_thread.start()
    sys.exit(app.exec_())

def read_from_queue(send_queue, textBrowser):
    while True:
        if not send_queue.empty():
            cmd = send_queue.get(block=False)
            textBrowser.append(str(cmd) + '\n')
            if(cmd == None or cmd == 'exit'):
                return

class ChainGUI(QWidget):

    def __init__(self):
        super(ChainGUI, self).__init__()

    def initUI(self, textBrowser, receive_queue):
        #testLabel = QLabel('TestLabel')

        lineEdit = QLineEdit()

        # Buttons
        transactionButton = QPushButton("&Transaction", self)
        transactionButton.clicked.connect(partial(self.slot_transaction, receive_queue))
        mineButton = QPushButton("&Mine", self)
        mineButton.clicked.connect(partial(self.slot_mine, receive_queue))
        dumpButton = QPushButton("&Dump", self)
        dumpButton.clicked.connect(partial(self.slot_dump, receive_queue))
        peersButton = QPushButton("&Peers", self)
        peersButton.clicked.connect(partial(self.slot_peers, receive_queue))
        keyButton = QPushButton("&key <filename>", self)
        keyButton.clicked.connect(partial(self.slot_key, receive_queue))
        saveButton = QPushButton("&Save", self)
        saveButton.clicked.connect(partial(self.slot_save, receive_queue))
        exitButton = QPushButton("&Exit", self)
        exitButton.clicked.connect(partial(self.slot_exit, receive_queue))

        grid = QGridLayout()
        grid.setSpacing(5)

        #grid.addWidget(testLabel, 1, 0)
        grid.addWidget(textBrowser, 0, 0, 1, 7)
        grid.addWidget(lineEdit, 2, 0, 2, 7)

        grid.addWidget(transactionButton, 10, 0)
        grid.addWidget(mineButton, 10, 1)
        grid.addWidget(dumpButton, 10, 2)
        grid.addWidget(peersButton, 10, 3)
        grid.addWidget(keyButton, 10, 4)
        grid.addWidget(saveButton, 10, 5)
        grid.addWidget(exitButton, 10, 6)

        self.setLayout(grid)
#
        self.setGeometry(350, 350, 650, 600)
        self.setWindowTitle('Test Layout')
        self.show()

    # Slots
    def slot_transaction(self, receive_queue):
        # TODO open dialog for writing transaction details
        receive_queue.put("transaction")
        #print("transaction",)
    def slot_mine(self, receive_queue):
        receive_queue.put("mine")
        #print("mine")
    def slot_dump(self, receive_queue):
        receive_queue.put('dump')
        #print("dump")
    def slot_peers(self, receive_queue):
        receive_queue.put("peers")
        #print("peers")
    def slot_key(self, receive_queue):
        receive_queue.put("key")
        #print("key")
    def slot_save(self, receive_queue):
        receive_queue.put("save")
        #print("save")
    def slot_exit(self, receive_queue):
        receive_queue.put('exit')
        self.close()
        #sys.exit(status=None)

