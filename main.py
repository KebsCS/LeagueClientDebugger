from LoLXMPPDebugger import Ui_LoLXMPPDebuggerClass
import sys, json, time, os, io, asyncio, socket, pymem
from datetime import datetime
from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt, QEvent
from PyQt5.QtCore import QObject, QProcess, QCoreApplication, QItemSelection
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QListWidgetItem, QTableWidgetItem, QComboBox, QStyleFactory, QToolBar, QAction
from PyQt5.QtGui import QColor
from qasync import QEventLoop, QApplication
from ConfigProxy import ConfigProxy
from ChatProxy import ChatProxy
from HttpProxy import HttpProxy
from RtmpProxy import RtmpProxy
from SystemYaml import SystemYaml
from ProxyServers import ProxyServers
from UiObjects import UiObjects
from RmsProxy import RmsProxy

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

        self.mitmTableWidget.setColumnWidth(0, 104)
        self.mitmTableWidget.setColumnWidth(1, 73)
        self.mitmTableWidget.setColumnWidth(2, 262)
        self.tabWidget.setMovable(True)

        # self.httpsInjectButton = QtWidgets.QPushButton(self.tab_https)
        # self.httpsInjectButton.setObjectName("httpsInjectButton")
        # self.horizontalLayout_3.addWidget(self.httpsInjectButton)
        # self.httpsInjectButton.setText("Inject")
        # self.httpsInjectButton.clicked.connect(self.Inject)

        #palette = self.xmppList.palette()
        #listStyle = f"QListWidget::item {{ border-bottom: 1px solid {palette.midlight().color().name()}; height: {self.xmppList.font().pointSizeF()*1.75}px; }} QListWidget::item:selected {{ background-color: {palette.highlight().color().name()}; color: {palette.highlightedText().color().name()}; }}"

        # self.xmppList.setStyleSheet(listStyle)
        UiObjects.xmppList = self.xmppList
        self.xmppList.currentItemChanged.connect(self.on_xmppList_itemClicked)
        self.xmppScrollToBottom.setChecked(True)

        #self.rtmpList.setStyleSheet(listStyle)
        UiObjects.rtmpList = self.rtmpList
        self.rtmpList.currentItemChanged.connect(self.on_rtmpList_itemClicked)
        self.rtmpScrollToBottom.setChecked(True)

        self.xmppTextSearch.installEventFilter(self)
        self.rtmpTextSearch.installEventFilter(self)
        self.rmsTextSearch.installEventFilter(self)
        self.httpsTextSearch.installEventFilter(self)

        self.tab_xmpp.installEventFilter(self)
        self.tab_rtmp.installEventFilter(self)
        self.tab_rms.installEventFilter(self)
        self.tab_https.installEventFilter(self)


        #self.rmsList.setStyleSheet(listStyle)
        UiObjects.rmsList = self.rmsList
        self.rmsList.currentItemChanged.connect(self.on_rmsList_itemClicked)
        self.rmsScrollToBottom.setChecked(True)

        UiObjects.httpsList = self.httpsList
        self.httpsList.currentItemChanged.connect(self.on_httpsList_itemClicked)
        self.httpsScrollToBottom.setChecked(True)

        SystemYaml().read()

        self.allRegions.addItems(SystemYaml.regions)

        self.LoadConfig()

        UiObjects.mitmTableWidget = self.mitmTableWidget

        # todo maybe find free ports in ProxyServers.py
        ProxyServers.ledge_port = self.find_free_port()
        ProxyServers.entitlements_port = self.find_free_port()
        ProxyServers.player_platform_port = self.find_free_port()
        ProxyServers.playerpreferences_port = self.find_free_port()
        ProxyServers.geo_port = self.find_free_port()
        ProxyServers.email_port = self.find_free_port()
        ProxyServers.payments_port = self.find_free_port()

        SystemYaml().edit()

        self.proxies_started = False

    def eventFilter(self, obj, event):
        current_tab_index = self.tabWidget.currentIndex()
        if event.type() == QEvent.KeyPress and obj is self.xmppTextSearch:
            if event.key() == Qt.Key_Return and self.xmppTextSearch.hasFocus():
                self.on_xmppButtonSearch_clicked()
                return True
        elif event.type() == QEvent.KeyPress and obj is self.rtmpTextSearch:
            if event.key() == Qt.Key_Return and self.rtmpTextSearch.hasFocus():
                self.on_rtmpButtonSearch_clicked()
                return True
        elif event.type() == QEvent.KeyPress and obj is self.rmsTextSearch:
            if event.key() == Qt.Key_Return and self.rmsTextSearch.hasFocus():
                self.on_rmsButtonSearch_clicked()
                return True
        elif event.type() == QEvent.KeyPress and obj is self.httpsTextSearch:
            if event.key() == Qt.Key_Return and self.httpsTextSearch.hasFocus():
                self.on_httpsButtonSearch_clicked()
                return True

        elif event.type() == QEvent.KeyPress and current_tab_index == self.tabWidget.indexOf(self.tab_xmpp):
            if event.key() == Qt.Key_F and event.modifiers() == Qt.ControlModifier:
                self.xmppTextSearch.setFocus()
                return True
        elif event.type() == QEvent.KeyPress and current_tab_index == self.tabWidget.indexOf(self.tab_rtmp):
            if event.key() == Qt.Key_F and event.modifiers() == Qt.ControlModifier:
                self.rtmpTextSearch.setFocus()
                return True
        elif event.type() == QEvent.KeyPress and current_tab_index == self.tabWidget.indexOf(self.tab_rms):
            if event.key() == Qt.Key_F and event.modifiers() == Qt.ControlModifier:
                self.rmsTextSearch.setFocus()
                return True
        elif event.type() == QEvent.KeyPress and current_tab_index == self.tabWidget.indexOf(self.tab_https):
            if event.key() == Qt.Key_F and event.modifiers() == Qt.ControlModifier:
                self.httpsTextSearch.setFocus()
                return True
        return False

    def Inject(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            dll_path = os.path.join(current_dir, "LeagueHooker.dll")

            # Check if the DLL file exists
            if not os.path.exists(dll_path):
                print("DLL file not found:", dll_path)
                return
            file = pymem.Pymem("LeagueClient.exe")
            pymem.process.inject_dll(file.process_handle, bytes(dll_path, "UTF-8"))
        except Exception as e:
            print("Inject failed ", e)

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
        pass #todo
        # serv = ChatProxy.connectedServer
        # if serv:
        #     text = self.xmppCustomTextEdit.toPlainText()
        #     serv.write(text.encode("UTF-8"))
        #
        #     item = QListWidgetItem()
        #     item.setForeground(Qt.blue)
        #     item.setText(text)
        #     self.incomingList.addItem(item)

    @pyqtSlot()
    def on_rtmpCustomPushButton_clicked(self):
        print('asd')
        # serv = RtmpProxy.connectedServer
        # if serv:
        #     text = self.rtmpCustomTextEdit.toPlainText().encode().decode('unicode_escape').encode("raw_unicode_escape")
        #     print('asd2', text)
        #     serv.write(text)


    @pyqtSlot(QListWidgetItem)
    def on_xmppList_itemClicked(self, item: QListWidgetItem):
        if len(self.xmppList.selectedItems()) == 0:
            return
        item = self.xmppList.selectedItems()[0]
        self.xmppView.setText(item.data(256))


    @pyqtSlot(QListWidgetItem)
    def on_rtmpList_itemClicked(self):
        # todo, is called twice, from itemClicked and selectionchanged
        # workaround because selectionchanged works only after it has been selected at least once
        if len(self.rtmpList.selectedItems()) == 0:
            return
        item = self.rtmpList.selectedItems()[0]
        if item.data(257):
            self.rtmpView.setText(item.data(257))
            return
        pretty_item = json.dumps(json.loads(item.data(256)), indent=4)
        self.rtmpView.setText(pretty_item)

    @pyqtSlot(QListWidgetItem)
    def on_httpsList_itemClicked(self):
        if len(self.httpsList.selectedItems()) == 0:
            return
        item = self.httpsList.selectedItems()[0]
        self.httpsRequest.setText(item.data(256))
        self.httpsResponse.setText(item.data(257))

    @pyqtSlot()
    def on_xmppButtonSearch_clicked(self):
        search_text = self.xmppTextSearch.toPlainText().strip().lower()
        for index in range(self.xmppList.count()):
            item = self.xmppList.item(index)
            text = item.data(256) if item.data(256) else " "
            if search_text in text.lower():
                item.setBackground(Qt.yellow)
            else:
                item.setBackground(Qt.transparent)

    @pyqtSlot()
    def on_rtmpButtonSearch_clicked(self):
        search_text = self.rtmpTextSearch.toPlainText().strip().lower()
        for index in range(self.rtmpList.count()):
            item = self.rtmpList.item(index)
            text = item.data(256) if item.data(256) else item.data(257)
            if search_text in text.lower():
                item.setBackground(Qt.yellow)
            else:
                item.setBackground(Qt.transparent)

    @pyqtSlot()
    def on_rmsButtonSearch_clicked(self):
        search_text = self.rmsTextSearch.toPlainText().strip().lower()
        for index in range(self.rmsList.count()):
            item = self.rmsList.item(index)
            text = item.data(256) if item.data(256) else item.data(257)
            if search_text in text.lower():
                item.setBackground(Qt.yellow)
            else:
                item.setBackground(Qt.transparent)

    @pyqtSlot()
    def on_httpsButtonSearch_clicked(self):
        search_text = self.httpsTextSearch.toPlainText().strip().lower()
        for index in range(self.httpsList.count()):
            item = self.httpsList.item(index)
            text = item.data(256) + " " + item.data(257)
            if search_text in text.lower():
                item.setBackground(Qt.yellow)
            else:
                item.setBackground(Qt.transparent)

    @pyqtSlot(QListWidgetItem)
    def on_rmsList_itemClicked(self):
        # todo, is called twice, from itemClicked and selectionchanged
        # workaround because selectionchanged works only after it has been selected at least once
        if len(self.rmsList.selectedItems()) == 0:
            return
        item = self.rmsList.selectedItems()[0]
        if item.data(257):
            self.rmsView.setText(item.data(257))
            return
        pretty_item = json.dumps(json.loads(item.data(256)), indent=4)
        self.rmsView.setText(pretty_item)

    def start_proxy(self, original_host, port=None):
        httpProxy = HttpProxy()
        loop = asyncio.get_event_loop()
        if port is None:
            port = self.find_free_port()
        loop.create_task(httpProxy.run_server("127.0.0.1", port, original_host))

    @pyqtSlot()
    def on_allLaunchLeague_clicked(self):


        if not self.proxies_started:
            serv = self.allRegions.currentText()

            ProxyServers.client_config_port = self.find_free_port()
            ProxyServers.chat_port = self.find_free_port()
            configProxy = ConfigProxy(ProxyServers.chat_port)
            loop = asyncio.get_event_loop()
            loop.create_task(configProxy.run_server("127.0.0.1", ProxyServers.client_config_port, SystemYaml.client_config[serv]))

            ProxyServers.rms_port = self.find_free_port()
            rms_url = SystemYaml.rms[serv]
            parts = rms_url.split(":", 2)
            rms_url = ":".join(parts[:2])
            rms_proxy = RmsProxy(rms_url)
            loop = asyncio.get_event_loop()
            loop.create_task(rms_proxy.start_proxy())

            rtmp_proxy = RtmpProxy()
            loop = asyncio.get_event_loop()
            lcds = SystemYaml.lcds[serv]
            loop.create_task(
                rtmp_proxy.start_client_proxy("127.0.0.1", lcds.split(":")[1], lcds.split(":")[0], lcds.split(":")[1]))

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

            self.proxies_started = True

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
        QMessageBox.information(self, "About LeagueClientDebugger",
                                 "RTMP, XMPP, RMS, HTTP/S Debugger tool for League of Legends client <br> <a href='https://www.github.com/KebsCS'>GitHub</a>")

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
    def on_actionSave_full_client_config_triggered(self):
        with open(f'{self.saveDir}fullconfig.txt', 'w') as file:
            json.dump(ConfigProxy.full_config, file)

    @pyqtSlot()
    def on_xmppButtonClear_clicked(self):
        self.xmppList.clear()

    def on_rtmpButtonClear_clicked(self):
        self.rtmpList.clear()

    def on_rmsButtonClear_clicked(self):
        self.rmsList.clear()

    def on_httpsButtonClear_clicked(self):
        self.httpsList.clear()

    def scroll_func_xmpp(self):
        self.xmppList.scrollToBottom()

    @pyqtSlot(bool)
    def on_xmppScrollToBottom_toggled(self, checked):
        if checked:
            self.xmppList.model().rowsInserted.connect(self.scroll_func_xmpp)
        else:
            self.xmppList.model().rowsInserted.disconnect(self.scroll_func_xmpp)

    def scroll_func_rtmp(self):
        self.rtmpList.scrollToBottom()

    @pyqtSlot(bool)
    def on_rtmpScrollToBottom_toggled(self, checked):
        if checked:
            self.rtmpList.model().rowsInserted.connect(self.scroll_func_rtmp)
        else:
            self.rtmpList.model().rowsInserted.disconnect(self.scroll_func_rtmp)

    def scroll_func_rms(self):
        self.rmsList.scrollToBottom()

    @pyqtSlot(bool)
    def on_rmsScrollToBottom_toggled(self, checked):
        if checked:
            self.rmsList.model().rowsInserted.connect(self.scroll_func_rms)
        else:
            self.rmsList.model().rowsInserted.disconnect(self.scroll_func_rms)

    def scroll_func_https(self):
        self.httpsList.scrollToBottom()

    @pyqtSlot(bool)
    def on_httpsScrollToBottom_toggled(self, checked):
        if checked:
            self.httpsList.model().rowsInserted.connect(self.scroll_func_https)
        else:
            self.httpsList.model().rowsInserted.disconnect(self.scroll_func_https)

    # @pyqtSlot()
    # def on_actionSaveOutgoing_triggered(self):
    #     with open(f'{self.saveDir}outgoing.txt', 'a+') as file:
    #         file.write(f"<----- {datetime.fromtimestamp(self.startTime)} ----->\n")
    #         for item in range(self.outgoingList.count()):
    #             file.write(str(self.outgoingList.item(item).text())+ "\n")
    #         file.write("\n\n")

    @pyqtSlot()
    def on_httpsFiddlerButton_clicked(self):
        if not self.httpsFiddlerHost.toPlainText() or self.httpsFiddlerHost.toPlainText() == "" or not self.httpsFiddlerEnabled.isChecked():
            ProxyServers.fiddler_proxies = {}
            return
        ProxyServers.fiddler_proxies = {
            'http': self.httpsFiddlerHost.toPlainText()+":"+self.httpsFiddlerPort.toPlainText(),
            'https': self.httpsFiddlerHost.toPlainText()+":"+self.httpsFiddlerPort.toPlainText()
        }
        print(ProxyServers.fiddler_proxies)

    def on_httpsFiddlerEnabled_stateChanged(self, state):
        self.on_httpsFiddlerButton_clicked()

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

                if "fiddler_enabled" in data:
                    self.httpsFiddlerEnabled.setChecked(data["fiddler_enabled"])

                if "fiddler_host" in data:
                    self.httpsFiddlerHost.setText(data["fiddler_host"])
                else:
                    self.httpsFiddlerHost.setText("http://127.0.0.1")

                if "fiddler_port" in data:
                    self.httpsFiddlerPort.setText(data["fiddler_port"])
                else:
                    self.httpsFiddlerPort.setText("8888")

                if "selected_region" in data:
                    self.allRegions.setCurrentText(data["selected_region"])

                self.on_httpsFiddlerButton_clicked()

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

            data["fiddler_enabled"] = self.httpsFiddlerEnabled.isChecked()
            data["fiddler_host"] = self.httpsFiddlerHost.toPlainText()
            data["fiddler_port"] = self.httpsFiddlerPort.toPlainText()

            data["selected_region"] = self.allRegions.currentText()

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

