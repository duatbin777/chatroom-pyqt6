# 局域网聊天室（集成星火 AI 机器人）

基于 Python + PyQt6 实现的局域网聊天室系统，采用 C/S 架构，支持群聊、私聊、在线用户管理，并集成讯飞星火大模型 AI 机器人。

## 功能特性

- 群聊与私聊（基于 TCP Socket 通信）
- 在线用户列表实时刷新（上线/下线广播）
- 用户名唯一性校验（重复注册会被拒绝）
- 集成讯飞星火大模型 AI 机器人（群聊 @ 触发 + 私聊直接对话）
- @ 用户选择弹窗（输入 `@` 自动弹出在线用户列表）
- 服务器 GUI 控制面板（一键启停、IP 自动获取、复制 IP）
- 自定义消息分隔符 `__EOF__` 解决 TCP 粘包问题
- 多标签页私聊窗口（可关闭、可切换）

## 技术栈

- Python 3.x
- PyQt6（GUI 界面）
- socket / threading（TCP 网络通信与多线程）
- websocket-client（星火 AI WebSocket 接口）
- json（消息序列化）
- hmac / hashlib / base64（星火 API 鉴权签名）

## 项目结构

```
chat/
├── chat.py      # 客户端 UI 界面定义（PyQt6 设计）
├── client.py    # 客户端业务逻辑（连接、收发消息、私聊、@功能）
└── server.py    # 服务器业务逻辑（含星火 AI 集成、GUI 控制台）
```

## 安装

```bash
pip install PyQt6 websocket-client
```

## 使用方法

### 1. 启动服务器

```bash
python server.py
```

点击界面上的「启动服务器」按钮，界面会显示本机局域网 IP 和端口（默认 12345），可点击「复制IP」将 IP 复制到剪贴板，方便分享给局域网内的其他用户。

### 2. 启动客户端

```bash
python client.py
```

在客户端界面填写：

- **IP**：服务器所在主机的局域网 IP
- **Port**：12345
- **Name**：自定义用户名（不能与已有用户重复，也不能使用保留名 `SparkAI`）

点击「Connect」即可连接。

### 3. 使用 AI 机器人

- **群聊触发**：在群聊输入框输入 `@SparkAI 你好` 或 `AI: 今天天气如何` 等前缀，AI 会自动回复到群聊。
- **私聊触发**：双击在线用户列表中的 `SparkAI`，在私聊标签页直接发送消息即可与 AI 一对一对话。

## 通信协议

客户端与服务器之间使用 TCP 长连接通信，所有消息以 JSON 格式编码，并以 `__EOF__` 作为消息分隔符，从而解决 TCP 粘包/半包问题。

消息结构示例：

```json
{
  "type": "chat",
  "sender": "张三",
  "time": "14:23:05",
  "msg": "你好"
}
```

消息类型（`type` 字段）约定：

| type 值 | 含义 |
| --- | --- |
| 1 | 客户端上线注册 |
| 2 | 用户上线广播 |
| 3 | 私聊消息 |
| 4 | 用户下线广播 |
| 5 | 用户名注册失败（重复或保留名） |
| `chat` | 群聊消息 |

## 关键设计

### 粘包处理

TCP 是流式协议，没有消息边界。本项目在每条 JSON 消息末尾追加 `__EOF__` 作为分隔符，接收端在缓冲区中按 `__EOF__` 切分，确保完整解析每条消息。

### 线程模型

- **服务器端**：主线程运行 GUI，监听线程 `accept` 连接，每个客户端分配一个 `ServerThread` 处理消息，AI 调用在独立线程中执行避免阻塞。
- **客户端**：主线程运行 GUI，`ClientThread`（`QThread`）负责接收消息，通过 PyQt 信号将消息投递回主线程处理，保证 UI 操作线程安全。

### AI 上下文管理

`SparkAI` 类为群聊和每个私聊用户分别维护对话历史列表，当历史内容总字符数超过 8000 时，从头部删除最早的消息，避免超出模型上下文窗口限制。

### 用户名唯一性校验

服务器在收到 `type=1/2` 注册消息时，遍历所有已注册用户检查重名，同时禁止使用保留名 `SparkAI`。冲突时返回 `type=5` 错误消息并断开该连接。

### AI 虚拟客户端

服务器在 `clients` 字典中预先注册一个 `ai_virtual_client`（使用 `object()` 作为 key），用户名为 `SparkAI`。这样 AI 在用户列表中显示为在线用户，但不会真正建立 socket 连接，广播消息时也会跳过它。

## 代码

### `chat.py` — 客户端 UI 界面

```python
# -*- coding: utf-8 -*-
from PyQt6 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(750, 750)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        self.layoutWidget = QtWidgets.QWidget(self.centralwidget)
        self.layoutWidget.setGeometry(QtCore.QRect(20, 20, 710, 680))
        self.layoutWidget.setObjectName("layoutWidget")

        self.gridLayout = QtWidgets.QGridLayout(self.layoutWidget)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setObjectName("gridLayout")

        # --- 第一行: 基础连接设置 ---
        self.label = QtWidgets.QLabel("IP:", self.layoutWidget)
        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)
        self.ip = QtWidgets.QLineEdit(self.layoutWidget)
        self.gridLayout.addWidget(self.ip, 0, 1, 1, 1)

        self.label_3 = QtWidgets.QLabel("Port:", self.layoutWidget)
        self.gridLayout.addWidget(self.label_3, 0, 2, 1, 1)
        self.port = QtWidgets.QLineEdit(self.layoutWidget)
        self.gridLayout.addWidget(self.port, 0, 3, 1, 1)

        self.label_user = QtWidgets.QLabel("Name:", self.layoutWidget)
        self.gridLayout.addWidget(self.label_user, 0, 4, 1, 1)
        self.username = QtWidgets.QLineEdit(self.layoutWidget)
        self.gridLayout.addWidget(self.username, 0, 5, 1, 1)

        self.start_button = QtWidgets.QPushButton("Connect", self.layoutWidget)
        self.gridLayout.addWidget(self.start_button, 0, 6, 1, 1)
        self.terminal_button = QtWidgets.QPushButton("Close", self.layoutWidget)
        self.gridLayout.addWidget(self.terminal_button, 0, 7, 1, 1)

        # --- 聊天区域与连接列表 ---
        self.chat_tabs = QtWidgets.QTabWidget(self.layoutWidget)
        self.chat_tabs.setTabsClosable(True)

        self.group_chat_window = QtWidgets.QListWidget()
        self.group_chat_window.setWordWrap(True)
        self.group_chat_window.setResizeMode(QtWidgets.QListWidget.ResizeMode.Adjust)
        self.group_chat_window.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.group_chat_window.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        )

        self.chat_tabs.addTab(self.group_chat_window, "Group Chat (群聊)")
        self.gridLayout.addWidget(self.chat_tabs, 1, 0, 1, 6)

        self.list_label = QtWidgets.QLabel("双击用户发起私聊:", self.layoutWidget)
        self.gridLayout.addWidget(self.list_label, 1, 6, 1, 2, QtCore.Qt.AlignmentFlag.AlignBottom)

        self.connection_list = QtWidgets.QListWidget(self.layoutWidget)
        self.connection_list.setMaximumWidth(200)
        self.gridLayout.addWidget(self.connection_list, 1, 6, 1, 2)

        # --- 状态栏 ---
        self.label_5 = QtWidgets.QLabel("Status:", self.layoutWidget)
        self.gridLayout.addWidget(self.label_5, 2, 0, 1, 1)
        self.running_status = QtWidgets.QLabel("No Connection", self.layoutWidget)
        self.gridLayout.addWidget(self.running_status, 2, 1, 1, 7)

        # --- 输入框 ---
        self.input_window = QtWidgets.QTextEdit(self.layoutWidget)
        self.input_window.setMaximumSize(QtCore.QSize(16777215, 100))
        self.input_window.setPlaceholderText("此输入消息...")
        self.gridLayout.addWidget(self.input_window, 3, 0, 1, 8)

        # --- 底部控制栏 ---
        self.file_button = QtWidgets.QPushButton("Send File", self.layoutWidget)
        self.gridLayout.addWidget(self.file_button, 4, 4, 1, 1)
        self.clear_button = QtWidgets.QPushButton("Clear", self.layoutWidget)
        self.gridLayout.addWidget(self.clear_button, 4, 5, 1, 1)
        self.send_button = QtWidgets.QPushButton("Send", self.layoutWidget)
        self.gridLayout.addWidget(self.send_button, 4, 6, 1, 1)
        self.quit_button = QtWidgets.QPushButton("Quit", self.layoutWidget)
        self.gridLayout.addWidget(self.quit_button, 4, 7, 1, 1)

        MainWindow.setCentralWidget(self.centralwidget)
        MainWindow.setWindowTitle("局域网聊天室")
        QtCore.QMetaObject.connectSlotsByName(MainWindow)
```

### `client.py` — 客户端业务逻辑

```python
# -*- coding: utf-8 -*-
from PyQt6 import QtCore, QtWidgets, QtGui
import chat_ui_3 as chat_ui
import socket
import json
import sys
import base64
import os


class ClientThread(QtCore.QThread):
    incoming_message = QtCore.pyqtSignal(dict)

    def __init__(self, socket_conn):
        super().__init__()
        self.socket = socket_conn
        self.buffer = b""

    def run(self):
        while True:
            try:
                raw_data = self.socket.recv(1024 * 1024)
                if not raw_data:
                    break

                self.buffer += raw_data
                while b"__EOF__" in self.buffer:
                    msg_bytes, self.buffer = self.buffer.split(b"__EOF__", 1)
                    if msg_bytes.strip():
                        msg_str = msg_bytes.decode('utf-8')
                        msg_dict = json.loads(msg_str)
                        self.incoming_message.emit(msg_dict)
            except Exception as e:
                print(f"Thread connection lost: {e}")
                break


class ClientWindow(QtWidgets.QMainWindow, chat_ui.Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.socket = None
        self.thread = None

        self.ip.setText('127.0.0.1')
        self.port.setText('12345')
        self.username.setText('User_' + str(os.getpid())[-3:])

        self.quit_button.clicked.connect(self.quit)
        self.send_button.clicked.connect(self.send_chat)
        self.start_button.clicked.connect(self.connect_server)
        self.terminal_button.clicked.connect(self.terminate)
        self.clear_button.clicked.connect(self.clear_window)
        self.file_button.clicked.connect(self.send_file)

        self.connection_list.itemDoubleClicked.connect(self.on_user_double_clicked)
        self.chat_tabs.tabCloseRequested.connect(self.close_private_tab)

        self.online_users = []
        self.is_inserting_at = False
        self.input_window.textChanged.connect(self.on_text_changed)

        self.my_username = ""
        self.private_tabs = {}

    class FixedMessageDialog(QtWidgets.QDialog):
        def __init__(self, parent=None, title="提示", message="", is_critical=False):
            super().__init__(parent)
            self.setWindowTitle(title)
            self.setFixedSize(400, 150)

            layout = QtWidgets.QVBoxLayout(self)
            icon_label = QtWidgets.QLabel()
            if is_critical:
                icon_label.setPixmap(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxCritical).pixmap(32, 32))
            else:
                icon_label.setPixmap(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(32, 32))

            h_layout = QtWidgets.QHBoxLayout()
            h_layout.addWidget(icon_label)
            h_layout.addWidget(QtWidgets.QLabel(message), 1)
            layout.addLayout(h_layout)

            btn_ok = QtWidgets.QPushButton("确定")
            btn_ok.clicked.connect(self.accept)
            layout.addWidget(btn_ok, 0, QtCore.Qt.AlignmentFlag.AlignCenter)

    class UserSelectDialog(QtWidgets.QDialog):
        def __init__(self, parent=None, user_list=None):
            super().__init__(parent)
            if user_list is None:
                user_list = []
            self.selected_user = None
            self.setWindowTitle("选择@的用户")
            self.setFixedSize(400, 200)

            layout = QtWidgets.QVBoxLayout(self)
            label = QtWidgets.QLabel("请选择要@的群聊用户：")
            layout.addWidget(label)

            self.user_combo = QtWidgets.QComboBox()
            self.user_combo.addItems(user_list)
            layout.addWidget(self.user_combo)

            button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
            button_box.accepted.connect(self.accept)
            button_box.rejected.connect(self.reject)
            layout.addWidget(button_box)

        def accept(self):
            self.selected_user = self.user_combo.currentText()
            super().accept()

    def on_text_changed(self):
        if self.chat_tabs.currentIndex() != 0 or self.is_inserting_at:
            return

        cursor = self.input_window.textCursor()
        text = self.input_window.toPlainText()
        pos = cursor.position()

        if pos > 0 and text[pos - 1] == '@':
            if pos == 1 or text[pos - 2] in [' ', '\n', '\t', '']:
                self.is_inserting_at = True

                selectable_users = [user for user in self.online_users if user != self.my_username]
                if not selectable_users:
                    self.is_inserting_at = False
                    QtWidgets.QMessageBox.information(self, "提示", "暂无其他在线用户可@")
                    return

                dialog = self.UserSelectDialog(self, selectable_users)
                if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted and dialog.selected_user:
                    target_user = dialog.selected_user
                    cursor.insertText(f"{target_user} ")
                    self.input_window.setTextCursor(cursor)

                self.is_inserting_at = False

    def on_user_double_clicked(self, item):
        target_username = item.text().replace("[Online] ", "")
        if target_username == self.my_username:
            dialog = self.FixedMessageDialog(self, "提示", "不能跟自己私聊哦！")
            dialog.exec()
            return
        self.open_or_focus_private_tab(target_username)

    def open_or_focus_private_tab(self, target_username):
        if target_username in self.private_tabs:
            tab_widget = self.private_tabs[target_username]
            index = self.chat_tabs.indexOf(tab_widget)
            self.chat_tabs.setCurrentIndex(index)
            return tab_widget
        else:
            new_tab = QtWidgets.QListWidget()
            new_tab.setWordWrap(True)
            new_tab.setResizeMode(QtWidgets.QListWidget.ResizeMode.Adjust)
            new_tab.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            new_tab.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Expanding
            )

            self.private_tabs[target_username] = new_tab
            index = self.chat_tabs.addTab(new_tab, f"私聊: {target_username}")
            self.chat_tabs.setCurrentIndex(index)
            return new_tab

    def close_private_tab(self, index):
        if index == 0:
            return
        widget = self.chat_tabs.widget(index)
        for user, w in list(self.private_tabs.items()):
            if w == widget:
                del self.private_tabs[user]
                break
        self.chat_tabs.removeTab(index)
        widget.deleteLater()

    def get_current_target(self):
        index = self.chat_tabs.currentIndex()
        if index == 0:
            return 'All'
        else:
            title = self.chat_tabs.tabText(index)
            return title.replace("私聊: ", "")

    def send_chat(self):
        if self.thread is not None and self.thread.isRunning():
            text = self.input_window.toPlainText().strip()
            print(f"【客户端发送】原始文本: {text}, UTF-8编码: {text.encode('utf-8')}")
            if not text:
                return
            if text.startswith('sendTo '):
                parts = text.split(' ', 2)
                if len(parts) >= 3:
                    target = parts[1]
                    msg_text = parts[2]
                    self.open_or_focus_private_tab(target)
                    self._send_payload({'type': 3, 'target': target, 'msg': msg_text})
                    self.input_window.clear()
                    return

            target = self.get_current_target()
            if target == 'All':
                payload = {'type': 'chat', 'msg': text}
            else:
                payload = {'type': 3, 'target': target, 'msg': text}

            self._send_payload(payload)
            self.input_window.clear()
        else:
            self.running_status.setText("No Connection")

    def send_file(self):
        dialog = self.FixedMessageDialog(self, "功能提示", "此功能为会员专属，请联系管理员后使用")
        dialog.exec()

    def _send_payload(self, payload):
        try:
            send_bytes = json.dumps(payload).encode('utf-8') + b"__EOF__"
            self.socket.sendall(send_bytes)
        except Exception as e:
            self.running_status.setText(f"Send Error: {e}")

    def handle_incoming(self, msg):
        print(f"【客户端接收】完整msg: {msg}, 消息内容: {msg.get('msg', '无')}")
        msg_type = msg.get('type')

        if msg_type == 5:
            error_info = msg.get('msg', '用户名注册失败！')
            dialog = self.FixedMessageDialog(self, "注册失败", error_info, is_critical=True)
            dialog.exec()
            self.terminate()
            self.username.setEnabled(True)
            return

        if msg_type in [1, 2]:
            users = msg.get('users', [])
            joined_user = msg.get('username')

            self.online_users = users.copy()

            self.connection_list.clear()
            for user in users:
                item = QtWidgets.QListWidgetItem(f"[Online] {user}")
                item.setForeground(QtGui.QColor("green"))
                self.connection_list.addItem(item)

            if joined_user:
                self.print_sys_msg(f"用户 '{joined_user}' 上线了。", self.group_chat_window)

        elif msg_type == 4:
            left_user = msg.get('username')
            for i in range(self.connection_list.count()):
                if left_user in self.connection_list.item(i).text():
                    self.connection_list.takeItem(i)
                    break

            if left_user in self.online_users:
                self.online_users.remove(left_user)

            self.print_sys_msg(f"用户 '{left_user}' 下线了。", self.group_chat_window)
            if left_user in self.private_tabs:
                self.print_sys_msg(f"对方已下线，无法继续发送消息。", self.private_tabs[left_user])

        else:
            sender = msg.get('sender')
            time_str = msg.get('time')
            target = msg.get('target', 'All')

            if msg_type == 3 or (target and target != 'All'):
                counterpart = target if sender == self.my_username else sender
                target_tab = self.open_or_focus_private_tab(counterpart)
                prefix = f"[私聊] {sender}"
            else:
                target_tab = self.group_chat_window
                prefix = f"[群聊] {sender}"

            if msg_type == 'chat' or msg_type == 3:
                text = msg.get('msg')
                prefix = f"[私聊] {sender}" if (msg_type == 3 or (target and target != 'All')) else f"[群聊] {sender}"
                display_msg = f"{prefix} ({time_str}): {text}"

                item = QtWidgets.QListWidgetItem(display_msg)
                item.setSizeHint(QtCore.QSize(target_tab.width(), item.sizeHint().height()))
                target_tab.addItem(item)
                target_tab.scrollToBottom()

    def print_sys_msg(self, text, target_tab):
        item = QtWidgets.QListWidgetItem(f">> System: {text}")
        item.setForeground(QtGui.QColor("gray"))
        target_tab.addItem(item)
        target_tab.scrollToBottom()

    def connect_server(self):
        if self.thread is not None and self.thread.isRunning():
            self.running_status.setText("Already Connected.")
            return

        ip = self.ip.text().strip()
        port_str = self.port.text().strip()
        self.my_username = self.username.text().strip()

        if not self.my_username:
            QtWidgets.QMessageBox.warning(self, "错误", "请输入用户名！")
            return

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((ip, int(port_str)))

            self.thread = ClientThread(self.socket)
            self.thread.incoming_message.connect(self.handle_incoming)
            self.thread.start()

            self._send_payload({'type': 1, 'username': self.my_username})

            self.running_status.setText("Connected successfully")
            self.username.setEnabled(False)
        except Exception as e:
            self.running_status.setText(f"Connection Failed: {e}")

    def terminate(self):
        if self.thread is not None and self.thread.isRunning():
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except:
                pass
            self.thread.terminate()
            self.thread.wait()
            self.thread = None

            self.connection_list.clear()

            self.private_tabs.clear()
            while self.chat_tabs.count() > 1:
                self.chat_tabs.removeTab(1)

            self.clear_window()
            self.running_status.setText("Connection Closed")
            self.username.setEnabled(True)

    def clear_window(self):
        index = self.chat_tabs.currentIndex()
        if index >= 0:
            self.chat_tabs.widget(index).clear()
        self.input_window.clear()

    def quit(self):
        self.terminate()
        sys.exit(0)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    client = ClientWindow()
    client.show()
    sys.exit(app.exec())
```

> 说明：客户端代码中 `import chat_ui_3 as chat_ui`，实际使用时请将 `chat.py` 重命名为 `chat_ui_3.py`，或修改此处的导入名以保持一致。

### `server.py` — 服务器业务逻辑

```python
# -*- coding: utf-8 -*-
import socket
import threading
import time
import json
import datetime
import _thread as thread
import base64
import hashlib
import hmac
from urllib.parse import urlparse
import ssl
from time import mktime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time
import websocket
from PyQt6 import QtCore, QtGui, QtWidgets


# ====================== 星火AI核心逻辑 ======================
class SparkAI:
    def __init__(self, appid, api_key, api_secret, spark_url, domain):
        self.APPID = appid
        self.APIKey = api_key
        self.APISecret = api_secret
        self.Spark_url = spark_url
        self.domain = domain
        self.group_chat_history = []
        self.private_chat_history = {}
        self.answer = ""
        self.is_first_content = False

    def create_url(self):
        now = datetime.datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        signature_origin = f"host: {urlparse(self.Spark_url).netloc}\ndate: {date}\nGET {urlparse(self.Spark_url).path} HTTP/1.1"
        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature_sha_base64 = base64.b64encode(signature_sha).decode(encoding='utf-8')
        authorization_origin = f'api_key="{self.APIKey}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha_base64}"'
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        v = {
            "authorization": authorization,
            "date": date,
            "host": urlparse(self.Spark_url).netloc
        }
        url = self.Spark_url + '?' + urlencode(v)
        return url

    def gen_params(self, is_private=False, private_user=None):
        if is_private and private_user:
            history = self.private_chat_history.get(private_user, [])
        else:
            history = self.group_chat_history
        return {
            "header": {"app_id": self.APPID, "uid": private_user if is_private else "chatroom_ai"},
            "parameter": {"chat": {"domain": self.domain, "temperature": 1.2, "max_tokens": 32768}},
            "payload": {"message": {"text": history}}
        }

    def get_content_length(self, is_private=False, private_user=None):
        if is_private and private_user:
            history = self.private_chat_history.get(private_user, [])
        else:
            history = self.group_chat_history
        return sum(len(item["content"]) for item in history)

    def check_history_length(self, is_private=False, private_user=None):
        if is_private and private_user:
            history = self.private_chat_history.get(private_user, [])
            while self.get_content_length(is_private=True, private_user=private_user) > 8000:
                del history[0]
            self.private_chat_history[private_user] = history
        else:
            while self.get_content_length() > 8000:
                del self.group_chat_history[0]

    def get_ai_response(self, question, is_private=False, private_user=None):
        self.answer = ""
        self.is_first_content = False

        if is_private and private_user:
            if private_user not in self.private_chat_history:
                self.private_chat_history[private_user] = []
            self.private_chat_history[private_user].append({"role": "user", "content": question})
            self.check_history_length(is_private=True, private_user=private_user)
        else:
            self.group_chat_history.append({"role": "user", "content": question})
            self.check_history_length()

        def on_message(ws, message):
            data = json.loads(message)
            code = data['header']['code']
            if code != 0:
                print(f'AI请求错误: {code}, {data}')
                ws.close()
                return
            choices = data["payload"]["choices"]
            status = choices["status"]
            text = choices['text'][0]
            if 'content' in text and text['content']:
                content = text["content"]
                self.answer += content
            if status == 2:
                ws.close()

        def on_error(ws, error):
            print(f'AI连接错误: {error}')

        def on_close(ws, *args):
            pass

        def on_open(ws):
            thread.start_new_thread(lambda: ws.send(json.dumps(self.gen_params(is_private, private_user))), ())

        ws_url = self.create_url()
        ws = websocket.WebSocketApp(ws_url, on_message=on_message, on_error=on_error, on_close=on_close,
                                    on_open=on_open)
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

        if is_private and private_user:
            self.private_chat_history[private_user].append({"role": "assistant", "content": self.answer})
        else:
            self.group_chat_history.append({"role": "assistant", "content": self.answer})
        return self.answer


# ====================== 客户端处理线程 ======================
class ServerThread(threading.Thread):
    def __init__(self, server_instance, client_socket, address):
        threading.Thread.__init__(self)
        self.server = server_instance
        self.client = client_socket
        self.address = address
        self.buffer = b""

    def run(self):
        while self.server.is_running:
            try:
                raw_data = self.client.recv(1024 * 1024)
                if not raw_data:
                    break

                self.buffer += raw_data
                while b"__EOF__" in self.buffer and self.server.is_running:
                    msg_bytes, self.buffer = self.buffer.split(b"__EOF__", 1)
                    if msg_bytes.strip():
                        msg_str = msg_bytes.decode('utf-8')
                        self.process_message(msg_str)
            except Exception as e:
                print(f"Client Exception {self.address}: {e}")
                break

        self.server.remove_client(self.client)

    def process_message(self, msg_str):
        data = json.loads(msg_str)
        print(f"【服务器接收】原始消息: {data}")
        msg_type = data.get('type')
        target = data.get('target')
        sender_name = self.server.clients.get(self.client, {}).get('username', f"{self.address[0]}:{self.address[1]}")
        data['sender'] = sender_name
        data['time'] = datetime.datetime.fromtimestamp(time.time()).strftime('%H:%M:%S')
        print(f"【服务器转发】处理后消息: {data}")

        if msg_type in [1, 2]:
            new_username = data.get('username')
            if new_username == 'SparkAI':
                error_msg = {
                    'type': 5,
                    'msg': '用户名"SparkAI"为系统保留名，无法使用！',
                    'time': datetime.datetime.fromtimestamp(time.time()).strftime('%H:%M:%S')
                }
                error_bytes = json.dumps(error_msg).encode('utf-8') + b"__EOF__"
                self.client.sendall(error_bytes)
                self.server.remove_client(self.client)
                return

            for c, info in self.server.clients.items():
                if c != self.server.ai_virtual_client and info.get('username') == new_username:
                    error_msg = {
                        'type': 5,
                        'msg': f'用户名"{new_username}"已被占用，请更换！',
                        'time': datetime.datetime.fromtimestamp(time.time()).strftime('%H:%M:%S')
                    }
                    error_bytes = json.dumps(error_msg).encode('utf-8') + b"__EOF__"
                    self.client.sendall(error_bytes)
                    self.server.remove_client(self.client)
                    return

            self.server.clients[self.client]['username'] = new_username
            self.server.broadcast_users(action_type=2, changed_user=new_username)

        elif msg_type == 3 or (target and target != 'All'):
            send_bytes = json.dumps(data).encode('utf-8') + b"__EOF__"
            for c, info in self.server.clients.items():
                if info['username'] == target or info['username'] == sender_name:
                    try:
                        c.sendall(send_bytes)
                    except:
                        pass

            if target == 'SparkAI':
                question = data.get('msg', '').strip()
                if not question:
                    return

                def ai_private_reply_task():
                    try:
                        ai_response = self.server.spark_ai.get_ai_response(
                            question,
                            is_private=True,
                            private_user=sender_name
                        )
                        ai_msg = {
                            'type': 3,
                            'target': sender_name,
                            'sender': 'SparkAI',
                            'msg': ai_response,
                            'time': datetime.datetime.fromtimestamp(time.time()).strftime('%H:%M:%S')
                        }
                        ai_send_bytes = json.dumps(ai_msg).encode('utf-8') + b"__EOF__"
                        for c, info in self.server.clients.items():
                            if info['username'] == sender_name:
                                try:
                                    c.sendall(ai_send_bytes)
                                except:
                                    pass
                    except Exception as e:
                        print(f'AI私聊回复失败: {e}')

                threading.Thread(target=ai_private_reply_task).start()

        else:

            send_bytes = json.dumps(data).encode('utf-8') + b"__EOF__"
            for c in self.server.clients.keys():
                if c != self.server.ai_virtual_client:
                    try:
                        c.sendall(send_bytes)
                    except:
                        pass

            msg_content = data.get('msg', '').strip()
            ai_call_prefixes = ['@SparkAI', 'AI：', 'AI:', '机器人：', '机器人:']
            is_call_ai = any(msg_content.startswith(prefix) for prefix in ai_call_prefixes)

            if is_call_ai and msg_type == 'chat':
                for prefix in ai_call_prefixes:
                    if msg_content.startswith(prefix):
                        question = msg_content[len(prefix):].strip()
                        break
                if not question:
                    return

                def ai_reply_task():
                    try:
                        ai_response = self.server.spark_ai.get_ai_response(
                            question,
                            is_private=False
                        )
                        ai_msg = {
                            'type': 'chat',
                            'target': 'All',
                            'sender': 'SparkAI',
                            'msg': ai_response,
                            'time': datetime.datetime.fromtimestamp(time.time()).strftime('%H:%M:%S')
                        }
                        ai_send_bytes = json.dumps(ai_msg).encode('utf-8') + b"__EOF__"
                        for c in self.server.clients.keys():
                            if c != self.server.ai_virtual_client:
                                try:
                                    c.sendall(ai_send_bytes)
                                except:
                                    pass
                    except Exception as e:
                        print(f'AI群聊回复失败: {e}')

                threading.Thread(target=ai_reply_task).start()


# ====================== 服务器核心类 ======================
class ChatServer(QtCore.QObject):
    status_signal = QtCore.pyqtSignal(str)
    ip_port_signal = QtCore.pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.server_socket = None
        self.host = ""
        self.port = 12345
        self.clients = {}
        self.is_running = False
        self.listen_thread = None

        # 初始化星火AI（替换为你的密钥）
        self.spark_ai = SparkAI(
            appid="ea155baa",
            api_key="7b210bf6d6a650f250200f97f6c8f112",
            api_secret="ZTI5YmEzMTU0MzVjNGMzM2Y4YWRjYmJh",
            spark_url="wss://spark-api.xf-yun.com/x2",
            domain="spark-x"
        )
        self.ai_virtual_client = object()
        self.clients[self.ai_virtual_client] = {'address': ('AI', 0), 'username': 'SparkAI'}

        self.get_local_ip()

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            self.host = s.getsockname()[0]
            s.close()
        except Exception as e:
            self.host = "127.0.0.1"
            print(f"获取IP失败: {e}")
        self.ip_port_signal.emit(self.host, str(self.port))

    def start_server(self):
        if self.is_running:
            self.status_signal.emit("服务器已在运行")
            return

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            self.is_running = True

            self.listen_thread = threading.Thread(target=self.listen_clients)
            self.listen_thread.daemon = True
            self.listen_thread.start()

            self.broadcast_users(action_type=2, changed_user='SparkAI')
            self.status_signal.emit(f"服务器已启动 | IP: {self.host} | 端口: {self.port}")
        except Exception as e:
            self.status_signal.emit(f"启动失败: {str(e)}")
            self.is_running = False

    def listen_clients(self):
        while self.is_running:
            try:
                self.server_socket.settimeout(1.0)
                con, addr = self.server_socket.accept()
                print(f"新连接: {addr}")
                self.clients[con] = {'address': addr, 'username': None}
                client_thread = ServerThread(self, con, addr)
                client_thread.daemon = True
                client_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.is_running:
                    self.status_signal.emit(f"监听错误: {str(e)}")
                break

    def stop_server(self):
        if not self.is_running:
            self.status_signal.emit("服务器未运行")
            return

        self.is_running = False
        try:
            if self.server_socket:
                self.server_socket.close()
                self.server_socket = None

            for client in list(self.clients.keys()):
                if client != self.ai_virtual_client:
                    try:
                        client.shutdown(socket.SHUT_RDWR)
                        client.close()
                    except:
                        pass
            self.clients.clear()
            self.clients[self.ai_virtual_client] = {'address': ('AI', 0), 'username': 'SparkAI'}

            self.status_signal.emit("服务器已停止")
        except Exception as e:
            self.status_signal.emit(f"停止失败: {str(e)}")

    def broadcast_users(self, action_type, changed_user):
        if not self.is_running:
            return
        users = [info['username'] for info in self.clients.values() if info['username'] is not None]
        msg = {'type': action_type, 'users': users, 'username': changed_user}
        send_bytes = json.dumps(msg).encode('utf-8') + b"__EOF__"
        for c in self.clients.keys():
            if c != self.ai_virtual_client:
                try:
                    c.sendall(send_bytes)
                except:
                    pass

    def remove_client(self, client):
        if client == self.ai_virtual_client or not self.is_running:
            return
        if client in self.clients:
            offline_user = self.clients[client].get('username')
            print(f"客户端断开: {offline_user}")
            del self.clients[client]
            if offline_user:
                self.broadcast_users(action_type=4, changed_user=offline_user)
        try:
            client.close()
        except:
            pass


# ====================== 服务器GUI界面 ======================
class ServerGUI(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("局域网聊天服务器")
        self.resize(500, 250)
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QtWidgets.QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(30, 30, 30, 30)
        self.layout.setSpacing(20)

        self.info_group = QtWidgets.QGroupBox("服务器信息")
        self.info_layout = QtWidgets.QGridLayout(self.info_group)
        self.info_layout.setContentsMargins(20, 15, 20, 15)

        self.ip_label = QtWidgets.QLabel("服务器IP:")
        self.ip_value = QtWidgets.QLabel("")
        self.ip_value.setStyleSheet("color: #2E8B57; font-weight: bold;")
        self.copy_ip_btn = QtWidgets.QPushButton("复制IP")
        self.copy_ip_btn.setStyleSheet("""
            padding: 4px 12px; 
            font-size: 12px; 
            background-color: #2196F3; 
            color: white; 
            border: none; 
            border-radius: 4px;
        """)
        self.copy_ip_btn.clicked.connect(self.copy_ip_to_clipboard)
        self.info_layout.addWidget(self.ip_label, 0, 0, 1, 1)
        self.info_layout.addWidget(self.ip_value, 0, 1, 1, 3)
        self.info_layout.addWidget(self.copy_ip_btn, 0, 4, 1, 1)

        self.port_label = QtWidgets.QLabel("端口号:")
        self.port_value = QtWidgets.QLabel("12345")
        self.port_value.setStyleSheet("color: #2E8B57; font-weight: bold;")
        self.info_layout.addWidget(self.port_label, 1, 0, 1, 1)
        self.info_layout.addWidget(self.port_value, 1, 1, 1, 3)

        self.layout.addWidget(self.info_group)

        self.btn_layout = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("启动服务器")
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px 20px; font-size: 14px;")
        self.start_btn.clicked.connect(self.on_start_click)

        self.stop_btn = QtWidgets.QPushButton("停止服务器")
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; padding: 8px 20px; font-size: 14px;")
        self.stop_btn.clicked.connect(self.on_stop_click)
        self.stop_btn.setEnabled(False)

        self.btn_layout.addStretch()
        self.btn_layout.addWidget(self.start_btn)
        self.btn_layout.addWidget(self.stop_btn)
        self.btn_layout.addStretch()
        self.layout.addLayout(self.btn_layout)

        self.status_label = QtWidgets.QLabel("状态: 未运行")
        self.status_label.setStyleSheet("color: #666; font-size: 14px;")
        self.layout.addWidget(self.status_label, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        self.chat_server = ChatServer()
        self.chat_server.status_signal.connect(self.update_status)
        self.chat_server.ip_port_signal.connect(self.update_ip_port)

        self.chat_server.get_local_ip()

    def copy_ip_to_clipboard(self):
        ip_text = self.ip_value.text()
        if ip_text:
            clipboard = QtWidgets.QApplication.clipboard()
            clipboard.setText(ip_text)
            original_status = self.status_label.text()
            self.status_label.setText(f"状态: 已复制IP {ip_text} 到剪贴板 ")
            self.status_label.setStyleSheet("color: #2196F3; font-size: 14px; font-weight: bold;")
            QtCore.QTimer.singleShot(2000, lambda: self.update_status(original_status))

    def update_ip_port(self, ip, port):
        self.ip_value.setText(ip)
        self.port_value.setText(port)

    def update_status(self, status):
        self.status_label.setText(f"状态: {status}")
        if "已启动" in status:
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 14px; font-weight: bold;")
        elif "已停止" in status:
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.status_label.setStyleSheet("color: #f44336; font-size: 14px; font-weight: bold;")
        elif "已复制IP" not in status:
            self.status_label.setStyleSheet("color: #ff9800; font-size: 14px; font-weight: bold;")

    def on_start_click(self):
        self.chat_server.start_server()

    def on_stop_click(self):
        self.chat_server.stop_server()

    def closeEvent(self, event):
        if self.chat_server.is_running:
            self.chat_server.stop_server()
        event.accept()


if __name__ == '__main__':
    import sys

    app = QtWidgets.QApplication(sys.argv)
    server_gui = ServerGUI()
    server_gui.show()
    sys.exit(app.exec())
```

## 配置说明

如需使用星火 AI，请前往[讯飞开放平台](https://www.xfyun.cn/)申请自己的 APPID、APIKey、APISecret，并替换 `server.py` 中 `SparkAI` 初始化的对应参数：

```python
self.spark_ai = SparkAI(
    appid="你的APPID",
    api_key="你的APIKey",
    api_secret="你的APISecret",
    spark_url="wss://spark-api.xf-yun.com/x2",
    domain="spark-x"
)
```

## 后续扩展方向

- 文件传输功能（目前为占位）
- 消息持久化存储
- 用户头像与富文本消息
- 群组管理（创建/加入/退出群组）
- AI 多轮对话上下文持久化

## License

MIT
