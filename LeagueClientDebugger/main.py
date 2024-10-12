from LeagueClientDebugger import Ui_LeagueClientDebuggerClass
from DebuggerOptions import Ui_Dialog
import sys, json, time, os, io, asyncio, pymem, requests, gzip, re, base64, datetime, psutil
from lxml import etree
from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt, QEvent, QByteArray
from PyQt5.QtCore import QObject, QProcess, QItemSelection, QModelIndex
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QListWidgetItem, QTableWidgetItem, QComboBox, QPushButton
from PyQt5.QtGui import QColor, QIcon, QTextCharFormat, QTextCursor, QTextDocument, QSyntaxHighlighter, QGuiApplication
from qasync import QEventLoop, QApplication
from ConfigProxy import ConfigProxy
from ChatProxy import ChatProxy
from HttpProxy import HttpProxy
from RtmpProxy import RtmpProxy
from SystemYaml import SystemYaml
from ProxyServers import ProxyServers
from UiObjects import UiObjects
from RmsProxy import RmsProxy
from LcuWebsocket import LcuWebsocket, LCUConnection
from RiotWs import RiotWs

# import logging
# logging.getLogger().setLevel(logging.WARNING)
#
# logger = logging.getLogger(__name__)
# logger.handlers = []  # Remove all handlers
# logger.setLevel(logging.NOTSET)

# fix requests being blocked by fiddler
os.environ['no_proxy'] = '*'

JWT_PATTERN = r'eyJ[A-Za-z0-9=_-]+(?:\.[A-Za-z0-9=_-]+){2,}'
GZIP_PATTERN = r'H4sIA[A-Za-z0-9/+=]+'

#todo decode jwts and zips in all tabs not just start
#todo add auto inject
#todo lcu settings, optimize code, relogging, multi client
#todo speed up the listwidgets, maybe listview
#todo, finish mitm tab, vairables for mitm, like $timestamp$ so its easy to use

class MainWindow(QtWidgets.QMainWindow, Ui_LeagueClientDebuggerClass):

    counter = 0
    saveDir = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/') + '/'
    startTime = time.time()
    configFileName = "config_lcd.json"

    port = 0
    chatPort = 0

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent=parent)
        self.setupUi(self)
        self.allButtonInject.hide()

        self.allTextRCArgs.hide()
        self.allLabelRC.hide()
        self.allTextLCArgs.hide()
        self.allCheckboxLC.hide()
        # this lc method adds arguments to client config
        # other method would be running rc services without product and patchline
        # and then launching lc manually, that skips all checks but you need to fill rc port and token args
        UiObjects.allCheckboxLC = self.allCheckboxLC
        UiObjects.allTextLCArgs = self.allTextLCArgs
        self.allButtonTool.clicked.connect(self.show_hide_args)

        UiObjects.valoCallGets = self.valoCallGets

        self.allButtonDecodeJWTs.setEnabled(False)

        self.options_dialog = QtWidgets.QDialog()
        dialog_ui = Ui_Dialog()
        dialog_ui.setupUi(self.options_dialog)
        self.options_dialog.setWindowFlags(self.options_dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint | Qt.WindowCloseButtonHint)
        UiObjects.optionsDisableVanguard = dialog_ui.optionsDisableVanguard

        UiObjects.optionsEnableInject = dialog_ui.optionsEnableInject
        dialog_ui.optionsEnableInject.stateChanged.connect(lambda state: self.allButtonInject.show() if state == Qt.Checked else self.allButtonInject.hide())
        UiObjects.optionsIncludeLCU = dialog_ui.optionsIncludeLCU
        UiObjects.optionsIncludeRC = dialog_ui.optionsIncludeRC
        UiObjects.optionsIncludeJWTs = dialog_ui.optionsIncludeJWTs
        UiObjects.optionsDisableAuth = dialog_ui.optionsDisableAuth

        self.icon_xmpp = QIcon("images/xmpp.png")
        self.tabWidget.setTabIcon(1, self.icon_xmpp)
        self.icon_rtmp = QIcon("images/rtmp.png")
        self.tabWidget.setTabIcon(2, self.icon_rtmp)
        self.icon_rms = QIcon("images/rms.png")
        self.tabWidget.setTabIcon(3, self.icon_rms)
        self.icon_http = QIcon("images/http.png")
        self.tabWidget.setTabIcon(4, self.icon_http)
        self.icon_valo = QIcon("images/valo.png")
        self.tabWidget.setTabIcon(5, self.icon_valo)
        self.icon_lcu = QIcon("images/lcu.png")
        self.tabWidget.setTabIcon(6, self.icon_lcu)
        self.icon_rc = QIcon("images/rc.png")
        self.tabWidget.setTabIcon(7, self.icon_rc)

        self.mitmTableWidget.setColumnWidth(0, 104)
        self.mitmTableWidget.setColumnWidth(1, 73)
        self.mitmTableWidget.setColumnWidth(2, 262)
        self.tabWidget.setMovable(True)

        UiObjects.allList = self.allList
        UiObjects.xmppList = self.xmppList
        UiObjects.rtmpList = self.rtmpList
        UiObjects.rmsList = self.rmsList
        UiObjects.httpsList = self.httpsList
        UiObjects.valoList = self.valoList
        UiObjects.lcuList = self.lcuList
        UiObjects.rcList = self.rcList

        self.allTextSearch.installEventFilter(self)
        self.xmppTextSearch.installEventFilter(self)
        self.rtmpTextSearch.installEventFilter(self)
        self.rmsTextSearch.installEventFilter(self)
        self.httpsTextSearch.installEventFilter(self)
        self.valoTextSearch.installEventFilter(self)
        self.lcuTextSearch.installEventFilter(self)
        self.rcTextSearch.installEventFilter(self)

        self.tab_start.installEventFilter(self)
        self.tab_xmpp.installEventFilter(self)
        self.tab_rtmp.installEventFilter(self)
        self.tab_rms.installEventFilter(self)
        self.tab_https.installEventFilter(self)
        self.tab_valo.installEventFilter(self)
        self.tab_lcu.installEventFilter(self)
        self.tab_rc.installEventFilter(self)

        self.xmppList.model().rowsInserted.connect(
            lambda parent, start, end: self.add_item_to_all(self.xmppList, start))
        self.rtmpList.model().rowsInserted.connect(
            lambda parent, start, end: self.add_item_to_all(self.rtmpList, start))
        self.rmsList.model().rowsInserted.connect(
            lambda parent, start, end: self.add_item_to_all(self.rmsList, start))
        self.httpsList.model().rowsInserted.connect(
            lambda parent, start, end: self.add_item_to_all(self.httpsList, start))
        self.valoList.model().rowsInserted.connect(
            lambda parent, start, end: self.add_item_to_all(self.valoList, start))
        self.lcuList.model().rowsInserted.connect(
            lambda parent, start, end: self.add_item_to_all(self.lcuList, start))
        self.rcList.model().rowsInserted.connect(
            lambda parent, start, end: self.add_item_to_all(self.rcList, start))

        SystemYaml.read()

        self.allRegions.addItems(SystemYaml.regions)

        self.LoadConfig()

        # after load config, because searching for the process lags a bit
        self.lcu_ws = LcuWebsocket()
        self.lcuEnabled.stateChanged.connect(lambda state: self.start_lcu_ws() if state == Qt.Checked else loop.create_task(self.lcu_ws.close()))

        self.rc_ws = RiotWs()
        self.rcEnabled.stateChanged.connect(
            lambda state: self.start_rc_ws() if state == Qt.Checked else loop.create_task(self.rc_ws.close()))

        UiObjects.mitmTableWidget = self.mitmTableWidget

        ProxyServers.assign_ports()

        SystemYaml.edit()

        self.proxies_started = False
        self.custom_process = None

    def show_hide_args(self):
        if self.allTextRCArgs.isHidden():
            self.allTextRCArgs.show()
            self.allLabelRC.show()
            self.allTextLCArgs.show()
            self.allCheckboxLC.show()
        else:
            self.allTextRCArgs.hide()
            self.allLabelRC.hide()
            self.allTextLCArgs.hide()
            self.allCheckboxLC.hide()

    def eventFilter(self, obj, event):
        def handle_enter_in_textedit(text_edit, button):
            if obj is text_edit and event.key() == Qt.Key_Return and text_edit.hasFocus():
                button.click()
                return True
            return False

        def handle_ctrl_f(tab, text_edit):
            if current_tab_index == self.tabWidget.indexOf(tab):
                if event.key() == Qt.Key_F and event.modifiers() == Qt.ControlModifier:
                    text_edit.setFocus()
                    return True
            return False

        current_tab_index = self.tabWidget.currentIndex()

        if event.type() == QEvent.KeyPress:
            if handle_enter_in_textedit(self.allTextSearch, self.allButtonSearch):
                return True
            elif handle_enter_in_textedit(self.xmppTextSearch, self.xmppButtonSearch):
                return True
            elif handle_enter_in_textedit(self.rtmpTextSearch, self.rtmpButtonSearch):
                return True
            elif handle_enter_in_textedit(self.rmsTextSearch, self.rmsButtonSearch):
                return True
            elif handle_enter_in_textedit(self.httpsTextSearch, self.httpsButtonSearch):
                return True
            elif handle_enter_in_textedit(self.valoTextSearch, self.valoButtonSearch):
                return True
            elif handle_enter_in_textedit(self.lcuTextSearch, self.lcuButtonSearch):
                return True
            elif handle_enter_in_textedit(self.rcTextSearch, self.rcButtonSearch):
                return True

            elif handle_ctrl_f(self.tab_start, self.allTextSearch):
                return True
            elif handle_ctrl_f(self.tab_xmpp, self.xmppTextSearch):
                return True
            elif handle_ctrl_f(self.tab_rtmp, self.rtmpTextSearch):
                return True
            elif handle_ctrl_f(self.tab_rms, self.rmsTextSearch):
                return True
            elif handle_ctrl_f(self.tab_https, self.httpsTextSearch):
                return True
            elif handle_ctrl_f(self.tab_valo, self.valoTextSearch):
                return True
            elif handle_ctrl_f(self.tab_lcu, self.lcuTextSearch):
                return True
            elif handle_ctrl_f(self.tab_rc, self.rcTextSearch):
                return True

        return False    # super().eventFilter(obj, event)

    @pyqtSlot()
    def on_allButtonInject_clicked(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            dll_path = os.path.join(current_dir, "LeagueHooker/x64/Release/LeagueHooker.dll")

            if not os.path.exists(dll_path):
                print("DLL file not found:", dll_path)
                return
            file = pymem.Pymem("LeagueClient.exe")
            pymem.process.inject_dll(file.process_handle, bytes(dll_path, "UTF-8"))
        except Exception as e:
            print("Inject failed ", e)


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
        if text == "HTTP/S":
            self.customHttpUrl.show()
            self.customHttpMethod.show()
            self.customHttpHeaders.show()
        elif text == "LCU":
            self.customHttpUrl.show()
            self.customHttpMethod.show()
            self.customHttpHeaders.hide()
        else:
            self.customHttpUrl.hide()
            self.customHttpMethod.hide()
            self.customHttpHeaders.hide()


    def on_custom_set_clicked(self):
        sender = self.sender()
        if not sender:
            return
        for row in range(self.customTable.rowCount()):
            if self.customTable.cellWidget(row, 4) == sender:
                protocol = self.customTable.item(row, 1).text()
                self.customComboProtocol.setCurrentText(protocol)
                self.customComboDetination.setCurrentText(self.customTable.item(row, 2).text())
                if protocol == "HTTP/S" or protocol == "LCU":
                    item = self.customTable.item(row, 3)
                    self.customHttpMethod.setText(item.data(256))
                    self.customHttpUrl.setText(item.data(257))
                    if protocol != "LCU":
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
        if protocol == "HTTP/S" or protocol == "LCU":
            item = QTableWidgetItem()
            item.setText(self.customHttpMethod.toPlainText() + " " + self.customHttpUrl.toPlainText())
            item.setData(256, self.customHttpMethod.toPlainText())
            item.setData(257, self.customHttpUrl.toPlainText())
            if protocol != "LCU":
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
                QMessageBox.about(self, "Info", "RTMP custom requests are not ready yet")
            elif protocol == "LCU":
                # todo get process async on lc launch
                if not self.custom_process:
                    self.custom_process = next(LCUConnection.return_ux_process(), None)
                if self.custom_process:
                    try:
                        args = LCUConnection.process_args(self.custom_process)


                        headers = {
                            'Authorization': 'Basic ' + base64.b64encode(b'riot:' + args.lcu_token.encode()).decode(),
                            'Content-Type': 'application/json',
                            'Accept': 'application/json',
                            'User-Agent': 'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 '
                                          '(KHTML, like Gecko) LeagueOfLegendsClient/14.9.581.9966 (CEF 91) Safari/537.36'
                        }

                        url = self.customHttpUrl.toPlainText().strip()

                        if not url.startswith("http://") and not url.startswith("https://"):
                            url = "https://127.0.0.1:" + str(args.lcu_port) + url
                        elif url.startswith("https://127.0.0.1") and ":" not in url:
                            url = url[:len("https://127.0.0.1")] + ":" + str(args.lcu_port) + url[len("https://127.0.0.1"):]

                        response = requests.request(self.customHttpMethod.toPlainText().strip(),
                                                    url,
                                                    headers=headers, data=self.customText.toPlainText(),
                                                    proxies=ProxyServers.fiddler_proxies, verify=False)

                        HttpProxy.log_message(response)
                    except psutil.NoSuchProcess:
                        self.custom_process = None

        except Exception as e:
            print("Failed to send custom request ", e)


    original_text = ""
    is_decoded = False
    @pyqtSlot(int)
    def on_allList_currentRowChanged(self, row):
        if row == -1:
            return
        item = self.allList.item(row)
        data = item.data(256)
        text = json.dumps(data, indent=4) if isinstance(data, dict) else data
        self.allView.setText(text)

        matches_jwt = re.findall(JWT_PATTERN, text)
        matches_gzip = re.findall(GZIP_PATTERN, text)
        if matches_jwt or matches_gzip:
            self.allButtonDecodeJWTs.setEnabled(True)
        else:
            self.allButtonDecodeJWTs.setEnabled(False)

        self.is_decoded = False
        self.allButtonDecodeJWTs.setText("Decode JWTs and GZIPs")

    @pyqtSlot()
    def on_allButtonDecodeJWTs_clicked(self):
        scroll_value = self.allView.verticalScrollBar().value()
        if not self.is_decoded:
            self.original_text = self.allView.toPlainText()
            text = self.original_text
            matches_jwt = re.findall(JWT_PATTERN, text)
            for match in matches_jwt:
                payload = match.split('.')[1]
                payload += '=' * ((4 - len(payload) % 4) % 4)
                payload = payload.replace('-', '+').replace('_', '/')
                try:
                    decoded_payload = base64.urlsafe_b64decode(payload.encode()).decode('utf-8')
                    json_payload = bytes(decoded_payload, 'utf-8').decode('unicode_escape')
                    decoded_text = json.dumps(json.loads(json_payload), indent=4)
                    text = text.replace(match, decoded_text)
                except UnicodeDecodeError:
                    pass
            matches_gzip = re.findall(GZIP_PATTERN, text)
            for match in matches_gzip:
                decoded_text = gzip.decompress(base64.b64decode(match.encode("utf-8"))).decode('utf-8')
                try:
                    decoded_text = json.dumps(json.loads(decoded_text), indent=4)
                except Exception:
                    pass
                text = text.replace(match, decoded_text)
            self.allView.setText(text)
            self.allView.verticalScrollBar().setValue(scroll_value)
            self.allButtonDecodeJWTs.setText("Original text")
            self.is_decoded = True
        else:
            self.allView.setText(self.original_text)  # Restore original text
            self.allView.verticalScrollBar().setValue(scroll_value)
            self.allButtonDecodeJWTs.setText("Decode JWTs and GZIPs")
            self.is_decoded = False

    @pyqtSlot(int)
    def on_xmppList_currentRowChanged(self, row):
        if row == -1:
            return
        item = self.xmppList.item(row)

        def pretty_xml(xml_string):
            try:
                root = etree.fromstring(xml_string.encode("utf-8"))
                return etree.tostring(root, pretty_print=True).decode()
            except etree.XMLSyntaxError:
                return xml_string

        self.xmppView.setText(pretty_xml(item.data(256)))


    @pyqtSlot()
    def on_xmppButtonCopy_clicked(self):
        if not self.xmppView.toPlainText().strip() or len(self.xmppList.selectedItems()) == 0:
            return
        cb = QGuiApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cb.setText(self.xmppList.selectedItems()[0].data(256), mode=cb.Clipboard)


    @pyqtSlot(int)
    def on_rtmpList_currentRowChanged(self, row):
        if row == -1:
            return
        item = self.rtmpList.item(row)
        self.rtmpView.setText(item.data(256))

    @pyqtSlot(int)
    def on_rmsList_currentRowChanged(self, row):
        if row == -1:
            return
        item = self.rmsList.item(row)
        self.rmsView.setText(json.dumps(item.data(256), indent=4))

    @pyqtSlot(int)
    def on_httpsList_currentRowChanged(self, row):
        if row == -1:
            return
        item = self.httpsList.item(row)
        self.httpsRequest.setText(item.data(256))
        self.httpsResponse.setText(item.data(257))

    @pyqtSlot(int)
    def on_valoList_currentRowChanged(self, row):
        if row == -1:
            return
        item = self.valoList.item(row)
        self.valoView.setText(item.data(256))

    @pyqtSlot(int)
    def on_lcuList_currentRowChanged(self, row):
        if row == -1:
            return
        item = self.lcuList.item(row)
        self.lcuView.setText(json.dumps(item.data(256), indent=4))

    @pyqtSlot(int)
    def on_rcList_currentRowChanged(self, row):
        if row == -1:
            return
        item = self.rcList.item(row)
        self.rcView.setText(json.dumps(item.data(256), indent=4))

    @pyqtSlot()
    def on_allButtonSearch_clicked(self):
        search_text = self.allTextSearch.toPlainText().strip().lower()
        if not search_text:
            return
        for index in range(self.allList.count()):
            item = self.allList.item(index)
            text = item.data(256) if item.data(256) else " "
            if isinstance(text, dict):
                text = json.dumps(text)

            if UiObjects.optionsIncludeJWTs.isChecked():
                matches = re.findall(JWT_PATTERN, text)
                for match in matches:
                    payload = match.split('.')[1]
                    payload += '=' * ((4 - len(payload) % 4) % 4)
                    payload = payload.replace('-', '+').replace('_', '/')
                    try:
                        decoded_payload = base64.urlsafe_b64decode(payload.encode()).decode('utf-8')
                        text += "\r\n" + decoded_payload
                    except Exception:
                        pass

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
            if isinstance(text, dict):
                text = json.dumps(text)
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
    def on_valoButtonSearch_clicked(self):
        search_text = self.valoTextSearch.toPlainText().strip().lower()
        if not search_text:
            return
        for index in range(self.valoList.count()):
            item = self.valoList.item(index)
            text = item.data(256)
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
            if isinstance(text, dict):
                text = json.dumps(text)
            if search_text in text.lower():
                item.setBackground(Qt.yellow)
            else:
                item.setBackground(Qt.transparent)

    @pyqtSlot()
    def on_rcButtonSearch_clicked(self):
        search_text = self.rcTextSearch.toPlainText().strip().lower()
        if not search_text:
            return
        for index in range(self.rcList.count()):
            item = self.rcList.item(index)
            text = item.data(256) if item.data(256) else ""
            if isinstance(text, dict):
                text = json.dumps(text)
            if search_text in text.lower():
                item.setBackground(Qt.yellow)
            else:
                item.setBackground(Qt.transparent)

    def start_proxy(self, original_host, port):
        if not original_host:
            return
        httpProxy = HttpProxy()
        loop = asyncio.get_event_loop()
        loop.create_task(httpProxy.run_server("127.0.0.1", port, original_host))

    def start_lcu_ws(self):
        if self.lcu_ws.global_ws:
            return
        loop = asyncio.get_event_loop()
        loop.create_task(self.lcu_ws.start_ws())

    def start_rc_ws(self):
        if self.rc_ws.global_ws:
            return
        asyncio.create_task(self.rc_ws.run())

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
                rtmp_proxy.start_client_proxy("127.0.0.1", ProxyServers.rtmp_port, lcds.split(":")[0], lcds.split(":")[1]))

            self.start_proxy(SystemYaml.ledge[selected_region], ProxyServers.ledge_port)
            self.start_proxy(SystemYaml.entitlements[selected_region], ProxyServers.entitlements_port)
            self.start_proxy(SystemYaml.player_platform[selected_region], ProxyServers.player_platform_port)
            self.start_proxy(SystemYaml.email[selected_region], ProxyServers.email_port)
            self.start_proxy(SystemYaml.payments[selected_region], ProxyServers.payments_port)

            #todo get all hardcoded urls from config proxy if possible

            self.start_proxy("https://playerpreferences.riotgames.com", ProxyServers.playerpreferences_port)
            self.start_proxy("https://riot-geo.pas.si.riotgames.com", ProxyServers.geo_port)
            if not UiObjects.optionsDisableAuth.isChecked():
                self.start_proxy("https://auth.riotgames.com", ProxyServers.auth_port)
                self.start_proxy("https://authenticate.riotgames.com", ProxyServers.authenticator_port)
            self.start_proxy("https://api.account.riotgames.com", ProxyServers.accounts_port)
            self.start_proxy("https://content.publishing.riotgames.com",
                             ProxyServers.publishing_content_port)

            self.start_proxy("https://sieve.services.riotcdn.net", ProxyServers.sieve_port)
            self.start_proxy("https://scd.riotcdn.net", ProxyServers.scd_port)

            for server in ProxyServers.lifecycle_servers:
                self.start_proxy(server, ProxyServers.lifecycle_servers[server])

            self.start_proxy("https://pft-rndbdev.rdatasrv.net", ProxyServers.pft_port)
            self.start_proxy("https://data.riotgames.com", ProxyServers.data_riotgames_port)

            for server in ProxyServers.loyalty_servers:
                self.start_proxy(server, ProxyServers.loyalty_servers[server])

            self.start_proxy("https://pcbs.loyalty.riotgames.com", ProxyServers.pcbs_loyalty_port)

            # lor
            for server in ProxyServers.lor_login_servers:
                self.start_proxy(server, ProxyServers.lor_login_servers[server])
            for server in ProxyServers.lor_services_servers:
                self.start_proxy(server, ProxyServers.lor_services_servers[server])
            for server in ProxyServers.lor_spectate_servers:
                self.start_proxy(server, ProxyServers.lor_spectate_servers[server])

            # valorant, doesnt work, only pvp.net urls are working and theres ssl pinning
            # for server in ProxyServers.shared_servers:
            #     self.start_proxy(server, ProxyServers.shared_servers[server])

            self.proxies_started = True

        if self.lcuEnabled.isChecked():
            self.start_lcu_ws()

        if self.rcEnabled.isChecked():
            self.start_rc_ws()

        with open(os.getenv('PROGRAMDATA') + "/Riot Games/RiotClientInstalls.json", 'r', encoding='utf-8') as file: # RiotClientServices.exe
            clientPath = json.load(file)["rc_default"]
            league = QProcess(None)

            args_list = ['--' + arg.strip() for arg in self.allTextRCArgs.toPlainText().split('--') if arg.strip()]
            args_list += [f'--client-config-url=http://127.0.0.1:{ProxyServers.client_config_port}']
            if '--launch-patchline' not in self.allTextRCArgs.toPlainText():
                patchline = '--launch-patchline=' + ('pbe' if 'PBE' in selected_region else 'live')
                args_list += [patchline]
            print(f"Launched {clientPath} {args_list}")
            league.startDetached(clientPath, args_list)

    @pyqtSlot()
    def on_actionExit_triggered(self):
        QApplication.closeAllWindows()

    @pyqtSlot()
    def on_actionAbout_triggered(self):
        QMessageBox.about(self, "About LeagueClientDebugger",
                                 "RTMP, XMPP, RMS, HTTP/S Debugger tool for League of Legends client <br> <a href='https://github.com/KebsCS/LeagueClientDebugger'>GitHub</a>"+
                          "     <a href='https://discord.gg/qMmPBFpj2n'>Discord</a>")

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
        current_time = datetime.datetime.now().strftime("%H-%M-%S")
        with open(f'{self.saveDir}all_requests{current_time}.txt', 'w', encoding="utf-8") as file:
            for index in range(self.allList.count()):
                item = self.allList.item(index)
                if item is not None:
                    file.write(item.text() + '\r\n')
                    data = item.data(256)
                    data = json.dumps(data, indent=4) if isinstance(data, dict) else data
                    file.write(data.replace('\r\n', '\n') + '\r\n\r\n')


    @pyqtSlot()
    def on_actionOptions_triggered(self):
        stay_on_top = self.actionStay_on_top.isChecked()
        if stay_on_top:
            self.on_actionStay_on_top_triggered(False)

        self.options_dialog.exec_()
        if stay_on_top:
            self.on_actionStay_on_top_triggered(True)


    def add_item_to_all(self, list_widget, start):
        item = list_widget.item(start).clone()

        if item.text().startswith("Connected") or item.text().startswith("Connection lost"):
            return

        if list_widget is self.xmppList:
            item.setIcon(self.icon_xmpp)

            def pretty_xml(xml_string):
                try:
                    root = etree.fromstring(xml_string.encode("utf-8"))
                    return etree.tostring(root, pretty_print=True).decode()
                except etree.XMLSyntaxError:
                    return xml_string
            item.setData(256, pretty_xml(item.data(256)))
        elif list_widget is self.rtmpList:
            item.setIcon(self.icon_rtmp)
        elif list_widget is self.rmsList:
            item.setIcon(self.icon_rms)
        elif list_widget is self.httpsList:
            item.setIcon(self.icon_http)
            text = item.data(256) + "\n\n\n" + item.data(257)
            item.setData(256, text)
        elif list_widget is self.valoList:
            item.setIcon(self.icon_valo)
        elif list_widget is self.lcuList:
            if not UiObjects.optionsIncludeLCU.isChecked():
                return
            item.setIcon(self.icon_lcu)
        elif list_widget is self.rcList:
            if not UiObjects.optionsIncludeRC.isChecked():
                return
            item.setIcon(self.icon_rc)

        scrollbar = self.allList.verticalScrollBar()
        if not scrollbar or scrollbar.value() == scrollbar.maximum():
            self.allList.addItem(item)
            self.allList.scrollToBottom()
        else:
            self.allList.addItem(item)

    @pyqtSlot()
    def on_allButtonClear_clicked(self):
        self.allList.clear()

    @pyqtSlot()
    def on_xmppButtonClear_clicked(self):
        self.xmppList.clear()

    @pyqtSlot()
    def on_rtmpButtonClear_clicked(self):
        self.rtmpList.clear()

    @pyqtSlot()
    def on_rmsButtonClear_clicked(self):
        self.rmsList.clear()

    @pyqtSlot()
    def on_httpsButtonClear_clicked(self):
        self.httpsList.clear()

    @pyqtSlot()
    def on_valoButtonClear_clicked(self):
        self.valoList.clear()

    @pyqtSlot()
    def on_lcuButtonClear_clicked(self):
        self.lcuList.clear()

    @pyqtSlot()
    def on_rcButtonClear_clicked(self):
        self.rcList.clear()

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
        with open(self.configFileName, mode, encoding='utf-8') as configFile:
            try:
                data = json.load(configFile)
            except (io.UnsupportedOperation, json.decoder.JSONDecodeError):
                data = {}

            try:
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
                if "valoSplitter" in data:
                    self.valoSplitter.restoreState(QByteArray.fromHex(data["valoSplitter"].encode()))
                if "lcuSplitter" in data:
                    self.lcuSplitter.restoreState(QByteArray.fromHex(data["lcuSplitter"].encode()))
                if "rcSplitter" in data:
                    self.rcSplitter.restoreState(QByteArray.fromHex(data["rcSplitter"].encode()))
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
                        protocol = req["protocol"]
                        if protocol == "HTTP/S" or protocol == "LCU":
                            item = self.customTable.item(row, 3)
                            item.setData(256, req["method"])
                            item.setData(257, req["url"])
                            if protocol != "LCU":
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

                if "optionsIncludeRC" in data:
                    UiObjects.optionsIncludeRC.setChecked(data["optionsIncludeRC"])

                if "optionsIncludeJWTs" in data:
                    UiObjects.optionsIncludeJWTs.setChecked(data["optionsIncludeJWTs"])

                if "optionsDisableAuth" in data:
                    UiObjects.optionsDisableAuth.setChecked(data["optionsDisableAuth"])

                if "valoCallGets" in data:
                    self.valoCallGets.setChecked(data["valoCallGets"])

                if "lcuEnabled" in data:
                    self.lcuEnabled.setChecked(data["lcuEnabled"])

                if "rcEnabled" in data:
                    self.rcEnabled.setChecked(data["rcEnabled"])

                if "allTextRCArgs" in data:
                    self.allTextRCArgs.setPlainText(data["allTextRCArgs"])
                else:
                    self.allTextRCArgs.setPlainText("--allow-multiple-clients")

                if "allTextLCArgs" in data:
                    self.allTextLCArgs.setPlainText(data["allTextLCArgs"])
                else:
                    self.allTextLCArgs.setPlainText(
                        "--no-rads --disable-self-update --locale={locale} --rga-lite "
                        "--riotgamesapi-standalone --riotgamesapi-settings={settings-token} "
                        "--riotclient-auth-token={remoting-auth-token} --riotclient-app-port={remoting-app-port}")

                if "allCheckboxLC" in data:
                    self.allCheckboxLC.setChecked(data["allCheckboxLC"])

                self.on_httpsFiddlerButton_clicked()

            except KeyError as e:
                print("Config load error ", e)
                pass

    def SaveConfig(self):
        with open(self.configFileName, 'r+', encoding='utf-8') as configFile:
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

            data["fiddler_enabled"] = self.httpsFiddlerEnabled.isChecked()
            data["fiddler_host"] = self.httpsFiddlerHost.toPlainText()
            data["fiddler_port"] = self.httpsFiddlerPort.toPlainText()

            data["selected_region"] = self.allRegions.currentText()

            data["allSplitter"] = self.allSplitter.saveState().data().hex()
            data["xmppSplitter"] = self.xmppSplitter.saveState().data().hex()
            data["rtmpSplitter"] = self.rtmpSplitter.saveState().data().hex()
            data["rmsSplitter"] = self.rmsSplitter.saveState().data().hex()
            data["httpsSplitter"] = self.httpsSplitter.saveState().data().hex()
            data["valoSplitter"] = self.valoSplitter.saveState().data().hex()
            data["lcuSplitter"] = self.lcuSplitter.saveState().data().hex()
            data["rcSplitter"] = self.rcSplitter.saveState().data().hex()
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
                if protocol == "HTTP/S" or protocol == "LCU":
                    item = self.customTable.item(row, 3)
                    req["method"] = item.data(256)
                    req["url"] = item.data(257)
                    if protocol != "LCU":
                        req["headers"] = item.data(258)
                    req["body"] = item.data(259)
                data["customTable"].append(req)

            data["optionsDisableVanguard"] = UiObjects.optionsDisableVanguard.isChecked()
            data["optionsEnableInject"] = UiObjects.optionsEnableInject.isChecked()
            data["optionsIncludeLCU"] = UiObjects.optionsIncludeLCU.isChecked()
            data["optionsIncludeRC"] = UiObjects.optionsIncludeRC.isChecked()
            data["optionsIncludeJWTs"] = UiObjects.optionsIncludeJWTs.isChecked()
            data["optionsDisableAuth"] = UiObjects.optionsDisableAuth.isChecked()

            data["valoCallGets"] = self.valoCallGets.isChecked()
            data["lcuEnabled"] = self.lcuEnabled.isChecked()
            data["rcEnabled"] = self.rcEnabled.isChecked()

            data["allTextRCArgs"] = self.allTextRCArgs.toPlainText()
            data["allTextLCArgs"] = self.allTextLCArgs.toPlainText()
            data["allCheckboxLC"] = self.allCheckboxLC.isChecked()


            configFile.seek(0)
            json.dump(data, configFile, indent=4)
            configFile.truncate()

    #endregion

    def closeEvent(self, event):
       self.SaveConfig()
       event.accept()

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

