from LoLXMPPDebugger import Ui_LoLXMPPDebuggerClass
from DebuggerOptions import Ui_Dialog
import sys, json, time, os, io, asyncio, socket, pymem, requests, gzip
from datetime import datetime
from lxml import etree
from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt, QEvent, QByteArray
from PyQt5.QtCore import QObject, QProcess, QCoreApplication, QItemSelection, QModelIndex
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QListWidgetItem, QTableWidgetItem, QComboBox, QPushButton
from PyQt5.QtGui import QColor, QIcon, QTextCharFormat, QTextCursor, QTextDocument, QSyntaxHighlighter
from qasync import QEventLoop, QApplication
from ConfigProxy import ConfigProxy
from ChatProxy import ChatProxy
from HttpProxy import HttpProxy
from RtmpProxy import RtmpProxy
from SystemYaml import SystemYaml
from ProxyServers import ProxyServers
from UiObjects import UiObjects
from RmsProxy import RmsProxy
from LcuWebsocket import LcuWebsocket

# import logging
# logging.getLogger().setLevel(logging.WARNING)
#
# logger = logging.getLogger(__name__)
# logger.handlers = []  # Remove all handlers
# logger.setLevel(logging.NOTSET)


os.environ['no_proxy'] = '*'

#todo debug dll source, lcu in custom
#todo change file names, lock scroll to bottom like in fiddler instead of checkbox
#todo, finish mitm, vairables for mitm, like $timestamp$ or some python code executing

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
        self.allButtonInject.hide()

        self.options_dialog = QtWidgets.QDialog()
        dialog_ui = Ui_Dialog()
        dialog_ui.setupUi(self.options_dialog)
        self.options_dialog.setWindowFlags(self.options_dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint | Qt.WindowCloseButtonHint)
        UiObjects.optionsDisableVanguard = dialog_ui.optionsDisableVanguard

        #maybe add auto inject when leagueclient process detected
        UiObjects.optionsEnableInject = dialog_ui.optionsEnableInject
        dialog_ui.optionsEnableInject.stateChanged.connect(lambda state: self.allButtonInject.show() if state == Qt.Checked else self.allButtonInject.hide())
        UiObjects.optionsIncludeLCU = dialog_ui.optionsIncludeLCU

        self.icon_xmpp = QIcon("images/xmpp.png")
        self.icon_rtmp = QIcon("images/rtmp.png")
        self.icon_rms = QIcon("images/rms.png")
        self.icon_http = QIcon("images/http.png")
        self.icon_lcu = QIcon("images/lcu.png")

        self.mitmTableWidget.setColumnWidth(0, 104)
        self.mitmTableWidget.setColumnWidth(1, 73)
        self.mitmTableWidget.setColumnWidth(2, 262)
        self.tabWidget.setMovable(True)

        self.allList.currentItemChanged.connect(self.on_allList_itemClicked)
        self.allScrollToBottom.setChecked(True)

        UiObjects.xmppList = self.xmppList
        self.xmppList.currentItemChanged.connect(self.on_xmppList_itemClicked)
        self.xmppScrollToBottom.setChecked(True)

        UiObjects.rtmpList = self.rtmpList
        self.rtmpList.currentItemChanged.connect(self.on_rtmpList_itemClicked)
        self.rtmpScrollToBottom.setChecked(True)

        self.allTextSearch.installEventFilter(self)
        self.xmppTextSearch.installEventFilter(self)
        self.rtmpTextSearch.installEventFilter(self)
        self.rmsTextSearch.installEventFilter(self)
        self.httpsTextSearch.installEventFilter(self)
        self.lcuTextSearch.installEventFilter(self)

        self.tab_start.installEventFilter(self)
        self.tab_xmpp.installEventFilter(self)
        self.tab_rtmp.installEventFilter(self)
        self.tab_rms.installEventFilter(self)
        self.tab_https.installEventFilter(self)
        self.tab_lcu.installEventFilter(self)

        self.xmppList.model().rowsInserted.connect(
            lambda parent, start, end: self.add_item_to_all(self.xmppList, start))
        self.rtmpList.model().rowsInserted.connect(
            lambda parent, start, end: self.add_item_to_all(self.rtmpList, start))
        self.rmsList.model().rowsInserted.connect(lambda parent, start, end: self.add_item_to_all(self.rmsList, start))
        self.httpsList.model().rowsInserted.connect(
            lambda parent, start, end: self.add_item_to_all(self.httpsList, start))
        self.lcuList.model().rowsInserted.connect(
            lambda parent, start, end: self.add_item_to_all(self.lcuList, start))

        UiObjects.rmsList = self.rmsList
        self.rmsList.currentItemChanged.connect(self.on_rmsList_itemClicked)
        self.rmsScrollToBottom.setChecked(True)

        UiObjects.httpsList = self.httpsList
        self.httpsList.currentItemChanged.connect(self.on_httpsList_itemClicked)
        self.httpsScrollToBottom.setChecked(True)

        UiObjects.lcuList = self.lcuList
        self.lcuList.currentItemChanged.connect(self.on_lcuList_itemClicked)
        self.lcuScrollToBottom.setChecked(True)


        SystemYaml().read()

        self.allRegions.addItems(SystemYaml.regions)

        self.LoadConfig()

        # after load config, because searching for the process lags a bit
        # todo disconnect on unchecked
        self.lcuEnabled.stateChanged.connect(lambda state: self.start_lcu_ws() if state == Qt.Checked else None)

        UiObjects.mitmTableWidget = self.mitmTableWidget

        ProxyServers.assign_ports()

        SystemYaml().edit()

        self.proxies_started = False

    def eventFilter(self, obj, event):
        current_tab_index = self.tabWidget.currentIndex()
        if event.type() == QEvent.KeyPress and obj is self.allTextSearch:
            if event.key() == Qt.Key_Return and self.allTextSearch.hasFocus():
                self.on_allButtonSearch_clicked()
                return True
        elif event.type() == QEvent.KeyPress and obj is self.xmppTextSearch:
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
        elif event.type() == QEvent.KeyPress and obj is self.lcuTextSearch:
            if event.key() == Qt.Key_Return and self.lcuTextSearch.hasFocus():
                self.on_lcuButtonSearch_clicked()
                return True

        elif event.type() == QEvent.KeyPress and current_tab_index == self.tabWidget.indexOf(self.tab_start):
            if event.key() == Qt.Key_F and event.modifiers() == Qt.ControlModifier:
                self.allTextSearch.setFocus()
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
        elif event.type() == QEvent.KeyPress and current_tab_index == self.tabWidget.indexOf(self.tab_lcu):
            if event.key() == Qt.Key_F and event.modifiers() == Qt.ControlModifier:
                self.lcuTextSearch.setFocus()
                return True
        return False # super().eventFilter(obj, event)

    @pyqtSlot()
    def on_allButtonInject_clicked(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            dll_path = os.path.join(current_dir, "LeagueHooker.dll")

            if not os.path.exists(dll_path):
                print("DLL file not found:", dll_path)
                return
            file = pymem.Pymem("LeagueClient.exe")
            pymem.process.inject_dll(file.process_handle, bytes(dll_path, "UTF-8"))
        except Exception as e:
            print("Inject failed ", e)

    def closeEvent(self, event):
       self.SaveConfig()
       event.accept()

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

    def on_customComboProtocol_currentTextChanged(self, text):
        #todo maybe separate textedits for every protocol
        if text != "HTTP/S":
            self.customHttpUrl.hide()
            self.customHttpMethod.hide()
            self.customHttpHeaders.hide()
        else:
            self.customHttpUrl.show()
            self.customHttpMethod.show()
            self.customHttpHeaders.show()

    def on_custom_set_clicked(self):
        sender = self.sender()
        if not sender:
            return
        for row in range(self.customTable.rowCount()):
            if self.customTable.cellWidget(row, 4) == sender:
                protocol = self.customTable.item(row, 1).text()
                self.customComboProtocol.setCurrentText(protocol)
                self.customComboDetination.setCurrentText(self.customTable.item(row, 2).text())
                if protocol == "HTTP/S":
                    item = self.customTable.item(row, 3)
                    self.customHttpMethod.setText(item.data(256))
                    self.customHttpUrl.setText(item.data(257))
                    self.customHttpHeaders.setText(item.data(258))
                    self.customText.setText(item.data(259))
                else:
                    self.customText.setText(self.customTable.item(row, 3).text())
                break

    def on_custom_remove_clicked(self):
        sender = self.sender()
        if not sender:
            return
        for row in range(self.customTable.rowCount()):
            if self.customTable.cellWidget(row, 5) == sender:
                self.customTable.removeRow(row)
                self.customTable.setCurrentCell(0, 0)
                break

    @pyqtSlot()
    def on_customButtonSave_clicked(self):
        rowCount = self.customTable.rowCount()
        columnCount = self.customTable.columnCount()
        self.customTable.insertRow(rowCount)

        self.customTable.setItem(rowCount, 0, QTableWidgetItem(""))
        protocol = self.customComboProtocol.currentText()
        self.customTable.setItem(rowCount, 1, QTableWidgetItem(protocol))
        self.customTable.setItem(rowCount, 2, QTableWidgetItem(self.customComboDetination.currentText()))
        if protocol == "HTTP/S":
            item = QTableWidgetItem()
            item.setText(self.customHttpMethod.toPlainText() + " " + self.customHttpUrl.toPlainText())
            item.setData(256, self.customHttpMethod.toPlainText())
            item.setData(257, self.customHttpUrl.toPlainText())
            item.setData(258, self.customHttpHeaders.toPlainText())
            item.setData(259, self.customText.toPlainText())
            self.customTable.setItem(rowCount, 3, item)
        else:
            self.customTable.setItem(rowCount, 3, QTableWidgetItem(self.customText.toPlainText()))

        button = QPushButton("Set")
        button.clicked.connect(self.on_custom_set_clicked)
        self.customTable.setCellWidget(rowCount, 4, button)

        button = QPushButton("Remove")
        button.clicked.connect(self.on_custom_remove_clicked)
        self.customTable.setCellWidget(rowCount, 5, button)

    @pyqtSlot()
    def on_customButtonSend_clicked(self):
        protocol = self.customComboProtocol.currentText()
        destination = self.customComboDetination.currentText()
        text = self.customText.toPlainText()
        try:
            if protocol == "HTTP/S":

                headers_dict = {line.split(': ')[0]: line.split(': ')[1] for line in self.customHttpHeaders.toPlainText().strip().splitlines()}
                response = requests.request(self.customHttpMethod.toPlainText().strip(), self.customHttpUrl.toPlainText().strip(),
                                 headers=headers_dict, data=self.customText.toPlainText(),
                                 proxies=ProxyServers.fiddler_proxies, verify=False)

                HttpProxy.log_message(response)
            elif protocol == "XMPP":
                try:
                    parser = etree.XMLParser(remove_blank_text=True)
                    elem = etree.XML(text, parser=parser)
                    message = etree.tostring(elem).decode()
                except etree.XMLSyntaxError:
                    message = text
                if destination == "To server":
                    message = ChatProxy.log_and_edit_message(message, True)
                    ChatProxy.global_real_server.write(message.encode())
                elif destination == "To client":
                    message = ChatProxy.log_and_edit_message(message, False)
                    ChatProxy.global_league_client.write(message.encode())
            elif protocol == "RMS":
                loop = asyncio.get_event_loop()
                message = gzip.compress(text.encode())
                if destination == "To server":
                    loop.create_task(RmsProxy.log_message(message, True, RmsProxy.global_useragent))
                    loop.create_task(RmsProxy.global_target_ws.send(message))
                elif destination == "To client":
                    loop.create_task(RmsProxy.log_message(message, False, RmsProxy.global_useragent))
                    loop.create_task(RmsProxy.global_ws.send(gzip.compress(message)))
            elif protocol == "RTMP":
                #todo
                QMessageBox.information(self, "Info", "RTMP custom requests are not ready yet")

        except Exception as e:
            print("Failed to send custom request ", e)


    @pyqtSlot(QListWidgetItem)
    def on_allList_itemClicked(self, item: QListWidgetItem):
        if len(self.allList.selectedItems()) == 0:
            return
        item = self.allList.selectedItems()[0]
        data = item.data(256)
        self.allView.setText(json.dumps(data, indent=4) if isinstance(data, dict) else data)

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
        self.rtmpView.setText(item.data(256))

    @pyqtSlot(QListWidgetItem)
    def on_httpsList_itemClicked(self):
        if len(self.httpsList.selectedItems()) == 0:
            return
        item = self.httpsList.selectedItems()[0]
        self.httpsRequest.setText(item.data(256))
        self.httpsResponse.setText(item.data(257))

    @pyqtSlot(QListWidgetItem)
    def on_lcuList_itemClicked(self):
        if len(self.lcuList.selectedItems()) == 0:
            return
        item = self.lcuList.selectedItems()[0]
        self.lcuView.setText(json.dumps(item.data(256), indent=4))

    @pyqtSlot()
    def on_allButtonSearch_clicked(self):
        search_text = self.allTextSearch.toPlainText().strip().lower()
        if not search_text:
            return
        for index in range(self.allList.count()):
            item = self.allList.item(index)
            text = item.data(256) if item.data(256) else " "
            if search_text in text.lower():
                item.setBackground(Qt.yellow)
            else:
                item.setBackground(Qt.transparent)

    @pyqtSlot()
    def on_xmppButtonSearch_clicked(self):
        search_text = self.xmppTextSearch.toPlainText().strip().lower()
        if not search_text:
            return
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
        if not search_text:
            return
        for index in range(self.rtmpList.count()):
            item = self.rtmpList.item(index)
            text = item.data(256) if item.data(256) else ""
            if search_text in text.lower():
                item.setBackground(Qt.yellow)
            else:
                item.setBackground(Qt.transparent)

    @pyqtSlot()
    def on_rmsButtonSearch_clicked(self):
        search_text = self.rmsTextSearch.toPlainText().strip().lower()
        if not search_text:
            return
        for index in range(self.rmsList.count()):
            item = self.rmsList.item(index)
            text = item.data(256) if item.data(256) else ""
            if search_text in text.lower():
                item.setBackground(Qt.yellow)
            else:
                item.setBackground(Qt.transparent)

    @pyqtSlot()
    def on_httpsButtonSearch_clicked(self):
        search_text = self.httpsTextSearch.toPlainText().strip().lower()
        if not search_text:
            return
        for index in range(self.httpsList.count()):
            item = self.httpsList.item(index)
            text = item.data(256) + " " + item.data(257)
            if search_text in text.lower():
                item.setBackground(Qt.yellow)
            else:
                item.setBackground(Qt.transparent)

    @pyqtSlot()
    def on_lcuButtonSearch_clicked(self):
        search_text = self.lcuTextSearch.toPlainText().strip().lower()
        if not search_text:
            return
        for index in range(self.lcuList.count()):
            item = self.lcuList.item(index)
            text = item.data(256) if item.data(256) else ""
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
        self.rmsView.setText(item.data(256))

    def start_proxy(self, original_host, port):
        httpProxy = HttpProxy()
        loop = asyncio.get_event_loop()
        loop.create_task(httpProxy.run_server("127.0.0.1", port, original_host))

    def start_lcu_ws(self):
        if LcuWebsocket.is_running:
            return
        lcu_ws = LcuWebsocket()
        loop = asyncio.get_event_loop()
        loop.create_task(lcu_ws.start_ws())

    @pyqtSlot()
    def on_allLaunchLeague_clicked(self):
        selected_region = self.allRegions.currentText()

        if not self.proxies_started:
            configProxy = ConfigProxy(ProxyServers.chat_port)
            loop = asyncio.get_event_loop()
            loop.create_task(configProxy.run_server("127.0.0.1", ProxyServers.client_config_port, SystemYaml.client_config[selected_region]))

            rms_proxy = RmsProxy(SystemYaml.rms[selected_region])
            loop = asyncio.get_event_loop()
            loop.create_task(rms_proxy.start_proxy())

            rtmp_proxy = RtmpProxy()
            loop = asyncio.get_event_loop()
            lcds = SystemYaml.lcds[selected_region]
            loop.create_task(
                rtmp_proxy.start_client_proxy("127.0.0.1", lcds.split(":")[1], lcds.split(":")[0], lcds.split(":")[1]))

            self.start_proxy(SystemYaml.ledge[selected_region], ProxyServers.ledge_port)
            self.start_proxy(SystemYaml.entitlements[selected_region], ProxyServers.entitlements_port)
            self.start_proxy(SystemYaml.player_platform[selected_region], ProxyServers.player_platform_port)
            self.start_proxy(SystemYaml.email[selected_region], ProxyServers.email_port)
            self.start_proxy(SystemYaml.payments[selected_region], ProxyServers.payments_port)

            self.start_proxy("https://playerpreferences.riotgames.com", ProxyServers.playerpreferences_port) #todo could get url from config proxy
            self.start_proxy("https://riot-geo.pas.si.riotgames.com", ProxyServers.geo_port) #todo could get url from config proxy

            self.start_proxy("https://auth.riotgames.com", ProxyServers.auth_port)  # todo could get url from config proxy

            self.start_proxy("https://authenticate.riotgames.com", ProxyServers.authenticator_port)  # todo could get url from config proxy

            self.start_proxy("https://api.account.riotgames.com", ProxyServers.accounts_port)  # todo could get url from config proxy

            self.start_proxy("https://content.publishing.riotgames.com",
                             ProxyServers.publishing_content_port)  # todo could get url from config proxy

            self.start_proxy("https://sieve.services.riotcdn.net", ProxyServers.sieve_port)  # todo could get url from config proxy

            self.start_proxy("https://scd.riotcdn.net", ProxyServers.scd_port)  # todo could get url from config proxy

            self.start_proxy("https://player-lifecycle-euc.publishing.riotgames.com", ProxyServers.lifecycle_port)  # todo could get url from config proxy also there are different servers

            self.start_proxy("https://eu.lers.loyalty.riotgames.com", ProxyServers.loyalty_port )

            self.start_proxy("https://pcbs.loyalty.riotgames.com", ProxyServers.pcbs_loyalty_port)

            self.proxies_started = True

        if self.lcuEnabled.isChecked():
            self.start_lcu_ws()

        with open("C:/ProgramData/Riot Games/RiotClientInstalls.json", 'r') as file:
            clientPath = json.load(file)["rc_default"]
            league = QProcess(None)
            patchline = '--launch-patchline=' + 'pbe' if 'PBE' in selected_region else 'live'
            args = ['--allow-multiple-clients', f'--launch-product=league_of_legends', patchline, f'--client-config-url=http://127.0.0.1:{ProxyServers.client_config_port}']
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
        if self.saveDir and self.saveDir[-1] != "/":
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
        with open(f'{self.saveDir}fullconfig.txt', 'w', encoding="utf-8") as file:
            json.dump(ConfigProxy.full_config, file)

    @pyqtSlot()
    def on_actionSave_all_requests_triggered(self):
        with open(f'{self.saveDir}all_requests.txt', 'w', encoding="utf-8") as file:
            for index in range(self.allList.count()):
                item = self.allList.item(index)
                if item is not None:
                    file.write(item.text() + '\r\n')
                    file.write(item.data(256) + '\r\n\r\n')


    @pyqtSlot()
    def on_actionOptions_triggered(self):
        self.options_dialog.exec_()


    def add_item_to_all(self, list_widget, start):
        item = list_widget.item(start).clone()

        if item.text().startswith("Connected") or item.text().startswith("Connection lost"):
            return

        if list_widget is self.xmppList:
            item.setIcon(self.icon_xmpp)
        elif list_widget is self.rtmpList:
            item.setIcon(self.icon_rtmp)
        elif list_widget is self.rmsList:
            item.setIcon(self.icon_rms)
        elif list_widget is self.httpsList:
            item.setIcon(self.icon_http)
            text = item.data(256) + "\n\n\n" + item.data(257)
            item.setData(256, text)
        elif list_widget is self.lcuList:
            if not UiObjects.optionsIncludeLCU.isChecked():
                return
            item.setIcon(self.icon_lcu)

        self.allList.addItem(item)

    @pyqtSlot()
    def on_allButtonClear_clicked(self):
        self.allList.clear()

    @pyqtSlot()
    def on_xmppButtonClear_clicked(self):
        self.xmppList.clear()

    def on_rtmpButtonClear_clicked(self):
        self.rtmpList.clear()

    def on_rmsButtonClear_clicked(self):
        self.rmsList.clear()

    def on_httpsButtonClear_clicked(self):
        self.httpsList.clear()

    def on_lcuButtonClear_clicked(self):
        self.lcuList.clear()

    def scroll_func_all(self):
        self.allList.scrollToBottom()

    @pyqtSlot(bool)
    def on_allScrollToBottom_toggled(self, checked):
        if checked:
            self.allList.model().rowsInserted.connect(self.scroll_func_all)
        else:
            self.allList.model().rowsInserted.disconnect(self.scroll_func_all)

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


    def scroll_func_lcu(self):
        self.lcuList.scrollToBottom()

    @pyqtSlot(bool)
    def on_lcuScrollToBottom_toggled(self, checked):
        if checked:
            self.lcuList.model().rowsInserted.connect(self.scroll_func_lcu)
        else:
            self.lcuList.model().rowsInserted.disconnect(self.scroll_func_lcu)


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

    #region Config
    def LoadConfig(self):
        mode = 'r' if os.path.exists(self.configFileName) else 'w'
        with open(self.configFileName, mode) as configFile:
            try:
                data = json.load(configFile)

                if "geometry" in data:
                    self.restoreGeometry(QByteArray.fromHex(data["geometry"].encode()))

                if "tab_order" in data:
                    for i, tab_text in enumerate(data["tab_order"]):
                        for j in range(self.tabWidget.count()):
                            if self.tabWidget.tabText(j) == tab_text:
                                #self.tabWidget.tabBar().moveTab(j, i)
                                self.tabWidget.moveTab(j, i)
                                break
                    self.tabWidget.setCurrentIndex(0)

                if "stay_on_top" in data:
                    self.actionStay_on_top.setChecked(data["stay_on_top"])
                    self.on_actionStay_on_top_triggered(self.actionStay_on_top.isChecked())

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

                # if "custom_xmpp" in data:
                #     self.xmppCustomTextEdit.setText(data["custom_xmpp"])

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


                if "allSplitter" in data:
                    self.allSplitter.restoreState(QByteArray.fromHex(data["allSplitter"].encode()))
                if "xmppSplitter" in data:
                    self.xmppSplitter.restoreState(QByteArray.fromHex(data["xmppSplitter"].encode()))
                if "rtmpSplitter" in data:
                    self.rtmpSplitter.restoreState(QByteArray.fromHex(data["rtmpSplitter"].encode()))
                if "rmsSplitter" in data:
                    self.rmsSplitter.restoreState(QByteArray.fromHex(data["rmsSplitter"].encode()))
                if "httpsSplitter" in data:
                    self.httpsSplitter.restoreState(QByteArray.fromHex(data["httpsSplitter"].encode()))
                if "customSplitter" in data:
                    self.customSplitter.restoreState(QByteArray.fromHex(data["customSplitter"].encode()))

                if "customTableGeometry" in data:
                    self.customTable.restoreGeometry(QByteArray.fromHex(data["customTableGeometry"].encode()))
                if "custom_column_sizes" in data:
                    for col, size in enumerate(data["custom_column_sizes"]):
                        self.customTable.setColumnWidth(col, size)

                if "customTable" in data:
                    for req in data["customTable"]:
                        self.on_customButtonSave_clicked()
                        row = self.customTable.rowCount()-1
                        self.customTable.item(row, 0).setText(req["name"])
                        self.customTable.item(row, 1).setText(req["protocol"])
                        self.customTable.item(row, 2).setText(req["destination"])
                        self.customTable.item(row, 3).setText(req["text"])
                        if req["protocol"] == "HTTP/S":
                            item = self.customTable.item(row, 3)
                            item.setData(256, req["url"])
                            item.setData(257, req["method"])
                            item.setData(258, req["headers"])
                            item.setData(259, req["body"])

                if "optionsDisableVanguard" in data:
                    UiObjects.optionsDisableVanguard.setChecked(data["optionsDisableVanguard"])
                    if data["optionsEnableInject"]:
                        self.allButtonInject.show()

                if "optionsEnableInject" in data:
                    UiObjects.optionsEnableInject.setChecked(data["optionsEnableInject"])

                if "optionsIncludeLCU" in data:
                    UiObjects.optionsIncludeLCU.setChecked(data["optionsIncludeLCU"])

                if "lcuEnabled" in data:
                    self.lcuEnabled.setChecked(data["lcuEnabled"])

                self.on_httpsFiddlerButton_clicked()

            except (json.decoder.JSONDecodeError, KeyError, io.UnsupportedOperation):
                pass

    def SaveConfig(self):
        with open(self.configFileName, 'r+') as configFile:
            data = json.load(configFile) if os.stat(self.configFileName).st_size != 0 else {}

            data["geometry"] = self.saveGeometry().data().hex()

            tab_order = []
            for i in range(self.tabWidget.count()):
                tab_order.append(self.tabWidget.tabText(i))
            data["tab_order"] = tab_order

            data["stay_on_top"] = self.actionStay_on_top.isChecked()

            data['saveDir'] = self.saveDir
            data["mitm"] = []
            for row in range(self.mitmTableWidget.rowCount()):
                rule = {"type": self.mitmTableWidget.cellWidget(row, 0).currentText(),
                        "protocol": self.mitmTableWidget.cellWidget(row, 1).currentText(),
                        "enabled": self.mitmTableWidget.item(row, 2).checkState(),
                        "contains": self.mitmTableWidget.item(row, 2).text(),
                        "changeto": self.mitmTableWidget.item(row, 3).text()}
                data["mitm"].append(rule)

            # data["custom_xmpp"] = self.xmppCustomTextEdit.toPlainText()

            data["fiddler_enabled"] = self.httpsFiddlerEnabled.isChecked()
            data["fiddler_host"] = self.httpsFiddlerHost.toPlainText()
            data["fiddler_port"] = self.httpsFiddlerPort.toPlainText()

            data["selected_region"] = self.allRegions.currentText()

            data["allSplitter"] = self.allSplitter.saveState().data().hex()
            data["xmppSplitter"] = self.xmppSplitter.saveState().data().hex()
            data["rtmpSplitter"] = self.rtmpSplitter.saveState().data().hex()
            data["rmsSplitter"] = self.rmsSplitter.saveState().data().hex()
            data["httpsSplitter"] = self.httpsSplitter.saveState().data().hex()
            data["customSplitter"] = self.customSplitter.saveState().data().hex()

            data["customTableGeometry"] = self.customTable.saveGeometry().data().hex()

            custom_column_sizes = [self.customTable.columnWidth(col) for col in range(self.customTable.columnCount())]
            data["custom_column_sizes"] = custom_column_sizes

            data["customTable"] = []
            for row in range(self.customTable.rowCount()):
                name = self.customTable.item(row, 0)
                protocol = self.customTable.item(row, 1).text()
                req = {
                    "name": name.text() if name else "",
                    "protocol": protocol,
                    "destination": self.customTable.item(row, 2).text(),
                    "text": self.customTable.item(row, 3).text()
                }
                if protocol == "HTTP/S":
                    item = self.customTable.item(row, 3)
                    req["method"] = item.data(256)
                    req["url"] = item.data(257)
                    req["headers"] = item.data(258)
                    req["body"] = item.data(259)
                data["customTable"].append(req)

            data["optionsDisableVanguard"] = UiObjects.optionsDisableVanguard.isChecked()
            data["optionsEnableInject"] = UiObjects.optionsEnableInject.isChecked()
            data["optionsIncludeLCU"] = UiObjects.optionsIncludeLCU.isChecked()

            data["lcuEnabled"] = self.lcuEnabled.isChecked()


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

