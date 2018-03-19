import sys
import threading
import datetime
from functools import partial
from PyQt5.QtWidgets import *
from PyQt5 import QtGui, QtCore
from queue import Queue

lineQueue = Queue()

def gui_loop(gui_send_queue, gui_receive_queue):
    app = QApplication(sys.argv)
    ex = ChainGUI()
    lineEdit = QLineEdit()
    textBrowser = QTextBrowser()
    textBrowser.setStyleSheet("background-color: black")
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
            if(' ' in str(cmd)) == False:
                cmd_html = "<body><div style='color:yellow;'>"
                cmd_html += (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ' : ' + str(cmd))
                cmd_html += "</div'></body>"
                textBrowser.append(cmd_html)
            else:
                cmd_str = str(cmd)
                for ch in ["Block"]:
                    if ch in cmd_str:
                        cmd_str = cmd_str.replace(ch, "<br>" + ch)
                for ch in ['\n']:
                    if ch in cmd_str:
                        cmd_str = cmd_str.replace(ch, "<br>")

                cmd_html = "<body><div style='color:white;'>"
                cmd_html += str(cmd_str)
                cmd_html += "</div'></body>"
                textBrowser.append(str(cmd_html) + '\n')

            textBrowser.moveCursor(QtGui.QTextCursor.End)
            textBrowser.ensureCursorVisible()
            if(cmd == None or cmd == 'exit'):
                return


class ChainGUI(QWidget):
    lineEditHistory = list()
    lineHistoryCounter = len(lineEditHistory)

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
        saveKeyButton = QPushButton("&key <filename>", self)
        saveKeyButton.clicked.connect(partial(self.slot_saveKey, receive_queue))
        saveButton = QPushButton("&Save", self)
        saveButton.clicked.connect(partial(self.slot_save, receive_queue))
        importButton = QPushButton("&Import Key", self)
        importButton.clicked.connect(partial(self.slot_importKey, receive_queue))
        exportButton = QPushButton("E&xport", self)
        exportButton.clicked.connect(partial(self.slot_exportKey, receive_queue))

        helpButton = QPushButton('&Help', self)
        helpButton.clicked.connect(partial(self.slot_help, receive_queue))
        exitButton = QPushButton("&Exit", self)
        exitButton.clicked.connect(partial(self.slot_exit, receive_queue))
        # Keys
        lineEdit.returnPressed.connect(partial(self.slot_lineEdit, receive_queue, lineEdit))

        grid = QGridLayout()
        grid.setSpacing(5)

        grid.addWidget(textBrowser, 0, 0, 1, 10)
        grid.addWidget(lineEdit, 2, 0, 2, 10)

        grid.addWidget(transactionButton, 10, 0)
        grid.addWidget(mineButton, 10, 1)
        grid.addWidget(dumpButton, 10, 2)
        grid.addWidget(peersButton, 10, 3)
        grid.addWidget(saveKeyButton, 10, 4)
        grid.addWidget(saveButton, 10, 5)
        grid.addWidget(importButton, 10, 6)
        grid.addWidget(exportButton, 10, 7)
        grid.addWidget(helpButton, 10, 8)
        grid.addWidget(exitButton, 10, 9)

        self.setLayout(grid)
        self.setGeometry(350, 350, 650, 600)
        self.setWindowTitle('OTH-Chain')
        lineEdit.setFocus()
        self.show()

    # Slots
    def slot_importKey(self, receive_queue):
        #TODO add dialog
        #self.lineHistoryCounter = len(self.lineEditHistory)
        print("import")

    def slot_exportKey(self, receive_queue):
        #TODO add dialog
        print("export")


    def slot_help(self, receive_queue):
        self.lineEditHistory.append("help")
        receive_queue.put("help")

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
        self.lineHistoryCounter = len(self.lineEditHistory)
        receive_queue.put("mine")

    def slot_dump(self, receive_queue):
        self.lineEditHistory.append("dump")
        self.lineHistoryCounter = len(self.lineEditHistory)
        receive_queue.put('dump')

    def slot_peers(self, receive_queue):
        self.lineEditHistory.append("peers")
        self.lineHistoryCounter = len(self.lineEditHistory)
        receive_queue.put("peers")

    def slot_saveKey(self, receive_queue):
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
        self.lineHistoryCounter = len(self.lineEditHistory)

    def slot_save(self, receive_queue):
        self.lineEditHistory.append('save')
        self.lineHistoryCounter = len(self.lineEditHistory)
        receive_queue.put("save")

    def slot_exit(self, receive_queue):
        receive_queue.put('exit')
        self.close()

    def slot_sendTransactionData(self, receive_queue, to, amount):
        self.lineEditHistory.append("transaction " + str(to.text()) + ' ' + str(amount.text()))
        self.lineHistoryCounter = len(self.lineEditHistory)
        #print("transaction " + str(to.text()) + ' ' + str(amount.text()))
        receive_queue.put("transaction " + str(to.text()) + ' ' + str(amount.text()))

    def slot_lineEdit(self, receiveQueue, line):
        self.lineEditHistory.append(str(line.text()))
        self.lineHistoryCounter = len(self.lineEditHistory)
        #print("size: {}, list[0]: {}".format(len(self.lineEditHistory), self.lineEditHistory[0]))
        text = str(line.text())
        line.clear()
        receiveQueue.put(text)

    def keyPressEvent(self, event):
        if(event.key() == QtCore.Qt.Key_Up):
            if(self.lineEditHistory and self.lineHistoryCounter > 0):# and (not self.lineEditHistory[0] == 'gui')):
                lineQueue.put(self.lineEditHistory[self.lineHistoryCounter-1])
                self.lineHistoryCounter -= 1
        elif(event.key() == QtCore.Qt.Key_Down):
            if(self.lineHistoryCounter < len(self.lineEditHistory)):
                lineQueue.put(self.lineEditHistory[self.lineHistoryCounter])
                self.lineHistoryCounter += 1


