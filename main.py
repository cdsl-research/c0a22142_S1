import socket
import time
import network
from machine import Pin, time_pulse_us, RTC

# --- Wi-Fi設定 ---
SSID = 'Wi-FIのSSID'
PASSWORD = 'Wi-Fiのパスワード'
PC_IP = "PCのIPアドレス"
PC_PORT = 50000

# PIRセンサー（HW-416-B）
pir = Pin(4, Pin.IN)
led = Pin(2, Pin.OUT)  # 動作確認用LED

# 超音波センサー（HC-SR04）
trig = Pin(5, Pin.OUT)
echo = Pin(18, Pin.IN)

# --- Wi-Fi接続 ---
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("📡 Wi-Fiに接続中...")
        wlan.connect(SSID, PASSWORD)
        while not wlan.isconnected():
            time.sleep(0.5)
    print("✅ Wi-Fi接続成功:", wlan.ifconfig())

# --- NTP同期 ---
def sync_time():
    try:
        import ntptime
        ntptime.host = 'ntp.jst.mfeed.ad.jp'  # 日本のNTPサーバー
        ntptime.settime()
        rtc = RTC()
        tm = time.localtime(time.time() + 9 * 3600)  # JST補正
        rtc.datetime((tm[0], tm[1], tm[2], tm[6], tm[3], tm[4], tm[5], 0))
        print("⏰ NTP同期成功:", "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
            tm[0], tm[1], tm[2], tm[3], tm[4], tm[5]))
    except Exception as e:
        print(f"⚠️ NTP同期失敗: {e}")

# --- 距離測定関数 ---
def measure_distance():
    trig.off()
    time.sleep_us(2)
    trig.on()
    time.sleep_us(10)
    trig.off()

    try:
        duration = time_pulse_us(echo, 1, 100000)  # 最大100ms待機
        distance = (duration / 2) / 1000000 * 340  # mに変換
        print(f"📏 測定距離: {distance:.2f} m")
        return distance
    except Exception as e:
        print(f"❌ 測定エラー: {e}")
        return None

# --- ログ記録関数 ---
def log_event(pir_status, distance):
    timestamp = time.localtime()
    datetime_str = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        timestamp[0], timestamp[1], timestamp[2],
        timestamp[3], timestamp[4], timestamp[5]
    )
    date_str = "{:04d}-{:02d}-{:02d}".format(timestamp[0], timestamp[1], timestamp[2])
    log_filename = f"sensor_log_{date_str}.csv"

    log_entry = f"{datetime_str},PIR:{pir_status},Distance:{distance if distance is not None else 'Error'}\n"
    try:
        with open(log_filename, "a") as f:
            f.write(log_entry)
        print(f"📝 ログ記録: {log_entry.strip()}")
    except Exception as e:
        print(f"❌ ログ書き込みエラー: {e}")

# --- PC送信関数 ---
def send_motion_alert():
    try:
        addr = socket.getaddrinfo(PC_IP, PC_PORT)[0][-1]
        s = socket.socket()
        s.connect(addr)
        s.send(b"MOTION_DETECTED\n")
        s.close()
        print("✅ MOTION_DETECTED をPCへ送信")
        led.value(1)
        time.sleep(0.5)
        led.value(0)
    except Exception as e:
        print(f"❌ 送信エラー: {e}")

# --- メイン処理 ---
connect_wifi()
sync_time()

last_sent_time = 0
cooldown = 15  # 15秒クールダウン
check_period = 1.0
check_interval = 0.05

print("🚨 PIR+HC-SR04記録システム起動")

while True:
    stable_detect = True
    samples = int(check_period / check_interval)

    for _ in range(samples):
        if pir.value() == 0:
            stable_detect = False
            break
        time.sleep(check_interval)

    # HC-SR04の測定実行
    distance = measure_distance()

    # ログ記録（PIR状態と距離を記録）
    log_event("ON" if stable_detect else "OFF", distance)

    # PIRが検知していれば送信
    if stable_detect:
        now = time.time()
        if now - last_sent_time > cooldown:
            print("👀 PIR検知 → データ送信実行")
            send_motion_alert()
            last_sent_time = now
            print("⌛ PIRが0に戻るまで待機...")
            while pir.value() == 1:
                time.sleep(0.1)
        else:
            print("⚠️ クールダウン中、送信スキップ")
    else:
        print("📡 PIR変動検知（ノイズ扱い）")

    time.sleep(0.1)

