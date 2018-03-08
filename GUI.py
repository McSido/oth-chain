import sys
from PyQt5.QtWidgets import *


class ChainGUI(QWidget):

    def __init__(self):
        super(ChainGUI, self).__init__()

        self.initUI()

    def initUI(self):
        #testLabel = QLabel('TestLabel')

        lineEdit = QLineEdit()
        textBrowser = QTextBrowser()


        # Buttons
        transactionButton = QPushButton("&Transaction", self)
        transactionButton.clicked.connect(self.slot_transaction)
        mineButton = QPushButton("&Mine", self)
        mineButton.clicked.connect(self.slot_mine)
        dumpButton = QPushButton("&Dump", self)
        dumpButton.clicked.connect(self.slot_dump)
        peersButton = QPushButton("&Peers", self)
        peersButton.clicked.connect(self.slot_peers)
        keyButton = QPushButton("&key <filename>", self)
        keyButton.clicked.connect(self.slot_key)
        saveButton = QPushButton("&Save", self)
        saveButton.clicked.connect(self.slot_save)
        exitButton = QPushButton("&Exit", self)
        exitButton.clicked.connect(self.slot_exit)

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

        self.setGeometry(350, 350, 650, 600)
        self.setWindowTitle('Test Layout')
        self.show()

    # Slots
    def slot_transaction(self):
        print("transaction")
    def slot_mine(self):
        print("mine")
    def slot_dump(self):
        print("dump")
    def slot_peers(self):
        print("peers")
    def slot_key(self):
        print("key")
    def slot_save(self):
        print("save")
    def slot_exit(self):
        sys.exit(status=None)


#app = QApplication(sys.argv)
#ex = ChainGUI()
#sys.exit(app.exec_())
