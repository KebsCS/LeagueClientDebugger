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
	// start a server on open port
	server = new QTcpServer(this);
	if (!server->listen(QHostAddress::Any, port))
	{
		qDebug() << "Couldnt start server";
	}
	else
	{
		qDebug() << "Server started on port " << port;
	}

	connect(server, SIGNAL(newConnection()), this, SLOT(onNewConnection()));

	ui.statusBar->showMessage("Proxy server started.", 10000);
}

void LoLXMPPDebugger::onNewConnection()
{
	QTcpSocket* clientSocket = server->nextPendingConnection();
	connect(clientSocket, SIGNAL(readyRead()), this, SLOT(onReadyRead()));
	connect(clientSocket, SIGNAL(stateChanged(QAbstractSocket::SocketState)), this, SLOT(onSocketStateChanged(QAbstractSocket::SocketState)));

	clients.push_back(clientSocket);
	qDebug() << clientSocket->peerAddress().toString() << " connected to server";
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
	// proxied client request
	QTcpSocket* sender = static_cast<QTcpSocket*>(QObject::sender());
	QString response = sender->readAll();
	leagueSocket = sender;
	qDebug() << "Server received: " << response;
	QStringList buf = QString(response).split(' ');


	// send proxied request to real server
	QNetworkAccessManager* manager = new QNetworkAccessManager(this);
	connect(manager, SIGNAL(finished(QNetworkReply*)), this, SLOT(onFinishRequest(QNetworkReply*)));
	connect(manager, SIGNAL(finished(QNetworkReply*)), manager, SLOT(deleteLater()));

	QString url = clientConfigUrl + buf.at(1);
	QNetworkRequest request(url);
	request.setHeader(QNetworkRequest::KnownHeaders::ContentTypeHeader, "application/json");

	QRegularExpression userAgent(R"((?<=user-agent: )([a-z/A-Z0-9.\ \-\(\;\,\)]+))");
	QRegularExpressionMatch match = userAgent.match(response);
	if (match.hasMatch())
	{
		request.setHeader(QNetworkRequest::KnownHeaders::UserAgentHeader, match.captured());
	}

	QRegularExpression acceptEncoding(R"((?<=Accept-Encoding: )([a-z/A-Z0-9.\ \-\(\;\,\)]+))");
	match = acceptEncoding.match(response);
	if (match.hasMatch())
	{
		request.setRawHeader(QByteArray("Accept-Encoding"), match.captured().toUtf8());
	}

	QRegularExpression entitlements(R"((?<=X-Riot-Entitlements-JWT: )([a-z/A-Z0-9.\ \-\(\;\,\)\_]+))");
	match = entitlements.match(response);
	if (match.hasMatch())
	{
		request.setRawHeader(QByteArray("X-Riot-Entitlements-JWT"), match.captured().toUtf8());
	}

	QRegularExpression authorization(R"((?<=Authorization: )([a-z/A-Z0-9.\ \-\(\;\,\)\_]+))");
	match = authorization.match(response);
	if (match.hasMatch())
	{
		request.setRawHeader(QByteArray("Authorization"), match.captured().toUtf8());
	}

	QRegularExpression identify(R"((?<=X-Riot-RSO-Identity-JWT: )([a-z/A-Z0-9.\ \-\(\;\,\)\_]+))");
	match = identify.match(response);
	if (match.hasMatch())
	{
		request.setRawHeader(QByteArray("X-Riot-RSO-Identity-JWT"), match.captured().toUtf8());
	}

	QRegularExpression accept(R"((?<=Accept: )([a-z/A-Z0-9.\ \-\(\;\,\)]+))");
	match = accept.match(response);
	if (match.hasMatch())
	{
		request.setRawHeader(QByteArray("Accept"), match.captured().toUtf8());
	}

	manager->get(request);
}

void LoLXMPPDebugger::onFinishRequest(QNetworkReply* response)
{
	// modify and send the real server response back to client
	QByteArray content = response->readAll();

	QJsonObject object = QJsonDocument::fromJson(content).object();
	if (!object.value("chat.host").isUndefined())
	{
		object["chat.host"] = QString("127.0.0.1");
	}
	if (!object.value("chat.port").isUndefined())
	{
		object["chat.port"] = port;
	}
	if (!object.value("chat.allow_bad_cert.enabled").isUndefined())
	{
		object["chat.allow_bad_cert.enabled"] = true;
	}
	if (!object.value("chat.affinities").isUndefined())
	{
		QJsonObject chatAffinities = object["chat.affinities"].toObject();
		foreach (const QString& key, chatAffinities.keys())
		{
			chatAffinities[key] = QString("127.0.0.1");
		}

		object["chat.affinities"] = chatAffinities;
	}


	content = QJsonDocument(object).toJson();
	
	qDebug() << "HTTP Received: " << response->url().toString() << QString(content) << response->rawHeaderList();

	QString message = QString("HTTP/1.1 200 OK\r\n") +
		QString("Content-Length: ") + QString::number(content.length()) + QString("\r\n") +
		QString("Content-Type: application/json\r\n") +
		QString("\r\n") + QString(content);
	leagueSocket->write(message.toUtf8());
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

	QStringList args;
	args << "--launch-product=league_of_legends" << "--launch-patchline=live"
		<< QString::fromStdString(std::format("--client-config-url=http://127.0.0.1:{}", port));
	QProcess* league = new QProcess(this);
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