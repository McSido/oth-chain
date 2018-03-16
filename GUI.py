import sys
import threading
import datetime
from functools import partial
from PyQt5.QtWidgets import *
from PyQt5 import QtGui, QtCore
from PyQt5.QtGui import QKeyEvent, QKeySequence
from queue import Queue

lineQueue = Queue()

def gui_loop(gui_send_queue, gui_receive_queue):
    app = QApplication(sys.argv)
    ex = ChainGUI()
    lineEdit = QLineEdit()
    textBrowser = QTextBrowser()
    ex.initUI(lineEdit, textBrowser, gui_receive_queue)
    read_thread = threading.Thread(
        target=read_from_queue,
        args=(gui_send_queue, textBrowser,), daemon=True)
    read_thread.start()

    lineEditThread = threading.Thread(
        target=writeToLineEdit,
        args=(lineQueue, lineEdit), daemon=True)
    lineEditThread.start()

    sys.exit(app.exec_())

def writeToLineEdit(lineQueue, line):
    while True:
        if (not lineQueue.empty()):
            line.setText(str(lineQueue.get()))


def read_from_queue(send_queue, textBrowser):
    while True:
        if not send_queue.empty():
            cmd = send_queue.get(block=False)
            textBrowser.append(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ' : ' + str(cmd) + '\n')
            textBrowser.moveCursor(QtGui.QTextCursor.End)
            textBrowser.ensureCursorVisible()
            if(cmd == None or cmd == 'exit'):
                return

class ChainGUI(QWidget):
    lineEditHistory = list()

    def __init__(self):
        super(ChainGUI, self).__init__()

    def initUI(self, lineEdit, textBrowser, receive_queue):

        #lineEdit = QLineEdit()
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
        # Keys
        lineEdit.returnPressed.connect(partial(self.slot_lineEdit, receive_queue, lineEdit))

        grid = QGridLayout()
        grid.setSpacing(5)

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
        self.setGeometry(350, 350, 650, 600)
        self.setWindowTitle('OTH-Chain')
        lineEdit.setFocus()
        self.show()

    # Slots
    def slot_transaction(self, receive_queue):
        d = QDialog()
        d.setWindowTitle("Transaction Details")
        line1 = QLineEdit(d)
        line1.setPlaceholderText("to")
        line2 = QLineEdit(d)
        line2.setPlaceholderText("Amount")
        cancelButton = QPushButton("&Cancel", d)
        okButton = QPushButton("&Ok", d)
        line1.move(100, 50)
        line2.move(100,100)
        okButton.move(50, 150)
        cancelButton.move(150, 150)
        okButton.clicked.connect(partial(self.slot_sendTransactionData, receive_queue, line1, line2))
        okButton.clicked.connect(d.close)
        cancelButton.clicked.connect(d.close)
        d.exec()

    def slot_mine(self, receive_queue):
        self.lineEditHistory.append("mine")
        receive_queue.put("mine")

    def slot_dump(self, receive_queue):
        self.lineEditHistory.append("dump")
        receive_queue.put('dump')

    def slot_peers(self, receive_queue):
        self.lineEditHistory.append("peers")
        receive_queue.put("peers")

    def slot_key(self, receive_queue):
        #fileName = QFileDialog.getOpenFileName(self, 'Open File')
        d = QDialog()
        d.setWindowTitle("Enter filename without extensions")
        line = QLineEdit(d)
        line.setPlaceholderText("filename for key")
        cancelButton = QPushButton("&Cancel", d)
        okButton = QPushButton("&Ok", d)
        line.move(20, 50)
        okButton.move(20, 100)
        cancelButton.move(100, 100)
        okButton.clicked.connect(d.close)
        cancelButton.clicked.connect(d.close)
        d.exec()
        receive_queue.put("key " + str(line.text()))
        self.lineEditHistory.append("key " + str(line.text()))

    def slot_save(self, receive_queue):
        self.lineEditHistory.append('save')
        receive_queue.put("save")

    def slot_exit(self, receive_queue):
        receive_queue.put('exit')
        self.close()

    def slot_sendTransactionData(self, receive_queue, to, amount):
        self.lineEditHistory.append("transaction " + str(to.text()) + ' ' + str(amount.text()))
        #print("transaction " + str(to.text()) + ' ' + str(amount.text()))
        receive_queue.put("transaction " + str(to.text()) + ' ' + str(amount.text()))

    def slot_lineEdit(self, receiveQueue, line):
        self.lineEditHistory.append(str(line.text()))
        text = str(line.text())
        line.clear()
        receiveQueue.put(text)

    def keyPressEvent(self, event):
        if(event.key() == QtCore.Qt.Key_Up):
            if(self.lineEditHistory and (not self.lineEditHistory[-1] == 'gui')):
                lineQueue.put(self.lineEditHistory[-1])
                self.lineEditHistory.pop(-1)


