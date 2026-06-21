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

        # 绑定按钮事件
        self.quit_button.clicked.connect(self.quit)
        self.send_button.clicked.connect(self.send_chat)
        self.start_button.clicked.connect(self.connect_server)
        self.terminal_button.clicked.connect(self.terminate)
        self.clear_button.clicked.connect(self.clear_window)
        self.file_button.clicked.connect(self.send_file)

        # 绑定双击用户列表发起私聊
        self.connection_list.itemDoubleClicked.connect(self.on_user_double_clicked)
        # 绑定关闭标签页事件
        self.chat_tabs.tabCloseRequested.connect(self.close_private_tab)

        # ========== 初始化在线用户列表 + 监听输入框文本变化 ==========
        self.online_users = []  # 维护在线用户列表（用于@选择）
        self.is_inserting_at = False  # 防止重复触发@选择弹窗
        self.input_window.textChanged.connect(self.on_text_changed)

        self.my_username = ""
        # 维护一个字典，保存当前已打开的私聊窗口：{ '目标用户名': QListWidget对象 }
        self.private_tabs = {}
    class FixedMessageDialog(QtWidgets.QDialog):
        """固定大小的信息提示对话框（用于替换QMessageBox）"""
        def __init__(self, parent=None, title="提示", message="", is_critical=False):
            super().__init__(parent)
            self.setWindowTitle(title)
            # 固定对话框大小
            self.setFixedSize(400, 150)
            
            layout = QtWidgets.QVBoxLayout(self)
            # 根据是否为错误类型设置图标
            icon_label = QtWidgets.QLabel()
            if is_critical:
                icon_label.setPixmap(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxCritical).pixmap(32, 32))
            else:
                icon_label.setPixmap(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(32, 32))
            
            h_layout = QtWidgets.QHBoxLayout()
            h_layout.addWidget(icon_label)
            h_layout.addWidget(QtWidgets.QLabel(message), 1) # 参数1表示拉伸因子
            layout.addLayout(h_layout)
            
            btn_ok = QtWidgets.QPushButton("确定")
            btn_ok.clicked.connect(self.accept)
            layout.addWidget(btn_ok, 0, QtCore.Qt.AlignmentFlag.AlignCenter)

    class UserSelectDialog(QtWidgets.QDialog):
        """用于@用户选择的自定义对话框，大小固定"""
        def __init__(self, parent=None, user_list=None):
            super().__init__(parent)
            if user_list is None:
                user_list = []
            self.selected_user = None
            self.setWindowTitle("选择@的用户")
            # 固定对话框大小
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
            """点击OK时，保存选中的用户名"""
            self.selected_user = self.user_combo.currentText()
            super().accept()
    # ========== 输入框文本变化监听（检测@触发选择） ==========
    def on_text_changed(self):
        # 1. 仅在群聊标签页（index=0）且非弹窗状态时检测
        if self.chat_tabs.currentIndex() != 0 or self.is_inserting_at:
            return

        # 2. 获取光标位置和输入框文本
        cursor = self.input_window.textCursor()
        text = self.input_window.toPlainText()
        pos = cursor.position()

        # 3. 检测光标前是否是单独的@（避免@后已有内容）
        if pos > 0 and text[pos - 1] == '@':
            # 过滤：@前是空格/换行/开头，确保是新的@指令
            if pos == 1 or text[pos - 2] in [' ', '\n', '\t', '']:
                self.is_inserting_at = True  # 标记弹窗状态，防止重复触发

                # 4. 过滤掉自己，仅显示其他在线用户
                selectable_users = [user for user in self.online_users if user != self.my_username]
                if not selectable_users:
                    self.is_inserting_at = False
                    QtWidgets.QMessageBox.information(self, "提示", "暂无其他在线用户可@")
                    return

                # 5. 弹出用户选择对话框
                dialog = self.UserSelectDialog(self, selectable_users)
                if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted and dialog.selected_user:
                    target_user = dialog.selected_user
                    # 6. 选择后自动填充@用户名 + 空格
                    cursor.insertText(f"{target_user} ")  # 插入用户名+空格，方便继续输入
                    self.input_window.setTextCursor(cursor)

                self.is_inserting_at = False  # 重置弹窗状态

    # ==============================================================

    def on_user_double_clicked(self, item):
        """双击列表中的用户，打开或跳转到私聊标签页"""
        target_username = item.text().replace("[Online] ", "")
        if target_username == self.my_username:
            # 使用自定义的固定大小消息对话框
            dialog = self.FixedMessageDialog(self, "提示", "不能跟自己私聊哦！")
            dialog.exec()
            return
        self.open_or_focus_private_tab(target_username)

    # def open_or_focus_private_tab(self, target_username):
    #     """如果标签页不存在则创建，存在则跳转过去"""
    #     if target_username in self.private_tabs:
    #         tab_widget = self.private_tabs[target_username]
    #         index = self.chat_tabs.indexOf(tab_widget)
    #         self.chat_tabs.setCurrentIndex(index)
    #         return tab_widget
    #     else:
    #         new_tab = QtWidgets.QListWidget()
    #         new_tab.setWordWrap(True)
    #         new_tab.setResizeMode(QtWidgets.QListWidget.ResizeMode.Adjust)

    #         self.private_tabs[target_username] = new_tab
    #         index = self.chat_tabs.addTab(new_tab, f"私聊: {target_username}")
    #         self.chat_tabs.setCurrentIndex(index)
    #         return new_tab
    def open_or_focus_private_tab(self, target_username):
        if target_username in self.private_tabs:
            tab_widget = self.private_tabs[target_username]
            index = self.chat_tabs.indexOf(tab_widget)
            self.chat_tabs.setCurrentIndex(index)
            return tab_widget
        else:
            new_tab = QtWidgets.QListWidget()
            # 新增：适配Linux的布局配置
            new_tab.setWordWrap(True)
            new_tab.setResizeMode(QtWidgets.QListWidget.ResizeMode.Adjust)
            # 允许水平滚动，避免文本截断
            new_tab.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            # 让控件自适应窗口大小
            new_tab.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Expanding
            )

            self.private_tabs[target_username] = new_tab
            index = self.chat_tabs.addTab(new_tab, f"私聊: {target_username}")
            self.chat_tabs.setCurrentIndex(index)
            return new_tab

    def close_private_tab(self, index):
        """关闭某个标签页"""
        if index == 0:
            # 群聊标签页不允许关闭
            return
        widget = self.chat_tabs.widget(index)
        # 从字典中移除记录
        for user, w in list(self.private_tabs.items()):
            if w == widget:
                del self.private_tabs[user]
                break
        self.chat_tabs.removeTab(index)
        widget.deleteLater()

    def get_current_target(self):
        """根据当前处于前台的标签页，判断发送的目标是谁"""
        index = self.chat_tabs.currentIndex()
        if index == 0:
            return 'All'
        else:
            # 标签页名称格式为 "私聊: xxx"
            title = self.chat_tabs.tabText(index)
            return title.replace("私聊: ", "")

    def send_chat(self):
        if self.thread is not None and self.thread.isRunning():
            text = self.input_window.toPlainText().strip()
            # 新增：打印原始输入文本和编码
            print(f"【客户端发送】原始文本: {text}, UTF-8编码: {text.encode('utf-8')}")
            if not text:
                return
            # sendTo 指令支持
            if text.startswith('sendTo '):
                parts = text.split(' ', 2)
                if len(parts) >= 3:
                    target = parts[1]
                    msg_text = parts[2]
                    # 打开该用户的私聊标签页，确保发出的消息自己能看到对应窗口
                    self.open_or_focus_private_tab(target)
                    self._send_payload({'type': 3, 'target': target, 'msg': msg_text})
                    self.input_window.clear()
                    return

            target = self.get_current_target()
            if target == 'All':
                payload = {'type': 'chat', 'msg': text}  # 群发
            else:
                payload = {'type': 3, 'target': target, 'msg': text}  # 头标签3代表私聊

            self._send_payload(payload)
            self.input_window.clear()
        else:
            self.running_status.setText("No Connection")

    def send_file(self):
        # 使用自定义的固定大小消息对话框
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

        # ===== 处理用户名重复错误 =====
        # ===== 处理用户名重复错误 =====
        if msg_type == 5:
            error_info = msg.get('msg', '用户名注册失败！')
            # 使用自定义的固定大小消息对话框，并标记为错误类型
            dialog = self.FixedMessageDialog(self, "注册失败", error_info, is_critical=True)
            dialog.exec()
            # 重置连接状态
            self.terminate()
            self.username.setEnabled(True)
            return

        # 1 & 2：更新列表和上线提示
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

        # 4：下线提示
        elif msg_type == 4:
            left_user = msg.get('username')
            # 刷新列表
            for i in range(self.connection_list.count()):
                if left_user in self.connection_list.item(i).text():
                    self.connection_list.takeItem(i)
                    break

            # ========== 更新在线用户列表（用户下线） ==========
            if left_user in self.online_users:
                self.online_users.remove(left_user)
            # =======================================================

            # 提示群聊和其他相关页面
            self.print_sys_msg(f"用户 '{left_user}' 下线了。", self.group_chat_window)
            if left_user in self.private_tabs:
                self.print_sys_msg(f"对方已下线，无法继续发送消息。", self.private_tabs[left_user])

        # 3 或 无头标签：处理文字聊天
        else:
            sender = msg.get('sender')
            time_str = msg.get('time')
            target = msg.get('target', 'All')

            # 判断消息归属的标签页
            if msg_type == 3 or (target and target != 'All'):
                # 私聊消息
                # 如果发送者是我自己，说明这是服务器回弹给我的记录，对方是 target
                counterpart = target if sender == self.my_username else sender
                target_tab = self.open_or_focus_private_tab(counterpart)
                prefix = f"[私聊] {sender}"
            else:
                # 群聊消息
                target_tab = self.group_chat_window
                prefix = f"[群聊] {sender}"

            # if msg_type == 'chat' or msg_type == 3:
            #     text = msg.get('msg')
            #     display_msg = f"{prefix} ({time_str}):\n  {text}"
            #     target_tab.addItem(display_msg)
            #     target_tab.scrollToBottom()
            # 找到handle_incoming方法中处理聊天消息的分支（msg_type == 'chat' or msg_type == 3）
            # 替换原有display_msg和addItem逻辑：
            if msg_type == 'chat' or msg_type == 3:
                text = msg.get('msg')
                # ① 去掉换行符，避免Linux下渲染截断
                prefix = f"[私聊] {sender}" if (msg_type == 3 or (target and target != 'All')) else f"[群聊] {sender}"
                display_msg = f"{prefix} ({time_str}): {text}"

                # ② 创建Item并设置自适应大小（关键：解决...截断问题）
                item = QtWidgets.QListWidgetItem(display_msg)
                # 让Item宽度适配列表宽度，高度适配文本
                item.setSizeHint(QtCore.QSize(target_tab.width(), item.sizeHint().height()))
                # ③ 添加Item到列表
                target_tab.addItem(item)
                target_tab.scrollToBottom()

    def print_sys_msg(self, text, target_tab):
        """向指定的标签页打印系统灰色提示"""
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

            # 发送上线注册
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

            # ===== 清空在线用户列表 =====
            self.connection_list.clear()

            # ===== 关闭所有私聊标签页，只保留群聊 =====
            # 先删除字典中所有私聊标签页记录
            self.private_tabs.clear()
            # 关闭除了第一个（群聊）之外的所有标签页
            while self.chat_tabs.count() > 1:
                self.chat_tabs.removeTab(1)

            self.clear_window()
            self.running_status.setText("Connection Closed")
            self.username.setEnabled(True)

    def clear_window(self):
        # 清除当前活跃标签页的聊天记录
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