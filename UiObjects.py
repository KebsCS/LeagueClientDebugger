from PyQt5.QtWidgets import QMessageBox, QFileDialog, QListWidgetItem, QTableWidgetItem, QComboBox, QStyleFactory, QCheckBox
from PyQt5.QtCore import Qt
import json


class UiObjects:
    xmppList = QListWidgetItem()
    rtmpList = QListWidgetItem()
    rmsList = QListWidgetItem()
    httpsList = QListWidgetItem()
    lcuList = QListWidgetItem()

    mitmTableWidget = QTableWidgetItem()

    # Options
    optionsDisableVanguard = QCheckBox
    optionsEnableInject = QCheckBox
    optionsIncludeLCU = QCheckBox

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
