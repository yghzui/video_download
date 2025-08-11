#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频下载器GUI界面
基于PyQt5的视频下载器图形界面
"""

import sys
import os
import threading
import time
import re
import subprocess
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTextEdit, QLineEdit, QPushButton, 
                             QLabel, QProgressBar, QFileDialog, QMessageBox,
                             QComboBox, QCheckBox, QGroupBox, QSplitter, QMenu, QAction)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer, QPoint, QSettings
from PyQt5.QtGui import QFont, QIcon, QTextCursor, QMouseEvent
from PyQt5.QtWidgets import QApplication
from video_downloader import VideoDownloader

def set_application_icon(app_or_widget=None):
    """
    设置应用程序图标
    
    Args:
        app_or_widget: QApplication实例或QWidget实例，如果为None则尝试获取当前应用
    """
    # 图标文件优先级列表
    icon_candidates = [
        "icon/app.png",
        "image/logo.png", 
        "image/logo-icon.png",
        "image/down-icon.png",
        "image/logomin.png"
    ]
    
    icon_path = None
    for candidate in icon_candidates:
        path = Path(candidate)
        if path.exists():
            icon_path = path
            break
    
    if icon_path:
        icon = QIcon(str(icon_path))
        if app_or_widget:
            app_or_widget.setWindowIcon(icon)
        else:
            # 尝试获取当前应用实例
            app = QApplication.instance()
            if app:
                app.setWindowIcon(icon)
        print(f"已设置应用程序图标: {icon_path}")
    else:
        print("未找到可用的图标文件")

class DownloadWorker(QThread):
    """下载工作线程"""
    progress_signal = pyqtSignal(str)  # 进度信息信号
    download_progress_signal = pyqtSignal(int)  # 下载进度信号
    finished_signal = pyqtSignal(bool, str)  # 完成信号
    
    def __init__(self, url, token=None, download_dir="downloads"):
        super().__init__()
        self.url = url
        self.token = token
        self.download_dir = download_dir
        self.downloader = None
        
    def run(self):
        """运行下载任务"""
        try:
            self.progress_signal.emit("正在初始化下载器...")
            self.downloader = VideoDownloader(self.download_dir)
            
            # 重写下载器的输出方法，将信息发送到GUI
            def custom_print(*args, **kwargs):
                # 处理所有参数，包括end等关键字参数
                message = ' '.join(str(arg) for arg in args)
                if message.strip():  # 只发送非空消息
                    # 检查是否是进度信息（包含\r的）
                    if '\r' in message:
                        # 提取进度百分比信息
                        progress_match = re.search(r'下载进度:\s*(\d+\.?\d*)%', message)
                        if progress_match:
                            progress = progress_match.group(1)
                            self.progress_signal.emit(f"下载进度: {progress}%")
                        else:
                            # 移除\r并发送消息
                            clean_message = message.replace('\r', '').strip()
                            if clean_message:
                                self.progress_signal.emit(clean_message)
                    else:
                        self.progress_signal.emit(message)
            
            # 替换下载器的print函数
            import builtins
            original_print = builtins.print
            builtins.print = custom_print
            
            try:
                self.progress_signal.emit("开始解析视频...")
                result = self.downloader.parse_video(self.url, self.token)
                
                if not result:
                    self.finished_signal.emit(False, "视频解析失败")
                    return
                
                # 获取视频列表
                video_list = result.get('voideDeatilVoList', [])
                if not video_list:
                    self.finished_signal.emit(False, "未找到可下载的视频")
                    return
                
                # 获取视频标题
                video_title = result.get('title', '')
                if not video_title:
                    # 尝试从第一个视频项中获取标题
                    if video_list and len(video_list) > 0:
                        video_title = video_list[0].get('title', '')
                
                self.progress_signal.emit(f"找到 {len(video_list)} 个文件")
                if video_title:
                    self.progress_signal.emit(f"视频标题: {video_title}")
                
                # 下载文件
                success_count = 0
                for i, item in enumerate(video_list):
                    file_url = item.get('url')
                    file_type = item.get('type', 'video')
                    
                    if not file_url:
                        continue
                    
                    # 生成文件名
                    if file_type == 'image':
                        extension = '.jpg'
                    else:
                        extension = '.mp4'
                    
                    # 使用视频标题命名文件（如果可用）
                    if video_title and video_title.strip():
                        # 清理标题中的非法字符
                        safe_title = self._sanitize_filename(video_title)
                        if len(video_list) == 1:
                            # 单个文件，直接使用标题
                            filename = f"{safe_title}{extension}"
                        else:
                            # 多个文件，添加索引
                            filename = f"{safe_title}_{i+1}{extension}"
                    else:
                        # 从URL中提取文件名，如果没有则使用默认名称
                        from urllib.parse import urlparse
                        parsed_url = urlparse(file_url)
                        original_filename = os.path.basename(parsed_url.path)
                        
                        if original_filename and '.' in original_filename:
                            filename = f"{i+1}_{original_filename}"
                        else:
                            filename = f"{i+1}_file{extension}"
                    
                    self.progress_signal.emit(f"正在下载: {filename}")
                    
                    # 下载文件
                    if self.downloader.download_file(file_url, filename):
                        success_count += 1
                        self.progress_signal.emit(f"下载成功: {filename}")
                    else:
                        self.progress_signal.emit(f"下载失败: {filename}")
                    
                    self.progress_signal.emit("-" * 30)
                
                if success_count > 0:
                    self.finished_signal.emit(True, f"下载完成！成功下载 {success_count}/{len(video_list)} 个文件")
                else:
                    self.finished_signal.emit(False, "所有文件下载失败")
                    
            finally:
                # 恢复原始的print函数
                builtins.print = original_print
                
        except Exception as e:
            self.finished_signal.emit(False, f"下载过程中出现错误: {str(e)}")
    
    def _sanitize_filename(self, filename):
        """
        清理文件名，移除或替换非法字符
        
        Args:
            filename (str): 原始文件名
            
        Returns:
            str: 清理后的文件名
        """
        import re
        # Windows文件系统不允许的字符
        illegal_chars = r'[<>:"/\\|?*]'
        # 替换为下划线
        safe_name = re.sub(illegal_chars, '_', filename)
        # 移除首尾空格和点
        safe_name = safe_name.strip(' .')
        # 限制长度（Windows路径限制）
        if len(safe_name) > 200:
            safe_name = safe_name[:200]
        return safe_name

class UrlTextEdit(QTextEdit):
    """
    支持识别链接的文本输入框
    右键菜单在识别到链接（优先使用选中文本，否则使用剪贴板文本）时，提供：
    - 换行追加链接：在末尾换行并追加该链接
    - 替换为该链接：用该链接替换全部内容
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # 仅接受纯文本，防止富文本粘贴带入样式
        self.setAcceptRichText(False)

    def contextMenuEvent(self, event):
        # 使用系统默认菜单作为基础
        menu: QMenu = self.createStandardContextMenu()

        # 尝试获取候选链接（优先选中文本，否则剪贴板）
        candidate_url = self._get_candidate_url()
        if candidate_url:
            menu.addSeparator()
            append_action = QAction("换行追加链接", self)
            replace_action = QAction("替换为该链接", self)

            def do_append():
                # 在末尾换行并追加链接
                current_text = self.toPlainText()
                if current_text and not current_text.endswith("\n"):
                    current_text += "\n"
                current_text += candidate_url
                self.setPlainText(current_text)
                # 光标移至末尾
                cursor = self.textCursor()
                cursor.movePosition(QTextCursor.End)
                self.setTextCursor(cursor)

            def do_replace():
                # 用该链接替换全部内容
                self.setPlainText(candidate_url)
                cursor = self.textCursor()
                cursor.movePosition(QTextCursor.End)
                self.setTextCursor(cursor)

            append_action.triggered.connect(do_append)
            replace_action.triggered.connect(do_replace)
            menu.addAction(append_action)
            menu.addAction(replace_action)

        menu.exec_(event.globalPos())

    def _get_candidate_url(self) -> str:
        """
        返回可用作链接的文本：优先使用选中的文本，否则使用剪贴板文本。
        未找到或不满足链接格式时返回空字符串。
        """
        # 优先：选中文本
        cursor = self.textCursor()
        selected_text = cursor.selectedText().strip()
        # QTextEdit 的 selectedText 中换行可能为 \u2029，统一处理
        selected_text = selected_text.replace("\u2029", "\n")
        if self._is_url(selected_text):
            return selected_text

        # 备选：剪贴板
        clipboard = QApplication.clipboard()
        if clipboard:
            clip_text = (clipboard.text() or "").strip()
            if self._is_url(clip_text):
                return clip_text

        return ""

    def _is_url(self, text: str) -> bool:
        """简单判断文本是否为链接"""
        if not text:
            return False
        # 识别 http/https 或 www. 开头的常见链接格式
        pattern = re.compile(r'^(https?://|www\.)\S+$', re.IGNORECASE)
        return bool(pattern.match(text))

class VideoDownloaderGUI(QMainWindow):
    """视频下载器GUI主窗口"""
    
    def __init__(self):
        super().__init__()
        self.download_worker = None
        self.current_progress_line = None  # 当前进度行
        self.dragging = False  # 是否正在拖动窗口
        self.drag_position = QPoint()  # 拖动起始位置
        
        # 初始化QSettings
        self.settings = QSettings("config/app.ini", QSettings.IniFormat)
        
        self.init_ui()
        self.load_settings()  # 加载保存的设置
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("视频解析下载器 v1.0")
        self.setGeometry(100, 100, 900, 650)
        
        # 设置窗口图标
        set_application_icon(self)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        
        # # 创建标题
        # title_label = QLabel("视频解析下载器")
        # title_label.setAlignment(Qt.AlignCenter)
        # title_label.setFont(QFont("Arial", 16, QFont.Bold))
        # title_label.setStyleSheet("color: #2c3e50; margin: 10px;")
        # main_layout.addWidget(title_label)
        
        # 创建输入区域
        input_group = QGroupBox("下载设置")
        input_layout = QVBoxLayout(input_group)
        
        # URL输入
        url_layout = QVBoxLayout()
        self.url_input = UrlTextEdit()
        self.url_input.setAcceptRichText(False)  # 禁用富文本粘贴，避免携带背景色/字体色
        self.url_input.setPlaceholderText("请输入视频链接（支持抖音、B站、快手、小红书、YouTube等）\n可以输入多个链接，每行一个")
        self.url_input.setMaximumHeight(100)  # 限制高度，避免占用太多空间
        self.url_input.setMinimumHeight(60)   # 设置最小高度
        self.url_input.setStyleSheet("""
            QTextEdit {
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
                background-color: #ffffff;
            }
            QTextEdit:focus {
                border-color: #3498db;
            }
        """)
        
        url_layout.addWidget(self.url_input)
        input_layout.addLayout(url_layout)
        
        # Token输入
        token_layout = QHBoxLayout()
        token_label = QLabel("用户Token:")
        token_label.setMinimumWidth(80)
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("可选，用于需要登录的视频")
        self.token_input.textChanged.connect(self.on_token_input_changed)  # 监听文本变化
        token_layout.addWidget(token_label)
        token_layout.addWidget(self.token_input)
        input_layout.addLayout(token_layout)
        
        # 下载目录选择
        dir_layout = QHBoxLayout()
        dir_label = QLabel("下载目录:")
        dir_label.setMinimumWidth(80)
        self.dir_input = QLineEdit("downloads")
        self.dir_input.setPlaceholderText("请输入或选择下载目录")
        self.dir_input.textChanged.connect(self.on_dir_input_changed)  # 监听文本变化
        self.browse_btn = QPushButton("浏览")
        self.browse_btn.setToolTip("选择下载文件夹")
        self.browse_btn.clicked.connect(self.browse_directory)
        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(self.browse_btn)
        input_layout.addLayout(dir_layout)
        
        main_layout.addWidget(input_group)
        
        # 创建控制按钮
        button_layout = QHBoxLayout()
        
        self.download_btn = QPushButton("开始下载")
        self.download_btn.setToolTip("开始下载视频文件")
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        self.download_btn.clicked.connect(self.start_download)
        
        self.stop_btn = QPushButton("停止下载")
        self.stop_btn.setToolTip("停止当前下载任务")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_download)
        self.stop_btn.setEnabled(False)
        
        self.clear_btn = QPushButton("清空日志")
        self.clear_btn.setToolTip("清空下载日志")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.clear_btn.clicked.connect(self.clear_log)
        
        self.clear_input_btn = QPushButton("清空输入")
        self.clear_input_btn.setToolTip("清空链接和Token输入框")
        self.clear_input_btn.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #e67e22;
            }
        """)
        self.clear_input_btn.clicked.connect(self.clear_input)
        
        self.open_folder_btn = QPushButton("打开文件夹")
        self.open_folder_btn.setToolTip("打开下载文件夹，查看已下载的文件")
        self.open_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
        """)
        self.open_folder_btn.clicked.connect(self.open_download_folder)
        
        button_layout.addWidget(self.download_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addWidget(self.clear_input_btn)
        button_layout.addWidget(self.open_folder_btn)
        button_layout.addStretch()
        
        main_layout.addLayout(button_layout)
        
        # 创建进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # 创建日志显示区域
        log_group = QGroupBox("下载日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setAcceptRichText(False)  # 仅接受纯文本，避免外部粘贴带入样式
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 1px solid #34495e;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        log_layout.addWidget(self.log_text)
        
        main_layout.addWidget(log_group)
        
        # 设置状态栏
        self.statusBar().showMessage("就绪")
        
        # 设置鼠标追踪，用于检测鼠标移动
        self.setMouseTracking(True)
        
    def load_settings(self):
        """加载保存的设置"""
        try:
            # 确保config目录存在
            config_dir = Path("config")
            config_dir.mkdir(exist_ok=True)
            
            # 加载下载目录
            download_dir = self.settings.value("download_dir", "downloads")
            self.dir_input.setText(download_dir)
            
            # 加载用户Token
            token = self.settings.value("user_token", "")
            self.token_input.setText(token)
            
            # 加载窗口位置和大小
            geometry = self.settings.value("window_geometry")
            if geometry:
                self.restoreGeometry(geometry)
            
            print("设置加载成功")
            
        except Exception as e:
            print(f"加载设置时出错: {e}")
    
    def save_settings(self):
        """保存当前设置"""
        try:
            # 保存下载目录
            self.settings.setValue("download_dir", self.dir_input.text())
            
            # 保存用户Token
            self.settings.setValue("user_token", self.token_input.text())
            
            # 保存窗口位置和大小
            self.settings.setValue("window_geometry", self.saveGeometry())
            
            # 同步设置到文件
            self.settings.sync()
            
            print("设置保存成功")
            
        except Exception as e:
            print(f"保存设置时出错: {e}")
    
    def on_dir_input_changed(self, text):
        """下载目录输入框文本变化事件"""
        # 延迟保存，避免频繁保存
        if hasattr(self, '_dir_save_timer'):
            self._dir_save_timer.stop()
        else:
            self._dir_save_timer = QTimer()
            self._dir_save_timer.setSingleShot(True)
            self._dir_save_timer.timeout.connect(self.save_settings)
        
        self._dir_save_timer.start(1000)  # 1秒后保存
    
    def on_token_input_changed(self, text):
        """Token输入框文本变化事件"""
        # 延迟保存，避免频繁保存
        if hasattr(self, '_token_save_timer'):
            self._token_save_timer.stop()
        else:
            self._token_save_timer = QTimer()
            self._token_save_timer.setSingleShot(True)
            self._token_save_timer.timeout.connect(self.save_settings)
        
        self._token_save_timer.start(1000)  # 1秒后保存
    
    def browse_directory(self):
        """浏览并选择下载目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择下载目录", self.dir_input.text())
        if dir_path:
            self.dir_input.setText(dir_path)
            # 保存设置
            self.save_settings()
            
    def start_download(self):
        """开始下载"""
        url_text = self.url_input.toPlainText().strip()
        if not url_text:
            QMessageBox.warning(self, "警告", "请输入视频链接！")
            return
            
        # 处理多行输入，取第一个非空行作为下载链接
        urls = [line.strip() for line in url_text.split('\n') if line.strip()]
        if not urls:
            QMessageBox.warning(self, "警告", "请输入有效的视频链接！")
            return
            
        url = urls[0]  # 暂时只处理第一个链接，后续可以扩展为批量下载
        if len(urls) > 1:
            self.log_message(f"检测到多个链接，当前只处理第一个链接: {url}")
            self.log_message(f"其他链接: {', '.join(urls[1:])}")
            
        # 禁用下载按钮，启用停止按钮
        self.download_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        
        # 清空日志
        self.log_text.clear()
        self.current_progress_line = None  # 重置进度行
        
        # 获取参数
        token = self.token_input.text().strip() or None
        download_dir = self.dir_input.text()
        
        # 确保下载目录存在
        try:
            Path(download_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.log_message(f"❌ 创建下载目录失败: {e}")
            return
        
        # 创建并启动下载线程
        self.download_worker = DownloadWorker(url, token, download_dir)
        self.download_worker.progress_signal.connect(self.update_log)
        self.download_worker.finished_signal.connect(self.download_finished)
        self.download_worker.start()
        
        self.statusBar().showMessage("正在下载...")
        self.log_message("开始下载任务...")
        
    def stop_download(self):
        """停止下载"""
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.terminate()
            self.download_worker.wait()
            self.log_message("下载已停止")
            self.statusBar().showMessage("下载已停止")
            
        # 恢复按钮状态
        self.download_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
    def download_finished(self, success, message):
        """下载完成回调"""
        # 恢复按钮状态
        self.download_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        # 显示结果
        if success:
            self.log_message(f"✅ {message}")
            self.statusBar().showMessage("下载完成")
            
            # # 询问是否打开下载文件夹
            # reply = QMessageBox.question(self, "下载完成", 
            #                            f"{message}\n\n是否要打开下载文件夹？",
            #                            QMessageBox.Yes | QMessageBox.No,
            #                            QMessageBox.Yes)
            # if reply == QMessageBox.Yes:
            #     self.open_download_folder()
        else:
            self.log_message(f"❌ {message}")
            self.statusBar().showMessage("下载失败")
            QMessageBox.warning(self, "失败", message)
            
    def update_log(self, message):
        """更新日志显示"""
        # 检查是否是进度信息（包含百分比）
        if '%' in message and any(char.isdigit() for char in message):
            self.update_progress_message(message)
        else:
            self.log_message(message)
        
    def log_message(self, message):
        """添加日志消息"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.log_text.append(log_entry)
        
        # 自动滚动到底部
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)
        
    def update_progress_message(self, message):
        """更新进度消息（在同一行显示）"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        
        # 获取当前文本内容
        current_text = self.log_text.toPlainText()
        lines = current_text.split('\n')
        
        # 查找是否已有进度行（包含"下载进度"的行）
        progress_line_index = None
        for i, line in enumerate(lines):
            if "下载进度:" in line:
                progress_line_index = i
                break
        
        if progress_line_index is not None:
            # 更新现有的进度行
            lines[progress_line_index] = log_entry
            self.current_progress_line = progress_line_index
        else:
            # 添加新的进度行
            lines.append(log_entry)
            self.current_progress_line = len(lines) - 1
        
        # 更新文本内容
        self.log_text.setPlainText('\n'.join(lines))
        
        # 自动滚动到底部
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)
        
    def clear_log(self):
        """清空日志"""
        self.log_text.clear()
        self.current_progress_line = None  # 重置进度行
        
    def clear_input(self):
        """清空输入框"""
        self.url_input.clear()
        self.token_input.clear()
        # 保存设置（清空token）
        self.save_settings()
        
    def open_download_folder(self):
        """打开下载文件夹"""
        try:
            download_path = Path(self.dir_input.text())
            if not download_path.exists():
                # 如果文件夹不存在，创建它
                download_path.mkdir(parents=True, exist_ok=True)
                self.log_message(f"创建下载文件夹: {download_path}")
            
            os.startfile(download_path)
                
            self.log_message(f"已打开下载文件夹: {download_path}")
            
        except subprocess.CalledProcessError as e:
            error_msg = f"无法打开文件夹: {e}"
            self.log_message(f"❌ {error_msg}")
            QMessageBox.warning(self, "错误", error_msg)
        except Exception as e:
            error_msg = f"打开文件夹时出现错误: {e}"
            self.log_message(f"❌ {error_msg}")
            QMessageBox.warning(self, "错误", error_msg)
        
    def closeEvent(self, event):
        """窗口关闭事件"""
        if self.download_worker and self.download_worker.isRunning():
            reply = QMessageBox.question(self, "确认退出", 
                                       "下载正在进行中，确定要退出吗？",
                                       QMessageBox.Yes | QMessageBox.No,
                                       QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.stop_download()
                # 保存设置
                self.save_settings()
                event.accept()
            else:
                event.ignore()
        else:
            # 保存设置
            self.save_settings()
            event.accept()
    
    def mousePressEvent(self, event: QMouseEvent):
        """
        鼠标按下事件
        在非控件区域按下鼠标左键时开始拖动窗口
        """
        if event.button() == Qt.LeftButton:
            # 检查点击位置是否在控件上
            child_widget = self.childAt(event.pos())
            if child_widget is None or not self._is_clickable_widget(child_widget):
                # 在非控件区域点击，开始拖动
                self.dragging = True
                self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()
            else:
                # 在控件上点击，不处理拖动
                event.ignore()
        else:
            event.ignore()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """
        鼠标移动事件
        在拖动状态下移动窗口
        """
        if self.dragging and event.buttons() & Qt.LeftButton:
            # 计算新位置并移动窗口
            new_pos = event.globalPos() - self.drag_position
            self.move(new_pos)
            event.accept()
        else:
            event.ignore()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """
        鼠标释放事件
        停止拖动
        """
        if event.button() == Qt.LeftButton:
            self.dragging = False
            event.accept()
        else:
            event.ignore()
    
    def _is_clickable_widget(self, widget):
        """
        判断是否为可点击的控件
        
        Args:
            widget: 要检查的控件
            
        Returns:
            bool: 是否为可点击控件
        """
        # 定义可点击的控件类型
        clickable_types = [
            'QPushButton', 'QLineEdit', 'QTextEdit', 'QComboBox', 
            'QCheckBox', 'QProgressBar', 'QGroupBox', 'QLabel'
        ]
        
        widget_type = type(widget).__name__
        
        # 检查控件类型
        if widget_type in clickable_types:
            return True
        
        # 检查控件是否启用
        if hasattr(widget, 'isEnabled') and not widget.isEnabled():
            return False
        
        # 检查控件是否可见
        if hasattr(widget, 'isVisible') and not widget.isVisible():
            return False
        
        # 对于QLabel，检查是否有文本或图片（可点击的标签）
        if widget_type == 'QLabel':
            if widget.text().strip() or widget.pixmap():
                return True
        
        return False

def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName("视频解析下载器")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("VideoDownloader")
    
    # 设置应用程序图标
    set_application_icon(app)
    
    # 创建主窗口
    window = VideoDownloaderGUI()
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 