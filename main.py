from LoLXMPPDebugger import Ui_LoLXMPPDebuggerClass
import sys, json, time, os, io, threading, asyncio, socket
from datetime import datetime
from bs4 import BeautifulSoup
from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt
from PyQt5.QtCore import QObject, QProcess, QCoreApplication, QItemSelection
from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog, QListWidgetItem, QTableWidgetItem, QComboBox, QStyleFactory
from asyncqt import QEventLoop
from ConfigProxy import ConfigProxy
from ChatProxy import ChatProxy

#todo, saving stuff in mitm tab to config, last custom too
#todo, save button in custom tab and list on the left of text edits with submit button
#todo, vairables for mitm, like $timestamp$ or some python code executing

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
        self.mitmTableWidget.setColumnWidth(0, 104)
        self.mitmTableWidget.setColumnWidth(1, 73)
        self.mitmTableWidget.setColumnWidth(2, 262)
        self.tabWidget.setMovable(True)

        palette = self.incomingList.palette()
        listStyle = f"QListWidget::item {{ border-bottom: 1px solid {palette.midlight().color().name()}; height: {self.incomingList.font().pointSizeF()*1.75}px; }} QListWidget::item:selected {{ background-color: {palette.highlight().color().name()}; color: {palette.highlightedText().color().name()}; }}"
        self.incomingList.setStyleSheet(listStyle)
        self.outgoingList.setStyleSheet(listStyle)

        self.LoadConfig()

        self.xmpp_objects = {"outgoingList": self.outgoingList,
                        "incomingList": self.incomingList,
                        "mitmTableWidget": self.mitmTableWidget}


    def find_free_port(self):
        with socket.socket() as s:
            s.bind(('', 0))
            return s.getsockname()[1]


    #region QT slots

    def pretty_xml(self, text):
        #todo, find a better lib
        return text
        # bs = BeautifulSoup(text, features="xml")
        # pretty = bs.prettify()
        # if '<?xml version="1.0" encoding="UTF-8"?>' not in text:
        #     pretty = pretty.replace('<?xml version="1.0" encoding="utf-8"?>\n', '')
        # else:
        #     pretty = pretty.replace('<?xml version="1.0" encoding="utf-8"?>\n',
        #                             '<?xml version="1.0" encoding="UTF-8"?>\n')
        # if not pretty:
        #     pretty = text
        # return pretty

    @pyqtSlot(QTableWidgetItem)
    def on_mitmTableWidget_itemChanged(self, item: QTableWidgetItem):
        if item.row() != self.mitmSelectedRow:
            return
        if item.column() == 2: # Contains
            if not self.mitmContainsTextEdit.hasFocus():
                self.mitmContainsTextEdit.setText(item.text())
        elif item.column() == 3:
            if not self.mitmChangeTextEdit.hasFocus():
                self.mitmChangeTextEdit.setText(item.text())

    mitmSelectedRow = 0

    @pyqtSlot()
    def on_mitmTableWidget_itemSelectionChanged(self):
        model = self.mitmTableWidget.selectionModel()
        if len(model.selectedRows()) == 0 or model.selectedRows() == 0:
            return
        self.mitmSelectedRow = model.selectedRows()[0].row()
        containsCell = self.mitmTableWidget.item(self.mitmSelectedRow, 2)
        self.mitmContainsTextEdit.setText(containsCell.text())
        changeCell = self.mitmTableWidget.item(self.mitmSelectedRow, 3)
        self.mitmChangeTextEdit.setText(changeCell.text())

    @pyqtSlot()
    def on_mitmContainsTextEdit_textChanged(self):
        if self.mitmSelectedRow != None:
            self.mitmTableWidget.item(self.mitmSelectedRow, 2).setText(self.mitmContainsTextEdit.toPlainText())

    @pyqtSlot()
    def on_mitmChangeTextEdit_textChanged(self):
        if self.mitmSelectedRow != None:
            self.mitmTableWidget.item(self.mitmSelectedRow, 3).setText(self.mitmChangeTextEdit.toPlainText())

    @pyqtSlot()
    def on_mitmAddButton_clicked(self):
        rowCount = self.mitmTableWidget.rowCount()
        columnCount = self.mitmTableWidget.columnCount()
        self.mitmTableWidget.insertRow(rowCount)

        combo = QComboBox()
        combo.addItem("Request")
        combo.addItem("Response")
        self.mitmTableWidget.setCellWidget(rowCount, 0, combo)

        combo = QComboBox()
        combo.addItem("XMPP")
        combo.addItem("RTMP")
        self.mitmTableWidget.setCellWidget(rowCount, 1, combo)

        item = QTableWidgetItem("")
        #item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        item.setCheckState(Qt.Unchecked)
        self.mitmTableWidget.setItem(rowCount, 2, item)

        self.mitmTableWidget.setItem(rowCount, 3, QTableWidgetItem(""))

        for row in range(self.mitmTableWidget.rowCount()):
            print(self.mitmTableWidget.cellWidget(row, 0).currentText(), self.mitmTableWidget.cellWidget(row, 1).currentText(),
                  self.mitmTableWidget.item(row, 2).checkState(),self.mitmTableWidget.item(row, 2).text() ,self.mitmTableWidget.item(row, 3).text())
            # if self.mitmTableWidget.cellWidget(row, 0).currentText() == "Request":
            #     if self.mitmTableWidget.cellWidget(row, 1).currentText() == "XMPP":
            #         print(row, self.mitmTableWidget.item(row, 2).checkState(), self.mitmTableWidget.item(row, 2).text())

    @pyqtSlot()
    def on_xmppCustomPushButton_clicked(self):
        serv = ChatProxy.connectedServer
        if serv:
            text = self.xmppCustomTextEdit.toPlainText()
            serv.write(text.encode("UTF-8"))

            item = QListWidgetItem()
            item.setForeground(Qt.blue)
            item.setText(text)
            self.incomingList.addItem(item)

    @pyqtSlot(QListWidgetItem)
    def on_incomingList_itemClicked(self, item: QListWidgetItem):
        self.viewTextEdit.setText(self.pretty_xml(item.text()))

    @pyqtSlot(QListWidgetItem)
    def on_outgoingList_itemClicked(self, item: QListWidgetItem):
        self.viewTextEdit.setText(self.pretty_xml(item.text()))

    @pyqtSlot()
    def on_pushButton_LaunchLeague_clicked(self):

        self.port = self.find_free_port()
        self.chatPort = self.find_free_port()

        configProxy = ConfigProxy(self.chatPort, self.xmpp_objects)
        loop = asyncio.get_event_loop()
        loop.create_task(configProxy.run_server("127.0.0.1", self.port))

        with open("C:/ProgramData/Riot Games/RiotClientInstalls.json", 'r') as file:
            clientPath = json.load(file)["rc_default"]
            league = QProcess(None)
            args = ['--allow-multiple-clients', f'--launch-product=league_of_legends', '--launch-patchline=live', f'--client-config-url=http://127.0.0.1:{self.port}']
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

    @pyqtSlot(bool)
    def on_actionStay_on_top_triggered(self, checked):
        if checked:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.show()
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
            self.show()

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

