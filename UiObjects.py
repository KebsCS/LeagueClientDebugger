from PyQt5.QtWidgets import QMessageBox, QFileDialog, QListWidgetItem, QTableWidgetItem, QComboBox, QStyleFactory
from PyQt5.QtCore import Qt
import json


class UiObjects:
    xmppList = QListWidgetItem()
    rtmpList = QListWidgetItem()
    rmsList = QListWidgetItem()
    httpsList = QListWidgetItem()

    mitmTableWidget = QTableWidgetItem()

    @staticmethod
    def add_connected_item(list_widget: QListWidgetItem, extra_info="", extra_data=" "):
        item = QListWidgetItem()
        item.setForeground(Qt.green)
        item.setText(f"Connected {extra_info}")
        item.setData(257, extra_data)
        list_widget.addItem(item)

    @staticmethod
    def add_disconnected_item(list_widget: QListWidgetItem, extra_info=""):
        item = QListWidgetItem()
        item.setForeground(Qt.red)
        item.setText(f"Connection lost {extra_info}")
        item.setData(257, " ")
        list_widget.addItem(item)
