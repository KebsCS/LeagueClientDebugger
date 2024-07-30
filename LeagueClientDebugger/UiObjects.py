from PyQt5.QtWidgets import QMessageBox, QFileDialog, QListWidget, QListWidgetItem, QTableWidgetItem, QComboBox, QStyleFactory, QCheckBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
import json


class UiObjects:
    allList = None
    xmppList = None
    rtmpList = None
    rmsList = None
    httpsList = None
    lcuList = None
    rcList = None

    mitmTableWidget = None

    allCheckboxLC = None
    allTextLCArgs = None

    # Options
    optionsDisableVanguard = None
    optionsEnableInject = None
    optionsIncludeLCU = None
    optionsIncludeRC = None
    optionsIncludeJWTs = None
    optionsDisableAuth = None

    @staticmethod
    def add_connected_item(list_widget: QListWidgetItem, extra_info="", extra_data=" "):
        item = QListWidgetItem()
        item.setForeground(Qt.green)
        item.setText(f"Connected {extra_info}")
        item.setData(256, extra_data)
        list_widget.addItem(item)

    @staticmethod
    def add_disconnected_item(list_widget: QListWidgetItem, extra_info=""):
        item = QListWidgetItem()
        item.setForeground(Qt.red)
        item.setText(f"Connection lost {extra_info}")
        item.setData(256, " ")
        list_widget.addItem(item)
