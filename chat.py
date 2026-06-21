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
        # 标签页 (开启可关闭属性 tabsClosable)
        self.chat_tabs = QtWidgets.QTabWidget(self.layoutWidget)
        self.chat_tabs.setTabsClosable(True)  # 允许关闭私聊标签页

        self.group_chat_window = QtWidgets.QListWidget()
        # 核心修改：开启自动换行 + 自适应宽度
        self.group_chat_window.setWordWrap(True)
        self.group_chat_window.setResizeMode(QtWidgets.QListWidget.ResizeMode.Adjust)
        self.group_chat_window.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.group_chat_window.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        )

        # 默认只保留群聊页面
        self.chat_tabs.addTab(self.group_chat_window, "Group Chat (群聊)")
        self.gridLayout.addWidget(self.chat_tabs, 1, 0, 1, 6)

        # 在线用户列表 (提示双击私聊)
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
        # 调整了布局，取消了之前的下拉选择框
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