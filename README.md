![Example](https://i.imgur.com/riDrBoc.png)

## Features
* See all requests the Riot Client and Riot's games send and receive - HTTP/S, RMS (riot messaging service), XMPP (chat), RTMP (custom games) and websockets
* Works on League of Legends, Valorant, Teamfight Tactics and Legends of Runeterra
* Modify the requests to change how the client works, eg. disable vanguard
* LCU and Riot Client websocket connection
* Send custom requests directly to the server or straight to client
* Fiddler or other HTTP proxy integration
* Run client with custom command line arguments, eg. LCU on any port you want
* Custom hosts blocklist to disable telemetry and tracking
* Disable OpenSSL verification certificate errors and see the client logs


## Installation
1. Clone or download the repository
2. Open Windows Command Prompt (**CMD**)
3. Run `cd LeagueClientDebugger`
4. `pip install -r requirements.txt`
5. Close all running League and Riot clients
6. `python main.py`, tested on python 3.9.7 and 3.12.3
7. Select your server and press the `Launch Client` button 



## Discord
Feel free to ask any questions regarding this project, or league client on my [discord server](https://discord.gg/qMmPBFpj2n), although I won't be teaching you how to code there if you're a complete beginner