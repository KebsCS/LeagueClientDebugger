from LoLXMPPDebugger import Ui_LoLXMPPDebuggerClass
import sys, json, time, os, io, threading, asyncio, socket
from datetime import datetime
from bs4 import BeautifulSoup
from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt
from PyQt5.QtCore import QObject, QProcess, QCoreApplication, QItemSelection
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QListWidgetItem, QTableWidgetItem, QComboBox, QStyleFactory
from qasync import QEventLoop, QApplication
from ConfigProxy import ConfigProxy
from ChatProxy import ChatProxy
from HttpProxy import HttpProxy
from LcdsProxy import LcdsProxy
from SystemYaml import SystemYaml
from ProxyServers import ProxyServers


# import logging
# logging.getLogger().setLevel(logging.WARNING)
#
# logger = logging.getLogger(__name__)
# logger.handlers = []  # Remove all handlers
# logger.setLevel(logging.NOTSET)


os.environ['no_proxy'] = '*'

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

        # todo maybe find free ports in ProxyServers.py
        ProxyServers.ledge_port = self.find_free_port()
        ProxyServers.entitlements_port = self.find_free_port()
        ProxyServers.player_platform_port = self.find_free_port()
        ProxyServers.playerpreferences_port = self.find_free_port()
        ProxyServers.geo_port = self.find_free_port()
        ProxyServers.email_port = self.find_free_port()
        ProxyServers.payments_port = self.find_free_port()

        SystemYaml().read()
        SystemYaml().edit()


    def find_free_port(self):
        with socket.socket() as s:
            s.bind(('', 0))
            return s.getsockname()[1]


    #region QT slots

    def closeEvent(self, event):
       self.SaveConfig()
       event.accept()

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

        # for row in range(self.mitmTableWidget.rowCount()):
        #     print(self.mitmTableWidget.cellWidget(row, 0).currentText(), self.mitmTableWidget.cellWidget(row, 1).currentText(),
        #           self.mitmTableWidget.item(row, 2).checkState(),self.mitmTableWidget.item(row, 2).text() ,self.mitmTableWidget.item(row, 3).text())
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

    @pyqtSlot()
    def on_rtmpCustomPushButton_clicked(self):
        print('asd')
        serv = LcdsProxy.connectedServer
        if serv:
            text = self.rtmpCustomTextEdit.toPlainText().encode().decode('unicode_escape').encode("raw_unicode_escape")
            print('asd2', text)
            serv.write(text)


    @pyqtSlot(QListWidgetItem)
    def on_incomingList_itemClicked(self, item: QListWidgetItem):
        self.viewTextEdit.setText(self.pretty_xml(item.text()))

    @pyqtSlot(QListWidgetItem)
    def on_outgoingList_itemClicked(self, item: QListWidgetItem):
        self.viewTextEdit.setText(self.pretty_xml(item.text()))

    def start_proxy(self, original_host, port=None):
        httpProxy = HttpProxy()
        loop = asyncio.get_event_loop()
        if port is None:
            port = self.find_free_port()
        loop.create_task(httpProxy.run_server("127.0.0.1", port, original_host))

    @pyqtSlot()
    def on_pushButton_LaunchLeague_clicked(self):

        serv = "EUW"

        ProxyServers.client_config_port = self.find_free_port()
        ProxyServers.chat_port = self.find_free_port()
        configProxy = ConfigProxy(ProxyServers.chat_port, self.xmpp_objects)
        loop = asyncio.get_event_loop()
        loop.create_task(configProxy.run_server("127.0.0.1", ProxyServers.client_config_port, SystemYaml.client_config[serv]))

        # todo get realhost from yaml
        lcdsProxy = LcdsProxy()
        loop = asyncio.get_event_loop()
        lcds = SystemYaml.lcds[serv]
        loop.create_task(
            lcdsProxy.run_from_client("127.0.0.1", lcds.split(":")[1], lcds.split(":")[0], lcds.split(":")[1]))

        # loop = asyncio.get_event_loop()
        # rtmpProxy = RtmpProxy()
        # loop.create_task(rtmpProxy.create("127.0.0.1", SystemYaml.lcds[serv].split(":")[1]))

        self.start_proxy(SystemYaml.ledge[serv], ProxyServers.ledge_port)
        self.start_proxy(SystemYaml.entitlements[serv], ProxyServers.entitlements_port)
        self.start_proxy(SystemYaml.player_platform[serv], ProxyServers.player_platform_port)
        self.start_proxy(SystemYaml.email[serv], ProxyServers.email_port)
        self.start_proxy(SystemYaml.payments[serv], ProxyServers.payments_port)

        #todo maybe find free ports in ProxyServers.py

        self.start_proxy("https://playerpreferences.riotgames.com", ProxyServers.playerpreferences_port) #todo could get url from config proxy
        self.start_proxy("https://riot-geo.pas.si.riotgames.com", ProxyServers.geo_port) #todo could get url from config proxy

        ProxyServers.auth_port = self.find_free_port()
        self.start_proxy("https://auth.riotgames.com", ProxyServers.auth_port)  # todo could get url from config proxy

        ProxyServers.authenticator_port = self.find_free_port()
        self.start_proxy("https://authenticate.riotgames.com", ProxyServers.authenticator_port)  # todo could get url from config proxy

        ProxyServers.accounts_port = self.find_free_port()
        self.start_proxy("https://api.account.riotgames.com", ProxyServers.accounts_port)  # todo could get url from config proxy

        ProxyServers.publishing_content_port = self.find_free_port()
        self.start_proxy("https://content.publishing.riotgames.com",
                         ProxyServers.publishing_content_port)  # todo could get url from config proxy

        ProxyServers.scd_port = self.find_free_port()
        self.start_proxy("https://scd.riotcdn.net", ProxyServers.scd_port)  # todo could get url from config proxy

        ProxyServers.lifecycle_port = self.find_free_port()
        self.start_proxy("https://player-lifecycle-euc.publishing.riotgames.com", ProxyServers.lifecycle_port)  # todo could get url from config proxy also there are different servers

        ProxyServers.loyalty_port = self.find_free_port()
        self.start_proxy("https://eu.lers.loyalty.riotgames.com", ProxyServers.loyalty_port )

        ProxyServers.pcbs_loyalty_port = self.find_free_port()
        self.start_proxy("https://pcbs.loyalty.riotgames.com", ProxyServers.pcbs_loyalty_port)

        with open("C:/ProgramData/Riot Games/RiotClientInstalls.json", 'r') as file:
            clientPath = json.load(file)["rc_default"]
            league = QProcess(None)
            args = ['--allow-multiple-clients', f'--launch-product=league_of_legends', '--launch-patchline=live', f'--client-config-url=http://127.0.0.1:{ProxyServers.client_config_port}']
            league.startDetached(clientPath, args)

    @pyqtSlot()
    def on_actionExit_triggered(self):
        QApplication.closeAllWindows()

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
        with open(f'{self.saveDir}fullconfig.txt', 'w') as file:
            json.dump(ConfigProxy.full_config, file)

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

    @pyqtSlot()
    def on_httpsFiddlerButton_clicked(self):
        ProxyServers.fiddler_proxies = {
            'http': self.httpsFiddlerHost.toPlainText()+":"+self.httpsFiddlerPort.toPlainText(),
            'https': self.httpsFiddlerHost.toPlainText()+":"+self.httpsFiddlerPort.toPlainText()
        }
        print(ProxyServers.fiddler_proxies)

    #endregion

    #region Config
    def LoadConfig(self):
        mode = 'r' if os.path.exists(self.configFileName) else 'w'
        with open(self.configFileName, mode) as configFile:
            try:
                data = json.load(configFile)

                if "saveDir" in data:
                    self.saveDir = data["saveDir"]
                if "mitm" in data:
                    for rule in data["mitm"]:
                        self.on_mitmAddButton_clicked()
                        row = self.mitmTableWidget.rowCount()-1
                        self.mitmTableWidget.cellWidget(row, 0).setCurrentText(rule["type"])
                        self.mitmTableWidget.cellWidget(row, 1).setCurrentText(rule["protocol"])
                        self.mitmTableWidget.item(row, 2).setCheckState(rule["enabled"])
                        self.mitmTableWidget.item(row, 2).setText(rule["contains"])
                        self.mitmTableWidget.item(row, 3).setText(rule["changeto"])

                if "custom_xmpp" in data:
                    self.xmppCustomTextEdit.setText(data["custom_xmpp"])

                if "fiddler_host" in data:
                    self.httpsFiddlerHost.setText(data["fiddler_host"])
                else:
                    self.httpsFiddlerHost.setText("http://127.0.0.1")

                if "fiddler_port" in data:
                    self.httpsFiddlerPort.setText(data["fiddler_port"])
                else:
                    self.httpsFiddlerPort.setText("8888")

                ProxyServers.fiddler_proxies = {
                    'http': self.httpsFiddlerHost.toPlainText() + ":" + self.httpsFiddlerPort.toPlainText(),
                    'https': self.httpsFiddlerHost.toPlainText() + ":" + self.httpsFiddlerPort.toPlainText()
                }

            except (json.decoder.JSONDecodeError, KeyError, io.UnsupportedOperation):
                pass

    def SaveConfig(self):
        with open(self.configFileName, 'r+') as configFile:
            data = json.load(configFile) if os.stat(self.configFileName).st_size != 0 else {}

            data['saveDir'] = self.saveDir
            data["mitm"] = []
            for row in range(self.mitmTableWidget.rowCount()):
                rule = {"type": self.mitmTableWidget.cellWidget(row, 0).currentText(),
                        "protocol": self.mitmTableWidget.cellWidget(row, 1).currentText(),
                        "enabled": self.mitmTableWidget.item(row, 2).checkState(),
                        "contains": self.mitmTableWidget.item(row, 2).text(),
                        "changeto": self.mitmTableWidget.item(row, 3).text()}
                data["mitm"].append(rule)

            data["custom_xmpp"] = self.xmppCustomTextEdit.toPlainText()

            data["fiddler_host"] = self.httpsFiddlerHost.toPlainText()
            data["fiddler_port"] = self.httpsFiddlerPort.toPlainText()

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

    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    w = MainWindow()
    w.show()
    with loop:
        loop.run_forever()

