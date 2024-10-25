import os, asyncio, re, requests, datetime
from UiObjects import *


class ValoLogWatcher:
    def __init__(self, auth, entitlements):
        self.auth = auth
        self.entitlements = entitlements

    async def run(self):
        log_path = os.getenv('LOCALAPPDATA') + r"\VALORANT\Saved\Logs\ShooterGame.log"
        if not os.path.exists(log_path):
            print(f"File {log_path} does not exist.")
            return

        valapi = requests.get("https://valorant-api.com/v1/version").json()
        headers = {
            "User-Agent": "ShooterGame/" + valapi["data"]["buildVersion"] + " Windows/10.0.19042.1.256.64bit",
            "X-Riot-ClientPlatform": "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9",
            "X-Riot-ClientVersion": valapi["data"]["riotClientVersion"],
            "X-Riot-Entitlements-JWT": self.entitlements,
            "Authorization": self.auth
        }

        with open(log_path, 'r', encoding='utf-8') as file:
            last_known_line = file.readline()

            while True:
                file.seek(0, 0)
                current_first_line = file.readline()

                # first line changed, new logs
                if current_first_line != last_known_line:
                    last_known_line = current_first_line

                    file.seek(0, 2)

                    while True:
                        line = file.readline()
                        if not line:
                            await asyncio.sleep(0.1)
                            continue

                        new_log_entry = line.strip()

                        if "server version: " in new_log_entry:
                            match = re.search(r"server version: (.+)", new_log_entry)
                            if match:
                                headers["X-Riot-ClientVersion"] = match.group(1)

                        if "Build version: " in new_log_entry:
                            match = re.search(r"Build version: (.+)", new_log_entry)
                            if match:
                                build = match.group(1)
                                headers["User-Agent"] = "ShooterGame/" + build + " Windows/10.0.19042.1.256.64bit"

                        if "Platform HTTP Query End" in new_log_entry:
                            query_name, method, url, response_code = self.extract_details(new_log_entry)
                            #print(f"Query Name: {query_name}, Method: {method}, URL: {url}, Response Code: {response_code}")
                            response = None
                            # todo, lags app on 404 i think
                            if method == "GET" and UiObjects.valoCallGets.isChecked():
                                response = requests.request(method, url, headers=headers)
                            await ValoLogWatcher.log_message(query_name, method, url, response_code, headers, response)

                await asyncio.sleep(0.1)

    def extract_details(self, log_entry):
        pattern = r"QueryName: \[([^\]]+)\], URL \[([A-Z]+) (https?://[^\]]+)\],.*Response Code: \[(\d{0,3})\]"
        match = re.search(pattern, log_entry)
        if match:
            query_name = match.group(1)
            method = match.group(2)
            url = match.group(3)
            response_code = match.group(4)
            return query_name, method, url, response_code
        print("[Valo] Something wrong: ", log_entry)
        return None, None, None, None

    @staticmethod
    async def log_message(query_name, method, url, response_code, headers, response=None):
        item = QListWidgetItem()
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        if response:
            text = f"[{current_time}] {str(response_code)}{f' ({str(response.status_code.real)})' if str(response.status_code.real) != str(response_code) else ''} {method} {url}   {query_name}"
        else:
            text = f"[{current_time}] {str(response_code)} {method} {url}   {query_name}"
        item.setText(text)
        data = f"{method} {url} HTTP/1.1\r\nHost: {requests.compat.urlparse(url).netloc}\r\n"
        for key in headers:
            data += f"{key}: {headers[key]}\r\n"
        data += "\r\n\r\n\r\n"

        if response != None:
            raw_response_str = to_raw_response(response).decode()
            try:
                if "Content-Type" in response.headers and response.status_code.real != 204:
                    try:
                        raw_response_split = raw_response_str.split("\r\n\r\n")
                        raw_response_str = raw_response_split[0] + "\r\n\r\n" + json.dumps(
                            json.loads(raw_response_split[1]), indent=4)
                    except Exception:
                        pass
                data += "\r\n\r\n" + raw_response_str
            except Exception as e:
                print("valo log_message error", e)
                print(raw_response_str)

        item.setData(256, data)

        scrollbar = UiObjects.valoList.verticalScrollBar()
        if not scrollbar or scrollbar.value() == scrollbar.maximum():
            UiObjects.valoList.addItem(item)
            UiObjects.valoList.scrollToBottom()
        else:
            UiObjects.valoList.addItem(item)