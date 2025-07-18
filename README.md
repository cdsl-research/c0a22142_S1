# Entering and leaving the room system

# 用途・目的
これらのファイルは入退室管理システムに関するプログラムである．
クライアントはmain.py，サーバはserver.pyである．これらのプログラムの説明をする．サーバは
ログをcsvファイルに保存する．
クライアントはノートパソコンと接続しているカードリーダーを動作させ読み取ったIDと日時をサーバに送信し，ログの同期を行う．もし，
サーバに接続できない場合は，一時的にクライアントのみでローカルに運用を行う．

# 今回使用したクライアントとサーバのハードウェア
クライアントにはESP32，ノートパソコン，人感センサーのHW-416-Bを使用した．クライアントには，main.pyと
client.pyがある．

サーバには，ESXiを用いて仮想マシンを作成した．サーバにはserver.pyがある．

# プログラム紹介
## main.py
人感センサーが検知したら検知した日時をノートパソコンに送信するプログラムである．

## client.py
カードリーダーを動作させIDと日時をサーバに送信したり，main.pyから受信した場合やカードリーダーに
スキャンされた場合に音声通知を行う．また，サーバが一時的に使用不可の場合には再送信やローカル運用を行う．

## server.py
クライアントから送信されたIDと日時をログに保存し，クライアントのログと同期する．そして，APIを用いて
スプレッドシートに日時や名前を保存する．

# その他ファイル
## felica.lib
今回使用したカードリーダーのPaSoRiを使用するために必要なファイル

参照URL：http://felicalib.tmurakam.org/

zipファイルを展開し，client.pyと同じディレクトリに置く．

# 使用言語
main.pyはMicroPython，client.pyとserver.pyはPythonで記述されている．

# 実行方法
main.pyはESP32を使い．MicroPythonのファームウェアはv1.24.0を使用している．プログラムの記述には
Thonnyを用いた．

クライアントにはノートパソコンとPaSoRiを使い，client.pyを置いている．
サーバはESXiに仮想環境を作成し，server.pyを置いている．

まず．サーバを起動し，仮想環境でPythonファイルを下記の方法からPowerShell等で実行する．
~~~
Python3 server.py
~~~

その後，クライアントとESP32のプログラムを実行する．
人感センサーが反応するように試しに近くを歩き，ESP32が以下の写真のようになれば検知ができている．

# 注意点
それぞれのプログラムに必要なIPアドレス，ポート番号，SSID，PASSWORDを設定する．

# main.pyの実行結果
main.pyの結果は以下のとおりである．

<img width="892" height="323" alt="Image" src="https://github.com/user-attachments/assets/a949118c-418d-41b3-b6f6-fb564de26f8b" />

# client.pyの実行結果
client.pyの結果は以下のとおりである．

<img width="486" height="264" alt="Image" src="https://github.com/user-attachments/assets/dfb9a02e-4ac6-4578-8e4e-034a39281c1f" />

# server.pyの実行結果
server.pyの結果は以下のとおりである．

<img width="703" height="66" alt="Image" src="https://github.com/user-attachments/assets/87a82a9f-5f59-4277-843d-d5f9007681ae" />

# おわりに
main.pyとclient.pyの送信されたデータはcsvファイルに保存されている．

main.pyの送信されたデータ(esp32_log_2025-07-16.csv)の一部
<img width="584" height="25" alt="image" src="https://github.com/user-attachments/assets/12024421-9522-41e9-bc8c-ee890d42a304" />

client.pyの送信されたデータ(entry_log_2025-07-16.csv)の一部
<img width="616" height="24" alt="image" src="https://github.com/user-attachments/assets/77813b8e-8e6c-4326-a085-4c28d4cb35b8" />


