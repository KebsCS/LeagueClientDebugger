#pragma once

#include <QtWidgets/QMainWindow>
#include <QDateTime>
#include <QFile>
#include <QMessageBox>
#include <QFileDialog>

#include "ui_LoLXMPPDebugger.h"

class LoLXMPPDebugger : public QMainWindow
{
	Q_OBJECT

public:
	LoLXMPPDebugger(QWidget* parent = Q_NULLPTR);
	~LoLXMPPDebugger();

private slots:
	void on_pushButton_clicked();

	void on_outgoingScrollToBottom_toggled(bool);
	void on_incomingScrollToBottom_toggled(bool);

	void on_outgoingButtonClear_clicked();
	void on_incomingButtonClear_clicked();

	void on_actionExit_triggered();
	void on_actionAbout_triggered();
	void on_actionOutgoing_triggered();
	void on_actionIncoming_triggered();
	void on_actionBoth_triggered();
	void on_actionChoose_directory_triggered();

private:
	Ui::LoLXMPPDebuggerClass ui;

	QDateTime startTime;

	QString saveDir;

	int counter = 0;
};
