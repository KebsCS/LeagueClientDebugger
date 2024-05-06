# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'DebuggerOptions.ui'
#
# Created by: PyQt5 UI code generator 5.15.9
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(400, 300)
        Dialog.setModal(False)
        self.horizontalLayout = QtWidgets.QHBoxLayout(Dialog)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout()
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.optionsIncludeLCU = QtWidgets.QCheckBox(Dialog)
        self.optionsIncludeLCU.setObjectName("optionsIncludeLCU")
        self.verticalLayout_3.addWidget(self.optionsIncludeLCU)
        self.optionsDisableVanguard = QtWidgets.QCheckBox(Dialog)
        self.optionsDisableVanguard.setObjectName("optionsDisableVanguard")
        self.verticalLayout_3.addWidget(self.optionsDisableVanguard)
        self.optionsEnableInject = QtWidgets.QCheckBox(Dialog)
        self.optionsEnableInject.setObjectName("optionsEnableInject")
        self.verticalLayout_3.addWidget(self.optionsEnableInject)
        self.optionsIncludeJWTs = QtWidgets.QCheckBox(Dialog)
        self.optionsIncludeJWTs.setObjectName("optionsIncludeJWTs")
        self.verticalLayout_3.addWidget(self.optionsIncludeJWTs)
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout_3.addItem(spacerItem)
        self.horizontalLayout.addLayout(self.verticalLayout_3)
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout.addLayout(self.verticalLayout)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Options"))
        self.optionsIncludeLCU.setText(_translate("Dialog", "Include LCU in Start tab \n"
"(Not recommended, slows down the app)"))
        self.optionsDisableVanguard.setText(_translate("Dialog", "Disable Vanguard"))
        self.optionsEnableInject.setText(_translate("Dialog", "Enable debug dll injecting"))
        self.optionsIncludeJWTs.setText(_translate("Dialog", "Include decoded JWTs in search\n"
"(Currently only in Start tab)"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    Dialog = QtWidgets.QDialog()
    ui = Ui_Dialog()
    ui.setupUi(Dialog)
    Dialog.show()
    sys.exit(app.exec_())
