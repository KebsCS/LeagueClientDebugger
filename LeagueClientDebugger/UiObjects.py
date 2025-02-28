from PyQt5.QtWidgets import QMessageBox, QFileDialog, QListWidget, QListWidgetItem, QTableWidgetItem, QComboBox, QStyleFactory, QCheckBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
import json, requests, gzip


class UiObjects:
    allList = None
    xmppList = None
    rtmpList = None
    rmsList = None
    httpsList = None
    lcuList = None
    rcList = None
    valoList = None

    mitmTableWidget = None

    allCheckboxLC = None
    allTextLCArgs = None

    allDisableVanguard = None
    valoCallGets = None

    miscDowngradeLCEnabled = None
    miscDowngradeLCText = None

    # Options
    optionsDarkMode = None
    optionsEnableInject = None
    optionsIncludeLCU = None
    optionsIncludeRC = None
    optionsIncludeJWTs = None
    optionsDisableAuth = None
    optionsRunAsAdmin = None
    optionsClientHandlesCookies = None
    optionsDisableRTMPEncoding = None

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


class Request:
    def __init__(self):
        self.headers = dict()
        self.method = "GET"
        self.version = None
        self.url = "/"
        self.body = b""


def to_raw_response(response: requests.Response) -> bytearray:
    HTTP_VERSIONS = {
        9: b'0.9',
        10: b'1.0',
        11: b'1.1',
    }

    def _coerce_to_bytes(data):
        if not isinstance(data, bytes) and hasattr(data, 'encode'):
            data = data.encode('utf-8')
        return data if data is not None else b''

    def _format_header(name, value):
        return (_coerce_to_bytes(name) + b': ' + _coerce_to_bytes(value) +
                b'\r\n')

    bytearr = bytearray()
    raw = response.raw
    version_str = HTTP_VERSIONS.get(raw.version, b'?')

    bytearr.extend(b'HTTP/' + version_str + b' ' +
                   str(raw.status).encode('ascii') + b' ' +
                   _coerce_to_bytes(response.reason) + b'\r\n')

    headers = raw.headers
    for name in headers.keys():
        for value in headers.getlist(name):
            bytearr.extend(_format_header(name, value))

    if len(response.content) > 0 and 'Content-Length' not in headers:
        bytearr.extend(_format_header('Content-Length', str(len(response.content))))

    bytearr.extend(b'\r\n')

    bytearr.extend(response.content)
    return bytearr


def to_raw_request(request) -> bytearray:

    def _coerce_to_bytes(data):
        if not isinstance(data, bytes) and hasattr(data, 'encode'):
            data = data.encode('utf-8')

        if isinstance(data, bytes):
            if data[0] == 0x1F and data[1] == 0x8B and data[2] == 0x08:    # gzip file format header
                data = gzip.decompress(data)

        return data if data is not None else b''

    def _build_request_path(url):
        uri = requests.compat.urlparse(url)
        request_path = _coerce_to_bytes(uri.path)
        if uri.query:
            request_path += b'?' + _coerce_to_bytes(uri.query)

        return request_path, uri

    def _format_header(name, value):
        return (_coerce_to_bytes(name) + b': ' + _coerce_to_bytes(value) +
                b'\r\n')

    method = _coerce_to_bytes(request.method)
    request_path, uri = _build_request_path(request.url)

    bytearr = bytearray()

    headers = request.headers.copy()
    host_header = _coerce_to_bytes(headers.pop('Host', uri.netloc))

    bytearr.extend(method + b' ' + b'https://' + host_header + request_path + b' HTTP/1.1\r\n')

    bytearr.extend(b'Host: ' + host_header + b'\r\n')

    for name, value in headers.items():
        bytearr.extend(_format_header(name, value))

    bytearr.extend(b'\r\n')
    if request.body:
        if isinstance(request.body, requests.compat.basestring):
            bytearr.extend(_coerce_to_bytes(request.body))
        else:
            # In the event that the body is a file-like object, let's not try
            # to read everything into memory.
            bytearr.extend('<< Request body is not a string-like type >>')
    bytearr.extend(b'\r\n')
    return bytearr
