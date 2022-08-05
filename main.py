from LoLXMPPDebugger import Ui_LoLXMPPDebuggerClass
import sys, json, time, os, io, threading, asyncio, socket
from datetime import datetime
from bs4 import BeautifulSoup
from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt
from PyQt5.QtCore import QObject, QProcess, QCoreApplication
from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog, QListWidgetItem,QTableWidgetItem
from asyncqt import QEventLoop
from ConfigProxy import ConfigProxy

class MainWindow(QtWidgets.QMainWindow, Ui_LoLXMPPDebuggerClass):

    counter = 0
    saveDir = QCoreApplication.applicationDirPath()
    startTime = time.time()
    configFileName = "config.json"

    port = 0
    chatPort = 0

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent=parent)
        self.setupUi(self)

        self.incomingScrollToBottom.setChecked(True)
        self.outgoingScrollToBottom.setChecked(True)

        self.LoadConfig()

        self.port = self.find_free_port()
        self.chatPort = self.find_free_port()

        xmpp_objects = {"outgoingList": self.outgoingList,
                        "incomingList": self.incomingList}

        configProxy = ConfigProxy(self.chatPort, xmpp_objects)
        loop = asyncio.get_event_loop()
        loop.create_task(configProxy.run_server("127.0.0.1", self.port))

    def find_free_port(self):
        with socket.socket() as s:
            s.bind(('', 0))
            return s.getsockname()[1]


    #region QT slots

    @pyqtSlot()
    def on_mitmTestbutton_clicked(self):
        rowCount = self.tableWidget.rowCount()
        columnCount = self.tableWidget.columnCount()
        item = QTableWidgetItem()
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Unchecked)
        self.tableWidget.insertRow(rowCount)
        self.tableWidget.setItem(rowCount-1, columnCount, item)

    @pyqtSlot(QListWidgetItem)
    def on_incomingList_itemClicked(self, item: QListWidgetItem):
        bs = BeautifulSoup(item.text(), features="lxml-xml")
        pretty_xml = bs.prettify()
        self.viewTextEdit.setText(pretty_xml)

    @pyqtSlot(QListWidgetItem)
    def on_outgoingList_itemClicked(self, item: QListWidgetItem):
        bs = BeautifulSoup(item.text(), features="lxml-xml")
        pretty_xml = bs.prettify()
        self.viewTextEdit.setHtml(pretty_xml)


    @pyqtSlot()
    def on_pushButton_LaunchLeague_clicked(self):
        with open("C:/ProgramData/Riot Games/RiotClientInstalls.json", 'r') as file:
            clientPath = json.load(file)["rc_default"]
            league = QProcess(None)
            args = [f'--launch-product=league_of_legends', '--launch-patchline=live', f'--client-config-url=http://127.0.0.1:{self.port}']
            league.startDetached(clientPath, args)

    @pyqtSlot()
    def on_actionExit_triggered(self):
        QApplication.quit()

    @pyqtSlot()
    def on_actionAbout_triggered(self):
        QMessageBox.information(self, "About LoLXMPPDebugger",
                                 "Simple XMPP debugger tool for League of Legends client <br> <a href='https://www.github.com/KebsCS'>GitHub</a>")

    @pyqtSlot()
    def on_actionChoose_directory_triggered(self):
        self.saveDir = QFileDialog.getExistingDirectory(self, "Select save directory", self.saveDir)
        if self.saveDir[-1] != "/":
            self.saveDir += "/"
        self.SaveConfig()

    @pyqtSlot()
    def on_pushButton_Test_clicked(self):
        self.incomingList.addItem("<?xml version='1.0'?><stream:stream xmlns='jabber:client' xmlns:stream='http://etherx.jabber.org/streams' id='152424151' from='eu1.pvp.net' version='1.0'>")
        self.outgoingList.addItem("<?xml version='1.0'?><stream:stream xmlns='jabber:client' xmlns:stream='http://etherx.jabber.org/streams' id='152424151' from='eu1.pvp.net' version='1.0'>")
        self.counter += 1

    @pyqtSlot()
    def on_outgoingButtonClear_clicked(self):
        self.outgoingList.clear()

    @pyqtSlot()
    def on_incomingButtonClear_clicked(self):
        self.incomingList.clear()

    def scroll_func_outgoing(self):
        self.outgoingList.scrollToBottom()

    @pyqtSlot(bool)
    def on_outgoingScrollToBottom_toggled(self, checked):
        if checked:
            self.outgoingList.model().rowsInserted.connect(self.scroll_func_outgoing)
        else:
            self.outgoingList.model().rowsInserted.disconnect(self.scroll_func_outgoing)

    def scroll_func_incoming(self):
        self.incomingList.scrollToBottom()
    @pyqtSlot(bool)
    def on_incomingScrollToBottom_toggled(self, checked):
        if checked:
            self.incomingList.model().rowsInserted.connect(self.scroll_func_incoming)
        else:
            self.incomingList.model().rowsInserted.disconnect(self.scroll_func_incoming)

    @pyqtSlot()
    def on_actionSaveOutgoing_triggered(self):
        with open(f'{self.saveDir}outgoing.txt', 'a+') as file:
            file.write(f"<----- {datetime.fromtimestamp(self.startTime)} ----->\n")
            for item in range(self.outgoingList.count()):
                file.write(str(self.outgoingList.item(item).text())+ "\n")
            file.write("\n\n")

    @pyqtSlot()
    def on_actionSaveIncoming_triggered(self):
        with open(f'{self.saveDir}incoming.txt', 'a+') as file:
            file.write(f"<----- {datetime.fromtimestamp(self.startTime)} ----->\n")
            for item in range(self.incomingList.count()):
                file.write(str(self.incomingList.item(item).text()) + "\n")
            file.write("\n\n")

    @pyqtSlot()
    def on_actionSaveBoth_triggered(self):
        self.on_actionSaveOutgoing_triggered()
        self.on_actionSaveIncoming_triggered()

    #endregion

    #region Config
    def LoadConfig(self):
        mode = 'r' if os.path.exists(self.configFileName) else 'w'
        with open(self.configFileName, mode) as configFile:
            try:
                data = json.load(configFile)

                self.saveDir = data["saveDir"]

            except (json.decoder.JSONDecodeError, KeyError, io.UnsupportedOperation):
                pass

    def SaveConfig(self):
        with open(self.configFileName, 'r+') as configFile:
            data = json.load(configFile) if os.stat(self.configFileName).st_size != 0 else {}

            data['saveDir'] = self.saveDir

            configFile.seek(0)
            json.dump(data, configFile, indent=4)
            configFile.truncate()

    #endregion

if __name__ == "__main__":
    # print silent QT errors
    sys._excepthook = sys.excepthook
    def exception_hook(exctype, value, traceback):
        #print(exctype, value, traceback)
        sys._excepthook(exctype, value, traceback)
        sys.exit(1)
    sys.excepthook = exception_hook

    app = QtWidgets.QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    w = MainWindow()
    w.show()
    with loop:
        loop.run_forever()

