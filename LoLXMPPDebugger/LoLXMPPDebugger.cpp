#include "LoLXMPPDebugger.h"

LoLXMPPDebugger::LoLXMPPDebugger(QWidget* parent)
	: QMainWindow(parent)
{
	ui.setupUi(this);
	ui.incomingScrollToBottom->setCheckState(Qt::CheckState::Checked);
	ui.outgoingScrollToBottom->setCheckState(Qt::CheckState::Checked);

	startTime = QDateTime::currentDateTime();

	ui.statusBar->showMessage("Connecting...", 3000);

	// open a free available port
	socket = new QTcpSocket(this);
	socket->bind(QHostAddress::SpecialAddress::LocalHost, 0);
	socket->connectToHost(QHostAddress::SpecialAddress::LocalHost, 0);
	
	port = socket->localPort();
	qDebug() << "PORT " << socket->peerPort() << " - " << socket->localPort();
	
	// start a server on open port
	server = new QTcpServer(this);
	if (!server->listen(QHostAddress::Any, port))
	{
		qDebug() << "Couldnt start server";
	}
	else
	{
		qDebug() << "Server started";
	}

	connect(server, SIGNAL(newConnection()), this, SLOT(onNewConnection()));

	//QNetworkProxy proxy;
	//proxy.setType(QNetworkProxy::HttpProxy);
	//proxy.setHostName(server->serverAddress().toString());
	//proxy.setPort(server->serverPort());
	////proxy.setUser("username");
	////proxy.setPassword("password");
	//QNetworkProxy::setApplicationProxy(proxy);

	//server->close();


	//NetworkProxy nt;
	//nt.queryProxy(socket->proxy());

	// 1. Set up a server on localhost
	// proxy everything from https://clientconfig.rpg.riotgames.com



	// connect and stuff
	ui.statusBar->showMessage("Connected.", 10000);
}

void LoLXMPPDebugger::onNewConnection()
{
	QTcpSocket* clientSocket = server->nextPendingConnection();
	connect(clientSocket, SIGNAL(readyRead()), this, SLOT(onReadyRead()));
	connect(clientSocket, SIGNAL(stateChanged(QAbstractSocket::SocketState)), this, SLOT(onSocketStateChanged(QAbstractSocket::SocketState)));

	clients.push_back(clientSocket);
	for (QTcpSocket* socket : clients)
	{		
		qDebug() << clientSocket->peerAddress().toString() << " connected to server";
	}

}

void LoLXMPPDebugger::onSocketStateChanged(QAbstractSocket::SocketState socketState)
{
	if (socketState == QAbstractSocket::UnconnectedState)
	{
		QTcpSocket* sender = static_cast<QTcpSocket*>(QObject::sender());
		clients.removeOne(sender);
	}
}

void LoLXMPPDebugger::onReadyRead()
{
	QTcpSocket* sender = static_cast<QTcpSocket*>(QObject::sender());
	QString response = sender->readAll();
	for (QTcpSocket* socket : clients) {
		if (socket != sender)
		{
			qDebug() << "Server received: " << response;
			QStringList buf = QString(response).split(' ');
			
			QNetworkAccessManager* manager = new QNetworkAccessManager(this);
			connect(manager, SIGNAL(finished(QNetworkReply*)), this, SLOT(onFinishRequest(QNetworkReply*)));
			connect(manager, SIGNAL(finished(QNetworkReply*)), manager, SLOT(deleteLater()));

			QString url = "https://clientconfig.rpg.riotgames.com" + buf.at(1);
			QNetworkRequest request(url);
			request.setHeader(QNetworkRequest::KnownHeaders::ContentTypeHeader, "application/json");
			request.setRawHeader(QByteArray("Host"), "clientconfig.rpg.riotgames.com");
			
			QRegularExpression userAgent("(?<=user-agent: )([a-zA-Z]+)");
			QRegularExpressionMatch match = userAgent.match(response);
			if (match.hasMatch())
			{
				request.setHeader(QNetworkRequest::KnownHeaders::UserAgentHeader, match.captured());
			}
			QRegularExpression acceptEncoding("(?<=Accept-Encoding: )([a-zA-Z]+)");
			match = acceptEncoding.match(response);
			if (match.hasMatch())
			{
				request.setRawHeader(QByteArray("Accept-Encoding"), match.captured().toUtf8());
			}
			QRegularExpression accept("(?<=Accept: )([a-z/A-Z]+)");
			match = accept.match(response);
			if (match.hasMatch())
			{
				request.setRawHeader(QByteArray("Accept"), match.captured().toUtf8());
			}

			manager->get(request);

		}
	}
}

void LoLXMPPDebugger::onFinishRequest(QNetworkReply* response)
{
	QByteArray content = response->readAll();
	qDebug() << "Http Received: " << response->url().toString() << QString(content);

	for (QTcpSocket* socket : clients)
	{
		socket->write(content);
	}
}

void LoLXMPPDebugger::newConnection()
{
	/*qDebug() << server->nextPendingConnection()->localAddress();
	QTcpSocket *connection = server->nextPendingConnection();
	if (socket->bytesAvailable() > 0)
	{
		QByteArray bytes = connection->readAll();
		ui.incomingList->addItem(bytes);
	}*/

}

LoLXMPPDebugger::~LoLXMPPDebugger()
{
	socket->disconnect();
	server->close();
}

void LoLXMPPDebugger::on_pushButton_LaunchLeague_clicked()
{
	QString riotClientPath;

	// TODO: Find a better way of getting ProgramData dir
	QFile file("C:/ProgramData/Riot Games/RiotClientInstalls.json");
	if (!file.open(QFile::ReadOnly | QFile::Text))
	{
		ui.statusBar->showMessage("Failed to get Riot Client path", 10000);
		return;
	}
	else
	{
		QByteArray jsonData = file.readAll();
		QJsonParseError jsonError;
		QJsonDocument document = QJsonDocument::fromJson(jsonData, &jsonError);
		if (jsonError.error != QJsonParseError::NoError)
		{
			ui.statusBar->showMessage("Unable to get Riot Client path", 10000);
			return;
		}
		if (document.isObject())
		{
			QJsonObject jsonObj = document.object();
			riotClientPath = jsonObj.value("rc_default").toString();
		}
	}
	file.close();

	std::string configUrl = std::format(R"("http://127.0.0.1:{}")", port);
	QString temp = QString::fromStdString(configUrl);
	//QStringList args = {temp, "--launch-product=league_of_legends", "--launch-patchline=live"
	//	,"--client-config-url=", QString::number(port)/*, "--allow-multiple-clients"*/};
	QStringList args;
	args << "--launch-product=league_of_legends" << "--launch-patchline=live"
	 << QString::fromStdString(std::format("--client-config-url=http://127.0.0.1:{}", port));
	QProcess *league = new QProcess(this);
	league->startDetached(riotClientPath, args);
	ui.statusBar->showMessage("Launching Riot Client", 5000);
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