import socket
import threading
import csv
import os
import datetime
import time
import json

# ====== 設定 ======
HOST = '0.0.0.0'
PORT = 12345
USER_CSV = "user_data.csv"
ENTRY_STATE_FILE = "entry_state.json"
MISSED_EXIT_FILE = "missed_exit.json"

lock = threading.Lock()
entry_state = {}


# ====== ユーザー情報の読み書き ======
def load_users():
    users = {}
    if os.path.exists(USER_CSV):
        with open(USER_CSV, newline='', encoding='utf-8') as f:
            for row in csv.reader(f):
                if len(row) >= 2:
                    users[row[0]] = row[1]
    return users


def register_user(users, idm, name):
    with lock:
        if idm in users:
            return False
        users[idm] = name
        with open(USER_CSV, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([idm, name])
        return True


# ====== 入退室状態の保存・復元 ======
def load_entry_state():
    global entry_state
    if os.path.exists(ENTRY_STATE_FILE):
        try:
            with open(ENTRY_STATE_FILE, "r", encoding="utf-8") as f:
                entry_state = json.load(f)
        except Exception as e:
            print(f"[load_entry_state] エラー: {e}")
            entry_state = {}
    else:
        entry_state = {}


def save_entry_state():
    try:
        with open(ENTRY_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(entry_state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[save_entry_state] エラー: {e}")


# ====== ログ保存 ======
def save_log(idm, name, action, scan_timestamp=None):
    try:
        if scan_timestamp:
            try:
                now = datetime.datetime.strptime(scan_timestamp, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                now = datetime.datetime.now()
        else:
            now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        date_str = now.strftime("%Y-%m-%d")
        log_filename = f"entry_log_{date_str}.csv"

        file_exists = os.path.isfile(log_filename)
        with open(log_filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["timestamp", "idm", "name", "action"])
            writer.writerow([timestamp, idm, name, action])
    except Exception as e:
        print(f"[save_log] エラー: {e}")


# ====== 退室漏れ通知と強制退室処理 ======
def show_missed_exit_users():
    if os.path.exists(MISSED_EXIT_FILE):
        try:
            with open(MISSED_EXIT_FILE, "r", encoding="utf-8") as f:
                missed = json.load(f)
            if missed:
                print("【前回の退室処理忘れユーザー】")
                for record in missed:
                    print(f"- {record['name']} ({record['idm']}) at {record['timestamp']}")
            else:
                print("前回の退室忘れなし")
        except Exception as e:
            print(f"[show_missed_exit_users] エラー: {e}")
        os.remove(MISSED_EXIT_FILE)


def force_checkout_all(users):
    now = datetime.datetime.now()
    print(f"{now.strftime('%Y-%m-%d %H:%M:%S')} 全員退室処理実行")
    missed = []

    with lock:
        for idm, state in entry_state.items():
            if state:
                entry_state[idm] = False
                name = users.get(idm, "不明")
                save_log(idm, name, "退室")
                missed.append({
                    "idm": idm,
                    "name": name,
                    "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")
                })

        save_entry_state()

    if missed:
        with open(MISSED_EXIT_FILE, "w", encoding="utf-8") as f:
            json.dump(missed, f, ensure_ascii=False, indent=2)


def daily_checker(users):
    while True:
        now = datetime.datetime.now()
        if now.hour == 20 and now.minute == 0:
            force_checkout_all(users)
            time.sleep(60)  # 1分間隔で重複実行防止
        time.sleep(10)


# ====== クライアント処理 ======
def handle_client(conn, addr, users):
    print(f"{addr} 接続")
    try:
        with conn:
            while True:
                data = conn.recv(4096)
                if not data:
                    break
                parts = data.decode(errors='ignore').strip().split(',', 4)
                cmd = parts[0].strip()

                if cmd == "CHECK" and len(parts) >= 2:
                    idm = parts[1]
                    with lock:
                        if idm in users:
                            state = entry_state.get(idm, False)
                            name = users[idm]
                            status = "IN" if state else "OUT"
                            conn.sendall(f"REGISTERED,{name},{status}".encode())
                        else:
                            conn.sendall(b"NOT_REGISTERED")

                elif cmd == "REGISTER" and len(parts) == 3:
                    idm, name = parts[1], parts[2]
                    success = register_user(users, idm, name)
                    conn.sendall(b"REGISTER_SUCCESS" if success else b"REGISTER_FAIL")

                elif cmd in ["ENTER", "EXIT"] and len(parts) == 2:
                    idm = parts[1]
                    with lock:
                        if idm in users:
                            entry_state[idm] = (cmd == "ENTER")
                            save_entry_state()
                            action = "入室" if cmd == "ENTER" else "退室"
                            save_log(idm, users[idm], action)
                            conn.sendall(f"{cmd}_OK".encode())
                        else:
                            conn.sendall(b"NOT_REGISTERED")

                elif cmd == "ENTRY_EVENT" and (len(parts) == 4 or len(parts) == 5):
                    idm, name, action = parts[1], parts[2], parts[3]
                    scan_timestamp = parts[4] if len(parts) == 5 else None
                    with lock:
                        if idm in users:
                            if action in ["入室", "IN"]:
                                entry_state[idm] = True
                                action_log = "入室"
                            elif action in ["退室", "OUT"]:
                                entry_state[idm] = False
                                action_log = "退室"
                            else:
                                conn.sendall(b"ENTRY_EVENT_FAIL")
                                return

                            save_entry_state()
                            save_log(idm, name, action, scan_timestamp)
                            conn.sendall(b"ENTRY_EVENT_OK")
                        else:
                            conn.sendall(b"NOT_REGISTERED")

                elif cmd == "GET_ENTRY_STATE":
                    with lock:
                        entries = [
                            {"idm": idm, "name": users.get(idm, "不明"), "state": "IN" if state else "OUT"}
                            for idm, state in entry_state.items()
                        ]
                        data = json.dumps(entries, ensure_ascii=False)
                        conn.sendall(data.encode("utf-8"))

                elif cmd == "GET_LOG":
                    print(f"[GET_LOG] {addr} からのログ取得リクエスト")
                    today_str = datetime.date.today().strftime("%Y-%m-%d")
                    log_filename = f"entry_log_{today_str}.csv"
                    if os.path.exists(log_filename):
                        with open(log_filename, "r", encoding="utf-8") as f:
                            log_content = f.read()
                        conn.sendall(log_content.encode("utf-8"))
                    else:
                        conn.sendall("".encode("utf-8"))
                    try:
                        conn.shutdown(socket.SHUT_WR)
                    except Exception as e:
                        print(f"[GET_LOG] shutdownエラー: {e}")
                else:
                    conn.sendall(b"UNKNOWN_COMMAND")

    except Exception as e:
        print(f"[handle_client] 通信エラー: {e}")
    finally:
        print(f"{addr} 切断")


# ====== メイン処理 ======
if __name__ == "__main__":
    users = load_users()
    show_missed_exit_users()
    load_entry_state()

    threading.Thread(target=daily_checker, args=(users,), daemon=True).start()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"サーバー起動: {HOST}:{PORT}")
        while True:
            try:
                conn, addr = s.accept()
                threading.Thread(target=handle_client, args=(conn, addr, users), daemon=True).start()
            except Exception as e:
                print(f"[main] 接続受付エラー: {e}")
