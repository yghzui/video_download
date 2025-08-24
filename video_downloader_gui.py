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
                             QComboBox, QCheckBox, QGroupBox, QSplitter, QMenu, QAction,
                             QTabWidget)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer, QPoint, QSettings
from PyQt5.QtGui import QFont, QIcon, QTextCursor, QMouseEvent
from PyQt5.QtWidgets import QApplication
from video_downloader import VideoDownloader
from history_manager import HistoryManager
from history_widget import HistoryWidget
from thumbnail_extractor import ThumbnailExtractor

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
    """下载工作线程（子进程模式，便于并发且不影响全局print）"""
    progress_signal = pyqtSignal(str)  # 进度信息信号
    download_progress_signal = pyqtSignal(int)  # 下载进度信号（保留，当前未精细使用）
    finished_signal = pyqtSignal(bool, str)  # 完成信号
    status_changed_signal = pyqtSignal()  # 状态变化信号
    
    def __init__(self, url, token=None, download_dir="downloads", task_name="", history_manager=None, existing_record_id=None):
        super().__init__()
        self.url = url
        self.token = token
        self.download_dir = download_dir
        self.task_name = task_name or url
        self.process = None  # 子进程句柄
        self.downloaded_files = []  # 存储下载的文件信息
        self.video_title = None  # 视频标题
        self.platform = None  # 平台类型
        self.history_manager = history_manager
        self.history_record_id = existing_record_id  # 历史记录ID，可能是现有的
        
        # 初始化缩略图提取器
        self.thumbnail_extractor = ThumbnailExtractor()
        
        # 如果没有现有记录ID，则创建新的历史记录条目
        if not existing_record_id:
            self._create_initial_history_record()
        else:
            # 重用现有记录，更新状态为下载中
            self._update_existing_record_status()
        
    def run(self):
        """运行下载任务（通过调用子进程执行 video_downloader.py 的一次性下载）"""
        try:
            # 确保下载目录存在
            Path(self.download_dir).mkdir(parents=True, exist_ok=True)
            
            # 组装命令：使用 -u 关闭缓冲，便于实时输出
            cmd = [
                sys.executable,
                '-u',
                'video_downloader.py',
                '--url', self.url,
                '--dir', self.download_dir
            ]
            if self.token:
                cmd += ['--token', self.token]
            
            self.progress_signal.emit(f"[{self.task_name}] 启动下载进程: {' '.join(cmd)}")
            
            # 启动子进程，合并stderr到stdout
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(Path('.').resolve()),
                bufsize=0
            )
            
            success = False
            buffer = ''
            
            # 按字符读取，兼容带\r的进度输出
            if self.process.stdout is not None:
                while True:
                    chunk = self.process.stdout.read(1)
                    if not chunk:
                        break
                    try:
                        ch = chunk.decode('utf-8', errors='ignore')
                    except AttributeError:
                        # 在某些环境下read返回str
                        ch = chunk
                    
                    if ch in ('\r', '\n'):
                        line = buffer.strip()
                        if line:
                            self.progress_signal.emit(f"[{self.task_name}] {line}")
                            # 解析下载信息
                            self._parse_download_info(line)
                        buffer = ''
                    else:
                        buffer += ch
            
            # 处理剩余缓冲
            if buffer.strip():
                self.progress_signal.emit(f"[{self.task_name}] {buffer.strip()}")
            
            # 等待子进程退出并基于退出码判定成功
            retcode = self.process.wait()
            final_success = (retcode == 0)
            if final_success:
                # 提取缩略图
                self._extract_thumbnails()
                # 保存历史记录
                self._save_history_record(True)
                self.finished_signal.emit(True, f"[{self.task_name}] 下载完成")
            else:
                # 保存失败记录
                self._save_history_record(False)
                self.finished_signal.emit(False, f"[{self.task_name}] 下载失败（退出码 {retcode}）")
        except Exception as e:
            # 保存异常记录
            self._save_history_record(False, error_msg=str(e))
            self.finished_signal.emit(False, f"[{self.task_name}] 下载过程中出现错误: {str(e)}")
    
    def _parse_download_info(self, line: str):
        """解析下载信息"""
        try:
            # 解析视频标题
            if "标题:" in line or "Title:" in line:
                title_match = re.search(r'(?:标题|Title)[:：]\s*(.+)', line)
                if title_match:
                    self.video_title = title_match.group(1).strip()
            
            # 解析平台信息
            if "douyin" in line.lower() or "抖音" in line:
                self.platform = "抖音"
            elif "bilibili" in line.lower() or "b站" in line or "哔哩哔哩" in line:
                self.platform = "哔哩哔哩"
            elif "kuaishou" in line.lower() or "快手" in line:
                self.platform = "快手"
            elif "xiaohongshu" in line.lower() or "小红书" in line:
                self.platform = "小红书"
            elif "youtube" in line.lower():
                self.platform = "YouTube"
            
            # 解析下载文件路径
            if "保存到:" in line or "Saved to:" in line or "下载完成:" in line:
                file_match = re.search(r'(?:保存到|Saved to|下载完成)[:：]\s*(.+)', line)
                if file_match:
                    file_path = file_match.group(1).strip()
                    if os.path.exists(file_path):
                        file_size = os.path.getsize(file_path)
                        self.downloaded_files.append({
                            'path': file_path,
                            'name': os.path.basename(file_path),
                            'size': file_size
                        })
        except Exception as e:
            print(f"解析下载信息时出错: {e}")
    
    def _create_initial_history_record(self):
        """创建初始历史记录条目"""
        try:
            if not self.history_manager:
                return
                
            # 创建初始记录，状态为downloading
            self.history_record_id = self.history_manager.add_record(
                url=self.url,
                title=self.task_name,  # 使用任务名作为初始标题
                status='downloading',
                platform="检测中...",
                thumbnail_path="thumbnails/default_thumb.jpg"  # 使用默认缩略图
            )
            
            # 发出状态变化信号
            self.status_changed_signal.emit()
            
        except Exception as e:
            print(f"创建初始历史记录时出错: {e}")
    
    def _update_existing_record_status(self):
        """更新现有记录状态为下载中"""
        try:
            if not self.history_manager or not self.history_record_id:
                return
                
            # 更新现有记录状态为downloading
            self.history_manager.update_record(
                self.history_record_id,
                status='downloading',
                download_time=time.strftime('%Y-%m-%d %H:%M:%S'),
                error_msg=None  # 清除之前的错误信息
            )
            
            # 发出状态变化信号
            self.status_changed_signal.emit()
            
        except Exception as e:
            print(f"更新现有记录状态时出错: {e}")
    
    def _save_history_record(self, success: bool, error_msg: str = None):
        """更新历史记录"""
        try:
            if not self.history_manager or not self.history_record_id:
                print(f"无法更新历史记录: history_manager={self.history_manager}, record_id={self.history_record_id}")
                return
                
            # 如果没有下载文件信息但成功了，尝试从下载目录查找
            if success and not self.downloaded_files:
                self._find_downloaded_files()
            
            # 准备更新数据
            update_data = {
                'title': self.video_title or self.task_name,
                'platform': self.platform or "未知平台",
                'status': 'success' if success else 'failed',
                'download_time': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 如果下载失败，添加错误信息
            if not success:
                update_data['error_msg'] = error_msg or "下载失败"
            else:
                # 成功时清除错误信息
                update_data['error_msg'] = None
            
            # 如果有下载文件，更新第一个文件的信息
            if self.downloaded_files:
                file_info = self.downloaded_files[0]  # 取第一个文件
                # 实际提取缩略图
                thumbnail_path = None
                video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v']
                if any(file_info['path'].lower().endswith(ext) for ext in video_extensions):
                    print(f"正在为 {file_info['name']} 提取缩略图...")
                    thumbnail_path = self.thumbnail_extractor.extract_thumbnail(file_info['path'])
                    print(f"缩略图提取结果: {thumbnail_path}")
                else:
                    print(f"文件 {file_info['name']} 不是视频文件，跳过缩略图提取")
                
                update_data.update({
                    'file_path': file_info['path'],
                    'file_name': file_info['name'],
                    'file_size': file_info['size'],
                    'thumbnail_path': thumbnail_path
                })
                
                # 如果有多个文件，为其他文件创建新记录
                for file_info in self.downloaded_files[1:]:
                    # 为每个额外文件也提取缩略图
                    thumbnail_path = None
                    if any(file_info['path'].lower().endswith(ext) for ext in video_extensions):
                        print(f"正在为 {file_info['name']} 提取缩略图...")
                        thumbnail_path = self.thumbnail_extractor.extract_thumbnail(file_info['path'])
                        print(f"缩略图提取结果: {thumbnail_path}")
                    
                    self.history_manager.add_record(
                        url=self.url,
                        title=self.video_title or self.task_name,
                        file_path=file_info['path'],
                        file_name=file_info['name'],
                        thumbnail_path=thumbnail_path,
                        file_size=file_info['size'],
                        status='success' if success else 'failed',
                        platform=self.platform or "未知平台"
                    )
            
            # 更新主记录
            print(f"正在更新历史记录 ID {self.history_record_id}: {update_data}")
            result = self.history_manager.update_record(self.history_record_id, **update_data)
            print(f"历史记录更新结果: {result}")
            
            # 发出状态变化信号
            self.status_changed_signal.emit()
            print(f"已发出状态变化信号")
            
        except Exception as e:
            print(f"更新历史记录时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def _extract_thumbnails(self):
        """为下载的视频文件提取缩略图"""
        try:
            if not self.downloaded_files:
                self._find_downloaded_files()
            
            # 为每个下载的视频文件提取缩略图
            for file_info in self.downloaded_files:
                file_path = file_info['path']
                # 检查是否为视频文件
                video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v']
                if any(file_path.lower().endswith(ext) for ext in video_extensions):
                    # 检查缩略图是否已存在
                    thumbnail_path = self.thumbnail_extractor.get_thumbnail_path(file_path)
                    if not os.path.exists(thumbnail_path):
                        self.progress_signal.emit(f"[{self.task_name}] 正在提取缩略图: {Path(file_path).name}")
                        self.thumbnail_extractor.extract_thumbnail(file_path)
                    else:
                        print(f"缩略图已存在，跳过提取: {thumbnail_path}")
        except Exception as e:
            print(f"提取缩略图时出错: {e}")
    
    def _find_downloaded_files(self):
        """从下载目录查找可能的下载文件"""
        try:
            download_path = Path(self.download_dir)
            if not download_path.exists():
                return
            
            # 获取最近修改的文件（可能是刚下载的）
            recent_files = []
            current_time = time.time()
            
            for file_path in download_path.rglob('*'):
                if file_path.is_file():
                    # 检查文件修改时间（最近5分钟内）
                    if current_time - file_path.stat().st_mtime < 300:
                        recent_files.append(file_path)
            
            # 按修改时间排序，取最新的
            recent_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            for file_path in recent_files[:3]:  # 最多取3个最新文件
                file_size = file_path.stat().st_size
                self.downloaded_files.append({
                    'path': str(file_path),
                    'name': file_path.name,
                    'size': file_size
                })
        except Exception as e:
            print(f"查找下载文件时出错: {e}")
        
    def terminate(self):
        """终止任务：终止子进程"""
        try:
            if self.process and self.process.poll() is None:
                self.process.kill()
        except Exception:
            pass
        finally:
            super().terminate()

class UrlTextEdit(QTextEdit):
    """
    支持识别链接的文本输入框
    右键菜单在识别到链接（优先使用选中文本，否则使用剪贴板文本）时，提供：
    - 换行追加链接：在末尾换行并追加该链接
    - 替换为该链接：用该链接替换全部内容
    内置悬浮按钮：清除内容和粘贴并下载
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # 仅接受纯文本，防止富文本粘贴带入样式
        self.setAcceptRichText(False)
        
        # 创建内部悬浮按钮
        self._create_floating_buttons()
        
    def _create_floating_buttons(self):
        """创建内部悬浮按钮"""
        # 清除按钮
        self.clear_btn = QPushButton("×", self)
        self.clear_btn.setFixedSize(20, 20)
        self.clear_btn.setToolTip("清除输入框内容")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
        """)
        self.clear_btn.clicked.connect(self._clear_content)
        
        # 粘贴并下载按钮
        self.paste_download_btn = QPushButton("📋↓", self)
        self.paste_download_btn.setFixedSize(20, 20)
        self.paste_download_btn.setToolTip("粘贴剪切板内容并开始下载")
        self.paste_download_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:pressed {
                background-color: #229954;
            }
        """)
        self.paste_download_btn.clicked.connect(self._paste_and_download)
        
        # 初始隐藏按钮
        self.clear_btn.hide()
        self.paste_download_btn.hide()
        
    def _clear_content(self):
        """清除输入框内容"""
        self.clear()
        
    def _paste_and_download(self):
        """粘贴剪切板内容并触发下载"""
        clipboard = QApplication.clipboard()
        if clipboard:
            clip_text = clipboard.text()
            if clip_text.strip():
                self.setPlainText(clip_text.strip())
                # 触发父窗口的下载功能
                parent_window = self.window()
                if hasattr(parent_window, 'start_download'):
                    parent_window.start_download()
                    
    def resizeEvent(self, event):
        """重写resize事件，调整按钮位置"""
        super().resizeEvent(event)
        self._update_button_positions()
        
    def _update_button_positions(self):
        """更新按钮位置"""
        # 获取输入框的几何信息
        rect = self.rect()
        button_margin = 3  # 距离边框的距离
        
        # 计算可用的垂直空间
        available_height = rect.height() - 2 * button_margin
        button_height = self.clear_btn.height()
        
        # 计算两个按钮的垂直位置，使其均匀分布
        # 将可用空间分为3等份：上间距、中间距、下间距
        spacing = (available_height - 2 * button_height) / 3
        
        # 清除按钮位置（上方1/3处）
        clear_x = rect.width() - self.clear_btn.width() - button_margin
        clear_y = button_margin + spacing
        self.clear_btn.move(clear_x, int(clear_y))
        
        # 粘贴下载按钮位置（下方2/3处）
        paste_x = rect.width() - self.paste_download_btn.width() - button_margin
        paste_y = clear_y + button_height + spacing
        self.paste_download_btn.move(paste_x, int(paste_y))
        
    def enterEvent(self, event):
        """鼠标进入时显示按钮"""
        super().enterEvent(event)
        self.clear_btn.show()
        self.paste_download_btn.show()
        
    def leaveEvent(self, event):
        """鼠标离开时隐藏按钮"""
        super().leaveEvent(event)
        self.clear_btn.hide()
        self.paste_download_btn.hide()

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
    
    # 信号定义
    history_updated = pyqtSignal()  # 历史记录更新信号
    
    def __init__(self):
        super().__init__()
        self.download_worker = None
        self.current_progress_line = None  # 当前进度行
        self.dragging = False  # 是否正在拖动窗口
        self.drag_position = QPoint()  # 拖动起始位置
        
        # 初始化QSettings
        self.settings = QSettings("config/app.ini", QSettings.IniFormat)
        
        # 初始化历史管理器
        self.history_manager = HistoryManager()
        
        self.init_ui()
        self.load_settings()  # 加载保存的设置
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("视频解析下载器 v1.1")
        self.setGeometry(100, 100, 1000, 700)
        
        # 设置窗口图标
        set_application_icon(self)
        
        # 并发与任务管理
        self.max_concurrency = 3  # 默认并发数
        self.pending_urls = []    # 等待中的URL
        self.active_workers = []  # 正在运行的workers
        self.completed_results = []  # (success, message)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建Tab控件
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                border-radius: 6px;
                background-color: white;
            }
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabBar::tab {
                background-color: #f0f0f0;
                border: 1px solid #c0c0c0;
                border-bottom-color: #c0c0c0;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                min-width: 120px;
                padding: 8px 16px;
                margin-right: 2px;
                font-size: 12px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom-color: white;
                color: #007bff;
            }
            QTabBar::tab:hover {
                background-color: #e9ecef;
            }
        """)
        
        # 创建下载页面
        self.download_tab = self.create_download_tab()
        self.tab_widget.addTab(self.download_tab, "📥 视频下载")
        
        # 创建历史记录页面
        self.history_tab = HistoryWidget()
        self.tab_widget.addTab(self.history_tab, "📋 历史记录")
        
        # 连接历史记录更新信号
        self.history_updated.connect(self.history_tab.refresh_history)
        
        main_layout.addWidget(self.tab_widget)
        
        # 设置状态栏
        self.statusBar().showMessage("就绪")
        
        # 设置鼠标追踪，用于检测鼠标移动
        self.setMouseTracking(True)
        
    def create_download_tab(self):
        """创建下载页面"""
        download_widget = QWidget()
        main_layout = QVBoxLayout(download_widget)
        
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
        
        return download_widget
        
    def load_settings(self):
        """加载保存的设置"""
        try:
            # 确保config目录存在
            config_dir = Path("config")
            config_dir.mkdir(exist_ok=True)
            
            # 加载下载目录
            download_dir = self.settings.value("download_dir", "downloads")
            self.dir_input.setText(download_dir)
            
            # 确保下载目录存在
            try:
                Path(download_dir).mkdir(parents=True, exist_ok=True)
                print(f"已确保下载目录存在: {download_dir}")
            except Exception as e:
                print(f"创建下载目录时出错: {e}")
            
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
            # 确保下载目录存在
            download_dir = self.dir_input.text()
            try:
                Path(download_dir).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"创建下载目录时出错: {e}")
            
            # 保存下载目录
            self.settings.setValue("download_dir", download_dir)
            
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
            
        # 处理多行输入，按行收集所有有效链接
        urls = [line.strip() for line in url_text.split('\n') if line.strip()]
        if not urls:
            QMessageBox.warning(self, "警告", "请输入有效的视频链接！")
            return
        
        # 检查重复下载并记录现有记录ID（基于文件路径）
        duplicate_urls = []
        valid_urls = []
        url_record_map = {}  # 存储URL到记录ID的映射
        
        for url in urls:
            # 使用新的基于文件路径的重复检查方法
            existing_record = self.history_manager.check_duplicate_by_file_path(url)
            if existing_record:
                status = existing_record.get('status')
                title = existing_record.get('title', url)
                record_id = existing_record.get('id')
                file_path = existing_record.get('file_path', '')
                url_record_map[url] = record_id  # 记录URL对应的记录ID
                
                if status == 'success' and file_path and os.path.exists(file_path):
                    duplicate_urls.append(f"• {title} (文件已存在: {os.path.basename(file_path)})")
                elif status == 'downloading':
                    duplicate_urls.append(f"• {title} (正在下载中)")
                else:
                    # 失败的记录或文件不存在可以重新下载
                    valid_urls.append(url)
            else:
                valid_urls.append(url)
                url_record_map[url] = None  # 新URL没有现有记录
        
        # 如果有重复的URL，询问用户是否继续
        if duplicate_urls:
            duplicate_list = "\n".join(duplicate_urls)
            reply = QMessageBox.question(
                self, "重复下载检查", 
                f"检测到以下视频已下载过：\n\n{duplicate_list}\n\n是否仍要继续下载？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                if not valid_urls:
                    return  # 如果没有有效URL，直接返回
                else:
                    # 只下载有效的URL
                    urls = valid_urls
            # 如果用户选择Yes，则继续下载所有URL
         
        # 初始化任务队列，同时保存URL到记录ID的映射
        self.pending_urls = urls.copy()
        self.url_record_map = url_record_map  # 保存映射关系供_start_next_workers使用
        self.completed_results = []
         
        if len(urls) > 1:
            self.log_message(f"检测到 {len(urls)} 个链接，启用并发下载（上限 {self.max_concurrency}）")
         
        # 禁用下载按钮，启用停止按钮
        self.download_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
         
        # 显示进度条（未知进度）
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
         
        # 清空日志
        self.log_text.clear()
        self.current_progress_line = None
         
        # 获取公共参数
        token = self.token_input.text().strip() or None
        self._common_token = token
        self._common_download_dir = self.dir_input.text()
         
        # 确保下载目录存在
        try:
            Path(self._common_download_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.log_message(f"❌ 创建下载目录失败: {e}")
            return
         
        # 启动并发任务
        self._start_next_workers()
         
        self.statusBar().showMessage("正在下载...")
        self.log_message("开始下载任务...")
        
    def add_download_task(self, url):
        """添加单个下载任务到输入框"""
        try:
            # 获取当前输入框内容
            current_text = self.url_input.toPlainText().strip()
            
            # 如果输入框为空，直接设置URL
            if not current_text:
                self.url_input.setPlainText(url)
            else:
                # 如果输入框有内容，添加到新行
                self.url_input.setPlainText(current_text + "\n" + url)
            
            # 自动开始下载
            self.start_download()
            
        except Exception as e:
            print(f"添加下载任务时出错: {e}")
            QMessageBox.warning(self, "错误", f"添加下载任务失败: {e}")
    
    def add_redownload_task(self, url, record_id):
        """添加重新下载任务，重用现有记录"""
        try:
            # 检查是否已有相同URL的下载任务正在进行
            for worker in self.active_workers:
                if worker.url == url:
                    QMessageBox.warning(self, "警告", "该视频正在下载中，请稍后再试")
                    return
            
            # 检查待下载队列中是否已有相同URL
            if url in self.pending_urls:
                QMessageBox.warning(self, "警告", "该视频已在下载队列中")
                return
            
            # 获取公共参数
            token = self._common_token if hasattr(self, '_common_token') else None
            download_dir = self._common_download_dir if hasattr(self, '_common_download_dir') else self.dir_input.text()
            
            # 确保下载目录存在
            try:
                Path(download_dir).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.log_message(f"❌ 创建下载目录失败: {e}")
                return
            
            # 创建重新下载任务
            task_name = f"重新下载-{record_id}"
            worker = DownloadWorker(url, token, download_dir, task_name, self.history_manager, existing_record_id=record_id)
            worker.progress_signal.connect(self.update_log)
            worker.finished_signal.connect(lambda success, message, w=worker: self._on_worker_finished(success, message, w))
            worker.status_changed_signal.connect(self.history_updated.emit)
            
            # 启动任务
            if len(self.active_workers) < self.max_concurrency:
                self.active_workers.append(worker)
                worker.start()
                self.log_message(f"[{task_name}] 已启动重新下载: {url}")
            else:
                self.pending_urls.append(url)
                self.log_message(f"[{task_name}] 已加入下载队列: {url}")
            
            # 启用停止按钮，显示进度条
            self.stop_btn.setEnabled(True)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            
            self.statusBar().showMessage("正在下载...")
            
        except Exception as e:
            print(f"添加重新下载任务时出错: {e}")
            QMessageBox.warning(self, "错误", f"添加重新下载任务失败: {e}")
        
    def _start_next_workers(self):
        """根据并发上限启动等待中的任务"""
        while self.pending_urls and len(self.active_workers) < self.max_concurrency:
            url = self.pending_urls.pop(0)
            task_name = f"任务{len(self.completed_results) + len(self.active_workers) + 1}"
            
            # 获取现有记录ID（如果有的话）
            existing_record_id = None
            if hasattr(self, 'url_record_map') and url in self.url_record_map:
                existing_record_id = self.url_record_map[url]
                if existing_record_id:
                    task_name = f"重新下载-{existing_record_id}"
            
            worker = DownloadWorker(url, self._common_token, self._common_download_dir, task_name, self.history_manager, existing_record_id)
            worker.progress_signal.connect(self.update_log)
            # 使用lambda捕获worker引用以便识别
            worker.finished_signal.connect(lambda success, message, w=worker: self._on_worker_finished(success, message, w))
            # 连接状态变化信号
            worker.status_changed_signal.connect(self.history_updated.emit)
            self.active_workers.append(worker)
            worker.start()
            self.log_message(f"[{task_name}] 已启动: {url}")
        
    def _on_worker_finished(self, success, message, worker):
        """单个任务结束回调，启动队列中下一项或收尾"""
        # 移除该worker
        try:
            if worker in self.active_workers:
               self.active_workers.remove(worker)
        except Exception:
            pass
        
        self.completed_results.append((success, message))
        self.log_message(message)
        
        # 发出历史记录更新信号
        self.history_updated.emit()
        
        # 若还有待启动任务则继续
        if self.pending_urls:
            self._start_next_workers()
        
        # 所有任务结束
        if not self.active_workers and not self.pending_urls:
            # 恢复按钮状态
            self.download_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.progress_bar.setVisible(False)
            
            total = len(self.completed_results)
            ok = sum(1 for s, _ in self.completed_results if s)
            if ok > 0 and ok == total:
                self.statusBar().showMessage("全部下载完成")
                self.log_message(f"✅ 全部下载完成：{ok}/{total}")
            elif ok > 0:
                self.statusBar().showMessage("部分下载完成")
                self.log_message(f"⚠️ 部分完成：{ok}/{total}")
            else:
                self.statusBar().showMessage("下载失败")
                self.log_message("❌ 所有任务均失败")
        
    def stop_download(self):
        """停止下载：终止所有正在进行的任务"""
        # 终止活动worker
        for worker in list(self.active_workers):
            try:
                worker.terminate()
            except Exception:
                pass
        self.active_workers.clear()
        self.pending_urls.clear()
        
        self.log_message("下载已停止")
        self.statusBar().showMessage("下载已停止")
        
        # 恢复按钮状态
        self.download_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
    def update_log(self, message):
        """更新日志显示"""
        # 检查消息中是否包含回车符(\r)
        if '\r' in message:
            # 提取任务ID
            task_id = None
            if "] [任务" in message:
                try:
                    task_id = message.split("[任务")[1].split("]")[0]
                except:
                    pass
            
            if task_id:
                # 获取当前文本内容
                current_text = self.log_text.toPlainText()
                lines = current_text.split('\n')
                
                # 从后往前查找该任务的最后一个进度行
                progress_line_index = None
                for i in range(len(lines) - 1, -1, -1):
                    if f"[任务{task_id}]" in lines[i]:
                        progress_line_index = i
                        break
                
                # 更新或添加进度行
                timestamp = time.strftime("%H:%M:%S")
                message_clean = message.replace('\r', '')
                log_entry = f"[{timestamp}] {message_clean}"
                
                if progress_line_index is not None:
                    # 更新现有的进度行
                    lines[progress_line_index] = log_entry
                else:
                    # 添加新的进度行
                    lines.append(log_entry)
                
                # 更新文本内容
                self.log_text.setPlainText('\n'.join(lines))
                
                # 自动滚动到底部
                cursor = self.log_text.textCursor()
                cursor.movePosition(QTextCursor.End)
                self.log_text.setTextCursor(cursor)
                return
        
        # 对于非进度消息，直接添加新行
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
        
        # 查找是否已有进度行（包含百分比的行）
        progress_line_index = None
        task_id = None
        
        # 从消息中提取任务ID
        if "] [任务" in message:
            task_id = message.split("[任务")[1].split("]")[0]
        
        if task_id:
            # 从后往前查找该任务的最后一个进度行
            for i in range(len(lines) - 1, -1, -1):
                if f"[任务{task_id}]" in lines[i] and "%" in lines[i]:
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