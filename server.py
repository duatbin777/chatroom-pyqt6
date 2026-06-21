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


# ====================== 星火AI核心逻辑（复用原代码） ======================
class SparkAI:
    def __init__(self, appid, api_key, api_secret, spark_url, domain):
        self.APPID = appid
        self.APIKey = api_key
        self.APISecret = api_secret
        self.Spark_url = spark_url
        self.domain = domain
        self.group_chat_history = []  # 群聊对话上下文
        self.private_chat_history = {}  # 私聊上下文：{用户名: 历史列表}
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


# ====================== 客户端处理线程（复用原代码） ======================
class ServerThread(threading.Thread):
    def __init__(self, server_instance, client_socket, address):
        threading.Thread.__init__(self)
        self.server = server_instance
        self.client = client_socket
        self.address = address
        self.buffer = b""

    def run(self):
        # 仅在服务器运行中时处理消息
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
        print(f"【服务器接收】原始消息: {data}")  # 确认客户端消息是否完整
        msg_type = data.get('type')
        target = data.get('target')
        sender_name = self.server.clients.get(self.client, {}).get('username', f"{self.address[0]}:{self.address[1]}")
        data['sender'] = sender_name
        data['time'] = datetime.datetime.fromtimestamp(time.time()).strftime('%H:%M:%S')
        print(f"【服务器转发】处理后消息: {data}")  # 确认转发前消息未被篡改

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


# ====================== 可控制启停的服务器核心类 ======================
class ChatServer(QtCore.QObject):
    # 定义信号，用于更新GUI状态
    status_signal = QtCore.pyqtSignal(str)
    ip_port_signal = QtCore.pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.server_socket = None
        self.host = ""
        self.port = 12345
        self.clients = {}
        self.is_running = False  # 运行状态标志
        self.listen_thread = None  # 监听线程

        # 初始化星火AI（替换为你的密钥）
        self.spark_ai = SparkAI(
            appid="ea155baa",  # 你的APPID
            api_key="7b210bf6d6a650f250200f97f6c8f112",  # 你的APIKey
            api_secret="ZTI5YmEzMTU0MzVjNGMzM2Y4YWRjYmJh",  # 你的APISecret
            spark_url="wss://spark-api.xf-yun.com/x2",
            domain="spark-x"
        )
        # 添加SparkAI虚拟用户
        self.ai_virtual_client = object()
        self.clients[self.ai_virtual_client] = {'address': ('AI', 0), 'username': 'SparkAI'}

        # 自动获取本机IP
        self.get_local_ip()

    def get_local_ip(self):
        """获取本机局域网IP"""
        try:
            # 方法1：通过socket.gethostbyname
            
            # self.host = socket.gethostbyname(socket.gethostname())

            #self.host = "192.168.126.136"
            # 方法2（备选）：通过连接外部地址获取真实出口IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            self.host = s.getsockname()[0]
            s.close()
        except Exception as e:
            self.host = "127.0.0.1"
            print(f"获取IP失败: {e}")
        # 发送IP和端口到GUI
        self.ip_port_signal.emit(self.host, str(self.port))

    def start_server(self):
        """启动服务器"""
        if self.is_running:
            self.status_signal.emit("服务器已在运行")
            return

        try:
            # 创建socket并绑定
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 设置端口复用，避免重启时端口占用
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            self.is_running = True

            # 启动监听线程
            self.listen_thread = threading.Thread(target=self.listen_clients)
            self.listen_thread.daemon = True  # 守护线程，退出时自动关闭
            self.listen_thread.start()

            # 广播SparkAI上线
            self.broadcast_users(action_type=2, changed_user='SparkAI')
            self.status_signal.emit(f"服务器已启动 | IP: {self.host} | 端口: {self.port}")
        except Exception as e:
            self.status_signal.emit(f"启动失败: {str(e)}")
            self.is_running = False

    def listen_clients(self):
        """监听客户端连接（运行在独立线程）"""
        while self.is_running:
            try:
                # 设置超时，避免阻塞无法退出
                self.server_socket.settimeout(1.0)
                con, addr = self.server_socket.accept()
                print(f"新连接: {addr}")
                self.clients[con] = {'address': addr, 'username': None}
                # 启动客户端处理线程
                client_thread = ServerThread(self, con, addr)
                client_thread.daemon = True
                client_thread.start()
            except socket.timeout:
                # 超时只是为了检查is_running，继续循环
                continue
            except Exception as e:
                if self.is_running:
                    self.status_signal.emit(f"监听错误: {str(e)}")
                break

    def stop_server(self):
        """停止服务器"""
        if not self.is_running:
            self.status_signal.emit("服务器未运行")
            return

        self.is_running = False
        try:
            # 关闭监听socket
            if self.server_socket:
                self.server_socket.close()
                self.server_socket = None

            # 关闭所有客户端连接
            for client in list(self.clients.keys()):
                if client != self.ai_virtual_client:
                    try:
                        client.shutdown(socket.SHUT_RDWR)
                        client.close()
                    except:
                        pass
            self.clients.clear()
            # 重新添加AI虚拟用户
            self.clients[self.ai_virtual_client] = {'address': ('AI', 0), 'username': 'SparkAI'}

            self.status_signal.emit("服务器已停止")
        except Exception as e:
            self.status_signal.emit(f"停止失败: {str(e)}")

    def broadcast_users(self, action_type, changed_user):
        """广播在线用户列表"""
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
        """移除客户端"""
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


# ====================== 服务器GUI界面（新增复制IP按钮） ======================
class ServerGUI(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("局域网聊天服务器")
        self.resize(500, 250)
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)

        # 创建布局
        self.layout = QtWidgets.QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(30, 30, 30, 30)
        self.layout.setSpacing(20)

        # 1. IP和端口显示区域
        self.info_group = QtWidgets.QGroupBox("服务器信息")
        self.info_layout = QtWidgets.QGridLayout(self.info_group)
        self.info_layout.setContentsMargins(20, 15, 20, 15)

        # IP标签
        self.ip_label = QtWidgets.QLabel("服务器IP:")
        self.ip_value = QtWidgets.QLabel("")
        self.ip_value.setStyleSheet("color: #2E8B57; font-weight: bold;")
        # 新增：复制IP按钮
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
        self.info_layout.addWidget(self.copy_ip_btn, 0, 4, 1, 1)  # 把复制按钮加到IP行第5列

        # 端口标签
        self.port_label = QtWidgets.QLabel("端口号:")
        self.port_value = QtWidgets.QLabel("12345")
        self.port_value.setStyleSheet("color: #2E8B57; font-weight: bold;")
        self.info_layout.addWidget(self.port_label, 1, 0, 1, 1)
        self.info_layout.addWidget(self.port_value, 1, 1, 1, 3)

        self.layout.addWidget(self.info_group)

        # 2. 控制按钮区域
        self.btn_layout = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("启动服务器")
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px 20px; font-size: 14px;")
        self.start_btn.clicked.connect(self.on_start_click)

        self.stop_btn = QtWidgets.QPushButton("停止服务器")
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; padding: 8px 20px; font-size: 14px;")
        self.stop_btn.clicked.connect(self.on_stop_click)
        self.stop_btn.setEnabled(False)  # 初始禁用

        self.btn_layout.addStretch()
        self.btn_layout.addWidget(self.start_btn)
        self.btn_layout.addWidget(self.stop_btn)
        self.btn_layout.addStretch()
        self.layout.addLayout(self.btn_layout)

        # 3. 状态显示区域
        self.status_label = QtWidgets.QLabel("状态: 未运行")
        self.status_label.setStyleSheet("color: #666; font-size: 14px;")
        self.layout.addWidget(self.status_label, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        # 初始化服务器核心
        self.chat_server = ChatServer()
        # 绑定信号
        self.chat_server.status_signal.connect(self.update_status)
        self.chat_server.ip_port_signal.connect(self.update_ip_port)

        # 自动获取IP
        self.chat_server.get_local_ip()

    def copy_ip_to_clipboard(self):
        """新增：复制IP地址到剪贴板"""
        ip_text = self.ip_value.text()
        if ip_text:
            # 获取系统剪贴板并设置内容
            clipboard = QtWidgets.QApplication.clipboard()
            clipboard.setText(ip_text)
            # 显示复制成功提示（2秒后恢复原状态）
            original_status = self.status_label.text()
            self.status_label.setText(f"状态: 已复制IP {ip_text} 到剪贴板 ")
            self.status_label.setStyleSheet("color: #2196F3; font-size: 14px; font-weight: bold;")
            # 2秒后恢复原状态
            QtCore.QTimer.singleShot(2000, lambda: self.update_status(original_status))

    def update_ip_port(self, ip, port):
        """更新IP和端口显示"""
        self.ip_value.setText(ip)
        self.port_value.setText(port)

    def update_status(self, status):
        """更新状态显示"""
        self.status_label.setText(f"状态: {status}")
        # 更新按钮状态
        if "已启动" in status:
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 14px; font-weight: bold;")
        elif "已停止" in status:
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.status_label.setStyleSheet("color: #f44336; font-size: 14px; font-weight: bold;")
        elif "已复制IP" not in status:  # 排除复制提示的情况
            self.status_label.setStyleSheet("color: #ff9800; font-size: 14px; font-weight: bold;")

    def on_start_click(self):
        """启动服务器按钮点击"""
        self.chat_server.start_server()

    def on_stop_click(self):
        """停止服务器按钮点击"""
        self.chat_server.stop_server()

    def closeEvent(self, event):
        """窗口关闭时停止服务器"""
        if self.chat_server.is_running:
            self.chat_server.stop_server()
        event.accept()


# ====================== 主函数 ======================
if __name__ == '__main__':
    import sys

    app = QtWidgets.QApplication(sys.argv)
    server_gui = ServerGUI()
    server_gui.show()
    sys.exit(app.exec())