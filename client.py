import ctypes
import time
import threading
import sys
import datetime
import socket
import os
import csv
from plyer import notification
import winsound
import tkinter as tk
from tkinter import simpledialog, scrolledtext, messagebox

# ----- 設定値 -----
DLL_PATH = r"C:\\Users\\c0a22\\Downloads\\felicalib-0.4.2\\felicalib-0.4.2\\felicalib.dll"
SERVER_IP = "192.168.100.179"
SERVER_PORT = 12345
ENTRY_TIMEOUT = 30
RETRY_LOG_FILE = "retry_log.csv"
PASORI_SUCCESS = 0

# ----- 状態保持 -----
entry_state = {}
id_name_map = {}
server_available = True

# ----- FeliCa構造体定義 -----
class Felica(ctypes.Structure):
    _fields_ = [
        ("handle", ctypes.c_void_p),
        ("idm", ctypes.c_ubyte * 8),
        ("pmm", ctypes.c_ubyte * 8),
        ("system_code", ctypes.c_ushort)
    ]

def check_server_connection():  # ★追加
    try:
        with socket.create_connection((SERVER_IP, SERVER_PORT), timeout=5):
            return True
    except Exception:
        return False
    
def connection_monitor():  # ★追加
    global server_available
    wait_interval = 60
    while True:
        is_connected = check_server_connection()
        if is_connected:
            if not server_available:
                print("[再接続] サーバーとの接続が復旧しました。retry_logを再送します。")
                retry_unsent_logs()
            server_available = True
            wait_interval = min(wait_interval * 2, 1800)
        else:
            if server_available:
                print("[切断検知] サーバーに接続できません。ローカルモードに切り替えます。")
            server_available = False
            wait_interval = 300
        time.sleep(1800)  # 30分ごと

# ----- ログファイル名取得（当日ログ） -----
def get_log_filename(date=None):
    if date is None:
        date = datetime.date.today()
    return f"entry_log_{date.strftime('%Y-%m-%d')}.csv"

# ----- ログから状態復元機能を追加 -----
def load_entry_state_from_log():
    global entry_state, id_name_map
    # 当日ログファイル名取得（直近のファイルを自分で複数日対応したい場合は拡張可能）
    log_filename = get_log_filename()
    if not os.path.exists(log_filename):
        print(f"[復元] ログファイル {log_filename} が見つかりません。状態復元はスキップします。")
        return

    try:
        with open(log_filename, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                idm = row["idm"]
                name = row["name"]
                action = row["action"]
                # 入室なら True、退室なら False として状態セット
                entry_state[idm] = (action == "入室")
                id_name_map[idm] = name
        print(f"[復元] {log_filename} から入退室状態を復元しました。")
    except Exception as e:
        print(f"[復元] ログ復元中にエラーが発生しました: {e}")

def load_retry_state():
    global entry_state, id_name_map
    if not os.path.exists(RETRY_LOG_FILE):
        return
    try:
        with open(RETRY_LOG_FILE, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 6:
                    continue
                _, _, idm, name, action, _ = row
                entry_state[idm] = (action == "入室")
                id_name_map[idm] = name
        print("[復元] retry_log.csv から一時状態を補完しました。")
    except Exception as e:
        print(f"[復元] retry_log.csvの読み込みエラー: {e}")

# ----- ログ保存 -----
def save_log(scan_time, send_time, idm, name, action, status="OK"):
    try:
        # "IN" → "入室", "OUT" → "退室" に変換
        action_disp = action  # 既に変換済 or 異常値の保険

        date_str = scan_time.strftime("%Y-%m-%d")
        log_filename = f"entry_log_{date_str}.csv"
        file_exists = os.path.isfile(log_filename)

        with open(log_filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["scan_time", "send_time", "idm", "name", "action", "status"])
            writer.writerow([
                scan_time.strftime("%Y-%m-%d %H:%M:%S"),
                send_time.strftime("%Y-%m-%d %H:%M:%S"),
                idm,
                name.replace("，", "").replace(",", ""),  # 安全処理（全角カンマ対策）
                action_disp,
                status
            ])
    except Exception as e:
        print(f"[save_log] エラー: {e}")

# ----- 再送用ログ保存 -----
def save_retry_log(scan_time, send_time, idm, name, action, status="FAILED"):
    try:
        with open(RETRY_LOG_FILE, "a", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                scan_time.strftime("%Y-%m-%d %H:%M:%S"),
                send_time.strftime("%Y-%m-%d %H:%M:%S"),
                idm, name, action, status
            ])
    except Exception as e:
        print(f"[save_retry_log] エラー: {e}")

def retry_unsent_logs():
    if not os.path.exists(RETRY_LOG_FILE):
        return

    temp_rows = []
    with open(RETRY_LOG_FILE, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) != 6:
                print(f"[警告] 想定外の列数: {row}")
                continue
            scan_str, send_str, idm, name, action, status = row
            try:
                message = f"ENTRY_EVENT,{idm},{name},{action},{scan_str}"
                with socket.create_connection((SERVER_IP, SERVER_PORT), timeout=5) as sock:
                    sock.sendall(message.encode("utf-8"))
                    response = sock.recv(1024).decode("utf-8").strip()
                    print(f"[受信レスポンス] {repr(response)}")

                    if response == "ENTRY_EVENT_OK":
                        scan_time = datetime.datetime.strptime(scan_str, "%Y-%m-%d %H:%M:%S")
                        send_time = datetime.datetime.now()
                        save_log(scan_time, send_time, idm, name, action, status="OK")
                        print(f"[再送成功] {idm} {name} {action}")
                    elif response == "NOT_REGISTERED":
                        print(f"[再送失敗] 未登録: {idm}")

                        # 名前がある場合は自動登録を試みる
                        if name:
                            reg_res = communicate_with_server(idm, name=name, register=True)
                            print(f"[自動登録レスポンス] {reg_res}")
                            if reg_res == "REGISTERED_SUCCESS":
                                print(f"[自動登録成功] {idm} {name}")

                                # 再送を再試行
                                try:
                                    retry_msg = f"ENTRY_EVENT,{idm},{name},{action},{scan_str}"
                                    with socket.create_connection((SERVER_IP, SERVER_PORT), timeout=5) as sock2:
                                        sock2.sendall(retry_msg.encode("utf-8"))
                                        response2 = sock2.recv(1024).decode("utf-8").strip()
                                        if response2 == "ENTRY_EVENT_OK":
                                            scan_time = datetime.datetime.strptime(scan_str, "%Y-%m-%d %H:%M:%S")
                                            send_time = datetime.datetime.now()
                                            save_log(scan_time, send_time, idm, name, action, status="OK")
                                            print(f"[再送成功（登録後）] {idm} {name} {action}")
                                            continue  # 成功したので temp_rows に入れない
                                except Exception as e:
                                    print(f"[再送処理エラー（登録後）] {e}")
                        temp_rows.append(row)  # 自動登録不可 or 再送失敗
                    else:
                        print(f"[再送失敗] サーバー応答: {response}")
                        temp_rows.append(row)
            except Exception as e:
                print(f"[再送処理エラー] {e}")
                temp_rows.append(row)

    with open(RETRY_LOG_FILE, "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(temp_rows)

# ----- 入室者状態表示（コンソール） -----
def print_current_status(entry_state, id_name_map):
    inside = [idm for idm, state in entry_state.items() if state]
    print(f"現在入室中の人数: {len(inside)}")
    for idm in inside:
        name = id_name_map.get(idm, "不明")
        print(f" - {name} ({idm})")

# ----- 未登録ID入力GUI -----
def prompt_for_name(idm):
    root = tk.Tk()
    root.withdraw()
    root.after(0, root.deiconify)
    try:
        name = simpledialog.askstring("未登録ID検出", f"IDm {idm} の名前を入力してください:", parent=root)
    finally:
        root.destroy()
    return name

# ----- サーバー通信 -----
def communicate_with_server(idm, name=None, register=False, entry_event=None, retries=3, retry_delay=2):
    if not server_available:
        return None
    msg = ""
    if register and name:
        msg = f"REGISTER,{idm},{name}"
    elif entry_event:
        safe_name = name.replace(",", "，")
        msg = f"ENTRY_EVENT,{idm},{safe_name},{entry_event}"
    else:
        msg = f"CHECK,{idm}"

    for attempt in range(1, retries + 1):
        try:
            with socket.create_connection((SERVER_IP, SERVER_PORT), timeout=10) as sock:
                sock.sendall(msg.encode())
                response = sock.recv(1024).decode()
                return response.strip()
        except Exception as e:
            print(f"[{attempt}/{retries}] サーバー通信エラー: {e}")
            if attempt < retries:
                print(f" {retry_delay}秒後に再試行...")
                time.sleep(retry_delay)
    return None

# ----- サーバーログ取得 -----
def get_server_log():
    try:
        with socket.create_connection((SERVER_IP, SERVER_PORT), timeout=5) as sock:
            sock.sendall(b"GET_LOG")
            log_data = b""
            while True:
                part = sock.recv(4096)
                if not part:
                    break
                log_data += part
            return log_data.decode("utf-8")
    except Exception as e:
        return f"通信エラー: {e}"

def show_server_log():
    log_text = get_server_log()
    window = tk.Toplevel()
    window.title("サーバーログ閲覧")
    window.geometry("1200x800")  # サイズ追加

    st = scrolledtext.ScrolledText(window, width=150, height=40, font=("Meiryo", 12))
    st.pack(fill="both", expand=True)
    st.insert("1.0", log_text)
    st.config(state="disabled")


# ----- 入室者一覧表示 -----
def show_entry_list():
    window = tk.Toplevel()
    window.title("現在の入室者一覧")
    window.geometry("600x800")

    label = tk.Label(window, text="※10秒ごとに自動更新", fg="blue", font=("Meiryo", 12))
    label.pack(pady=10)

    listbox = tk.Listbox(window, width=50, height=30, font=("Meiryo", 14))
    listbox.pack(padx=20, pady=10)

    def update_list():
        listbox.delete(0, tk.END)
        inside = [idm for idm, state in entry_state.items() if state]
        for idm in inside:
            name = id_name_map.get(idm, "不明")
            listbox.insert(tk.END, f"{name} ({idm})")
        window.after(10000, update_list)

    update_list()

# ----- GUI起動 -----
def start_gui():
    root = tk.Tk()
    root.title("入退室管理システム クライアント")
    tk.Button(root, text="サーバーログを表示", command=show_server_log).pack(padx=20, pady=10)
    tk.Button(root, text="現在の入室者を表示", command=show_entry_list).pack(padx=20, pady=10)
    root.mainloop()

# ----- 通知表示 -----
def notify_user(title, message):
    try:
        notification.notify(
            title=title,
            message=message,
            timeout=3  # 秒数
        )
    except Exception as e:
        print(f"[通知エラー] {e}")

# ----- 音声通知 -----
def play_notification_sound():
    try:
        winsound.Beep(700, 800)
    except Exception as e:
        print(f"[音声通知エラー] {e}")

# ----- カード読み取りループ -----
def card_reader_loop():
    global entry_state, id_name_map
    last_seen = {}

    try:
        felicalib = ctypes.WinDLL(DLL_PATH)
    except Exception as e:
        print(f"felicalib.dllの読み込みに失敗: {e}")
        sys.exit(1)

    pasori = felicalib.pasori_open()
    if not pasori:
        print("PaSoRiが開けません。接続確認してください。")
        sys.exit(1)

    if felicalib.pasori_init(pasori) != PASORI_SUCCESS:
        print("PaSoRi初期化失敗")
        felicalib.pasori_close(pasori)
        sys.exit(1)

    print("カードをかざしてください...")

    retry_unsent_logs()  # 起動時に未送信ログの再送処理

    try:
        while True:
            card_ptr = felicalib.felica_polling(pasori, 0xFFFF, 0, 0)
            now_time = time.time()
            if card_ptr:
                felica = Felica.from_address(card_ptr)
                idm = ''.join(f"{byte:02X}" for byte in felica.idm)

                if idm in last_seen and (now_time - last_seen[idm]) < ENTRY_TIMEOUT:
                    time.sleep(0.1)
                    continue
                last_seen[idm] = now_time

                response = communicate_with_server(idm)
                if response is None:
                    print("通信失敗（CHECK）→ ローカル処理へ")
                    name = id_name_map.get(idm, "不明")  # 既知の名前があれば使用、なければ仮で記録
                    if name == "不明":
                        name = prompt_for_name(idm)
                        if name:
                            id_name_map[idm] = name
                        else:
                            print("名前が取得できず、処理中断")
                            continue

    # 入退室トグル処理
                    current_status = entry_state.get(idm, False)
                    new_status = not current_status
                    action_str = "入室" if new_status else "退室"
                    scan_time = datetime.datetime.now()
                    send_time = scan_time  # 通信しないので同時刻でOK

                    save_log(scan_time, send_time, idm, name, action_str, status="LOCAL")
                    save_retry_log(scan_time, send_time, idm, name, action_str)
                    entry_state[idm] = new_status

                    notify_user(f"{name}さん", f"{action_str}（ローカル記録）")
                    play_notification_sound()
                    continue  # この後の処理はスキップ


                if response.startswith("REGISTERED"):
                    name = response.split(",", 1)[-1]
                    id_name_map[idm] = name
                elif response == "NOT_REGISTERED":
                    print(f"未登録ID: {idm}")
                    name = prompt_for_name(idm)
                    if name:
                        print(f"登録開始: ID={idm}, 名前={name}")
                        res = communicate_with_server(idm, name=name, register=True)
                        print(f"登録レスポンス: {res}")  # 追加ログ
                        if res == "REGISTERE_SUCCESS":
                            id_name_map[idm] = name
                            print(f"{name} さんを登録しました。")
                        else:
                            print("登録失敗")
                            continue
                    else:
                        print("名前入力キャンセル")
                        continue
                else:
                    print(f"予期せぬレスポンス: {response}")
                    continue

                # 入退室トグル処理
                current_status = entry_state.get(idm, False)
                new_status = not current_status
                action_str = "入室" if new_status else "退室"

                # スキャン時刻はカード読み取り直後に取得
                scan_time = datetime.datetime.now()
                
                # サーバーへ送信
                send_response = communicate_with_server(idm, name=id_name_map[idm], entry_event=action_str)
                send_time = datetime.datetime.now()

                if send_response == "ENTRY_EVENT_OK" or send_response.startswith("REGISTERED"):
                    print(f"{name} さんの{action_str}を記録しました。")
                    entry_state[idm] = new_status
                    save_log(scan_time, send_time, idm, id_name_map[idm], action_str)

                    notify_user(f"{name}さん", f"{action_str}が記録されました")
                    play_notification_sound()

                elif send_response is None:  # ★追加：ローカルモード用
                    print(f"[ローカル記録] {name} さんの {action_str} を記録（サーバー未接続）")
                    save_log(scan_time, send_time, idm, name, action_str, status="LOCAL")
                    save_retry_log(scan_time, send_time, idm, name, action_str)
                    notify_user(f"{name}さん", f"{action_str}（ローカル記録）")
                    play_notification_sound()
                    entry_state[idm] = new_status
                
                else:
                    print(f"[受信レスポンス] {repr(send_response)}")
                    print(f"送信失敗、retry_logに記録します。")
                    save_retry_log(scan_time, send_time, idm, id_name_map[idm], action_str)

                    # === 追加：ローカルでも処理する ===
                    entry_state[idm] = new_status
                    save_log(scan_time, send_time, idm, id_name_map[idm], action_str, status="FAILED")
    
                    notify_user(f"{name}さん", f"{action_str}（ローカル記録）")
                    play_notification_sound()
            else:
                time.sleep(0.1)

    finally:
        felicalib.pasori_close(pasori)

def force_exit_process():
    while True:
        now = datetime.datetime.now()
        if now.hour == 20 and now.minute == 0:
            print("[強制退室] 20時になったため強制退室処理を実行します。")
            for idm, status in list(entry_state.items()):
                if status:  # 入室中の人だけ退室処理
                    name = id_name_map.get(idm, "不明")
                    scan_time = datetime.datetime.now()
                    action_str = "退室"
                    send_response = communicate_with_server(idm, name=name, entry_event=action_str)
                    send_time = datetime.datetime.now()

                    if send_response == "ENTRY_EVENT_OK":
                        entry_state[idm] = False
                        save_log(scan_time, send_time, idm, name, action_str)
                        print(f"[強制退室] {name} さんを退室処理しました。")
                    else:
                        print(f"[強制退室失敗] {name} → retry_logに記録")
                        save_retry_log(scan_time, send_time, idm, name, action_str)

            # 重複実行を避けるため1分間スリープ
            time.sleep(60)
        time.sleep(5)

def sync_log_from_server():
    try:
        with socket.create_connection((SERVER_IP, SERVER_PORT), timeout=15) as s:
            s.settimeout(15)
            s.sendall("GET_LOG".encode())
            buffer = b""
            while True:
                try:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    buffer += chunk
                except socket.timeout:
                    print("[同期] 受信タイムアウト発生")
            log_data = buffer.decode("utf-8", errors="ignore")
            if log_data:
                with open(f"entry_log_{datetime.date.today().strftime('%Y-%m-%d')}.csv", "w", encoding="utf-8") as f:
                    f.write(log_data)
                print("[同期] サーバーログ取得完了")
                return True
            else:
                print("[同期] サーバーログ空")
                return False
    except Exception as e:
        print(f"[同期] サーバーログ取得エラー: {e}")
        return False

def retry_loop():
    while True:
        if not os.path.exists(RETRY_LOG_FILE):
            time.sleep(300)  # 5分スリープ（ログがなければ頻繁に確認しない）
            continue

        with open(RETRY_LOG_FILE, newline='', encoding='utf-8') as f:
            lines = f.readlines()

        if len(lines) <= 1:
            time.sleep(300)  # 見出し以外の未送信データがなければスリープ延長
        else:
            retry_unsent_logs()
            time.sleep(30)  # 未送信があるなら頻度高くチェック

def start_retry_thread():
    def retry_loop():
        while True:
            retry_unsent_logs()
            time.sleep(30)
    t = threading.Thread(target=retry_loop, daemon=True)
    t.start()

# ----- メイン関数 -----
def main():
    synced = sync_log_from_server()
    if synced:
        load_entry_state_from_log()  # サーバーのログに基づいて復元
    else:
        load_entry_state_from_log()  # ローカルのログに基づいて復元
        load_retry_state()           # 未送信分も補完

    # GUIスレッド起動
    gui_thread = threading.Thread(target=start_gui, daemon=True)
    gui_thread.start()

    # 再送スレッド
    retry_thread = threading.Thread(target=retry_loop, daemon=True)
    retry_thread.start()
    start_retry_thread()

    # 強制退室スレッド
    force_exit_thread = threading.Thread(target=force_exit_process, daemon=True)
    force_exit_thread.start()

    # 接続監視スレッド（30分ごとにチェック）
    conn_thread = threading.Thread(target=connection_monitor, daemon=True)  # ★追加
    conn_thread.start()

    # カード読み取りループ（メインスレッド）
    card_reader_loop()

if __name__ == "__main__":
    main()
