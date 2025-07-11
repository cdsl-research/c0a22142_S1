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
<img width="1075" height="194" alt="Image" src="https://github.com/user-attachments/assets/380f0065-6d35-4bd2-91a1-86eb97c228b6" />

# client.pyの実行結果
client.pyの結果は以下のとおりである．
<img width="486" height="264" alt="Image" src="https://github.com/user-attachments/assets/dfb9a02e-4ac6-4578-8e4e-034a39281c1f" />

# server.pyの実行結果
server.pyの結果は以下のとおりである．
<img width="703" height="66" alt="Image" src="https://github.com/user-attachments/assets/87a82a9f-5f59-4277-843d-d5f9007681ae" />
