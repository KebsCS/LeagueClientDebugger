#include "LoLXMPPDebugger.h"
#include <QtWidgets/QApplication>

int main(int argc, char* argv[])
{
	QApplication a(argc, argv);
	LoLXMPPDebugger w;
	w.show();
	return a.exec();
}