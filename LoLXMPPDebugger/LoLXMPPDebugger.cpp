#include "LoLXMPPDebugger.h"

LoLXMPPDebugger::LoLXMPPDebugger(QWidget* parent)
	: QMainWindow(parent)
{
	ui.setupUi(this);
	ui.incomingScrollToBottom->setCheckState(Qt::CheckState::Checked);
	ui.outgoingScrollToBottom->setCheckState(Qt::CheckState::Checked);

	startTime = QDateTime::currentDateTime();

	ui.statusBar->showMessage("Connecting...", 3000);
	// connect and stuff
	ui.statusBar->showMessage("Connected.", 10000);
}

LoLXMPPDebugger::~LoLXMPPDebugger()
{
}

void LoLXMPPDebugger::on_outgoingScrollToBottom_toggled(bool state)
{
	if (state)
	{
		connect(
			ui.outgoingList->model(),
			SIGNAL(rowsInserted(const QModelIndex&, int, int)),
			ui.outgoingList,
			SLOT(scrollToBottom())
		);
	}
	else
	{
		disconnect(
			ui.outgoingList->model(),
			SIGNAL(rowsInserted(const QModelIndex&, int, int)),
			ui.outgoingList,
			SLOT(scrollToBottom())
		);
	}
}

void LoLXMPPDebugger::on_incomingScrollToBottom_toggled(bool state)
{
	if (state)
	{
		connect(
			ui.incomingList->model(),
			SIGNAL(rowsInserted(const QModelIndex&, int, int)),
			ui.incomingList,
			SLOT(scrollToBottom())
		);
	}
	else
	{
		disconnect(
			ui.incomingList->model(),
			SIGNAL(rowsInserted(const QModelIndex&, int, int)),
			ui.incomingList,
			SLOT(scrollToBottom())
		);
	}
}

void LoLXMPPDebugger::on_outgoingButtonClear_clicked()
{
	ui.outgoingList->clear();
}

void LoLXMPPDebugger::on_incomingButtonClear_clicked()
{
	ui.incomingList->clear();
}

void LoLXMPPDebugger::on_actionExit_triggered()
{
	QApplication::quit();
}

void LoLXMPPDebugger::on_actionAbout_triggered()
{
	QMessageBox::information(this, "About LoLXMPPDebugger", "Simple XMPP debugger tool for League of Legends client <br> <a href='https://www.github.com/KebsCS'>GitHub</a>");
}

void LoLXMPPDebugger::on_actionOutgoing_triggered()
{
	QFile file("outgoing.txt");
	if (!file.open(QFile::Append | QFile::Text))
	{
		ui.statusBar->showMessage("Failed to save", 5000);
		return;
	}

	QTextStream out(&file);
	out << "<----- " << startTime.toString("dd-MM-yyyy HH:mm:ss") << " ----->" << Qt::endl;
	for (auto item : ui.outgoingList->findItems("*", Qt::MatchWildcard))
	{
		out << item->text() << Qt::endl;
	}
	file.close();
}

void LoLXMPPDebugger::on_actionIncoming_triggered()
{
	QFile file("incoming.txt");
	if (!file.open(QFile::Append | QFile::Text))
	{
		ui.statusBar->showMessage("Failed to save", 5000);
		return;
	}

	QTextStream out(&file);
	out << "<----- " << startTime.toString("dd-MM-yyyy HH:mm:ss") << " ----->" << Qt::endl;
	for (auto item : ui.incomingList->findItems("*", Qt::MatchWildcard))
	{
		out << item->text() << Qt::endl;
	}
	file.close();
}

void LoLXMPPDebugger::on_actionBoth_triggered()
{
	on_actionOutgoing_triggered();
	on_actionIncoming_triggered();
}

void LoLXMPPDebugger::on_actionChoose_directory_triggered()
{
	// TODO: Start in current save dir, instead of app dir
	saveDir = QFileDialog::getExistingDirectory(this, "Select save directory", QCoreApplication::applicationDirPath());
}

void LoLXMPPDebugger::on_pushButton_clicked()
{
	ui.outgoingList->addItem(QString::number(counter++));
	ui.incomingList->addItem(QString::number(counter++));
}