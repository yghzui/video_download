# -*- coding: utf-8 -*-
"""
历史记录界面组件
实现包含缩略图、文件信息、操作按钮的列表界面
"""

import os
import sys
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QLineEdit, QComboBox, QFrame, QSizePolicy,
    QMessageBox, QMenu, QAction, QProgressBar, QScrollArea, QApplication,
    QInputDialog
)
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QIcon, QFont, QPalette, QColor, QImage, QPainter

from history_manager import HistoryManager


class ClickableLabel(QLabel):
    """支持间隔双击重命名的标签"""
    
    # 信号定义
    rename_requested = pyqtSignal()  # 重命名请求信号
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.original_text = text
        self.edit_mode = False
        self.line_edit = None
        
        # 设置右键菜单
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, position):
        """显示右键菜单"""
        if self.edit_mode:
            return
            
        menu = QMenu(self)
        rename_action = menu.addAction("重命名文件")
        rename_action.triggered.connect(self.request_file_rename)
        
        menu.exec_(self.mapToGlobal(position))
    
    def request_file_rename(self):
        """请求文件重命名"""
        # 发出重命名信号，让父组件处理文件重命名逻辑
        self.rename_requested.emit()
    
    def start_edit_mode(self):
        """开始编辑模式"""
        if self.edit_mode:
            return
            
        self.edit_mode = True
        self.original_text = self.text()
        
        # 创建编辑框
        self.line_edit = QLineEdit(self.original_text)
        self.line_edit.setFont(self.font())
        self.line_edit.setStyleSheet(self.styleSheet())
        
        # 替换标签为编辑框
        layout = self.parent().layout()
        if layout:
            index = layout.indexOf(self)
            if index >= 0:
                layout.removeWidget(self)
                layout.insertWidget(index, self.line_edit)
                self.hide()
                
                # 连接信号
                self.line_edit.editingFinished.connect(self.finish_edit_mode)
                self.line_edit.returnPressed.connect(self.finish_edit_mode)
                
                # 选中所有文本并获得焦点
                self.line_edit.selectAll()
                self.line_edit.setFocus()
    
    def finish_edit_mode(self):
        """结束编辑模式"""
        if not self.edit_mode or not self.line_edit:
            return
            
        new_text = self.line_edit.text().strip()
        
        # 恢复标签
        layout = self.parent().layout()
        if layout:
            index = layout.indexOf(self.line_edit)
            if index >= 0:
                layout.removeWidget(self.line_edit)
                layout.insertWidget(index, self)
                self.show()
        
        # 清理编辑框
        self.line_edit.deleteLater()
        self.line_edit = None
        self.edit_mode = False
        
        # 如果文本有变化，发出重命名信号
        if new_text and new_text != self.original_text:
            self.setText(new_text)
            self.rename_requested.emit(new_text)


class CopyableLabel(QLabel):
    """支持右键复制的标签"""
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def show_context_menu(self, position):
        """显示右键菜单"""
        menu = QMenu(self)
        
        # 复制链接动作
        copy_action = QAction("复制链接", self)
        copy_action.triggered.connect(self.copy_url)
        menu.addAction(copy_action)
        
        # 显示菜单
        menu.exec_(self.mapToGlobal(position))
    
    def copy_url(self):
        """复制URL到剪贴板"""
        text = self.text()
        # 提取URL部分（去掉"链接: "前缀）
        if text.startswith("链接: "):
            url = text[4:]  # 去掉"链接: "前缀
        else:
            url = text
        
        clipboard = QApplication.clipboard()
        clipboard.setText(url)
        
        # 可以添加提示信息
        print(f"已复制链接: {url}")


class HistoryItemWidget(QFrame):
    """历史记录项组件"""
    
    # 信号定义
    open_folder_requested = pyqtSignal(str)  # 打开文件夹信号
    delete_file_requested = pyqtSignal(int, str)  # 删除文件信号 (record_id, file_path)
    delete_record_requested = pyqtSignal(int)  # 删除记录信号
    redownload_requested = pyqtSignal(str, int)  # 重新下载信号 (url, record_id)
    rename_requested = pyqtSignal(int, str)  # 重命名信号 (record_id, new_name)
    
    def __init__(self, record_data, parent=None):
        super().__init__(parent)
        self.record_data = record_data
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI界面"""
        self.setFrameStyle(QFrame.Box)
        self.setLineWidth(1)
        # 设置固定高度，确保所有历史记录项高度一致
        self.setFixedHeight(100)
        
        # 根据记录状态设置样式
        status = self.record_data.get('status', 'success')
        if status == 'file_deleted':
            # 文件已删除状态 - 深灰色显示
            self.setStyleSheet("""
                HistoryItemWidget {
                    background-color: #d6d8db;
                    border: 1px solid #868e96;
                    border-radius: 8px;
                    margin: 2px;
                }
                HistoryItemWidget:hover {
                    background-color: #ced4da;
                    border-color: #6c757d;
                }
                QLabel {
                    color: #495057;
                }
                QPushButton {
                    background-color: #adb5bd;
                    color: #495057;
                    border: 1px solid #868e96;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #868e96;
                    color: #343a40;
                }
            """)
        else:
            # 正常状态
            self.setStyleSheet("""
                HistoryItemWidget {
                    background-color: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 8px;
                    margin: 2px;
                }
                HistoryItemWidget:hover {
                    background-color: #e9ecef;
                    border-color: #adb5bd;
                }
            """)
        
        # 主布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(12)
        
        # 缩略图区域 - 以容器高度为基准设置缩略图尺寸
        thumbnail_height = 80  # 容器高度减去边距
        thumbnail_width = int(thumbnail_height * 4 / 3)  # 4:3比例
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(thumbnail_width, thumbnail_height)
        # 根据状态设置缩略图样式
        if status == 'file_deleted':
            self.thumbnail_label.setStyleSheet("""
                QLabel {
                    border: 1px solid #868e96;
                    border-radius: 4px;
                    background-color: #ced4da;
                    opacity: 0.5;
                }
            """)
        else:
            self.thumbnail_label.setStyleSheet("""
                QLabel {
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                    background-color: #ffffff;
                }
            """)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        # 不使用setScaledContents，改为在load_thumbnail中手动缩放
        
        # 加载缩略图
        self.load_thumbnail()
        
        # 左侧：缩略图区域
        main_layout.addWidget(self.thumbnail_label)
        
        # 中间：信息区域
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        # 标题（使用文件名，去除扩展名）- 支持双击重命名
        file_path = self.record_data.get('file_path', '')
        if file_path:
            # 获取文件名并去除扩展名
            file_name = os.path.basename(file_path)
            title_text = os.path.splitext(file_name)[0]  # 去除扩展名
        else:
            title_text = self.record_data.get('title', '未知标题')
        
        self.title_label = ClickableLabel(title_text)
        self.title_label.setFont(QFont('Microsoft YaHei', 10, QFont.Bold))
        self.title_label.setStyleSheet("color: #212529;")
        self.title_label.setWordWrap(True)
        # 连接重命名信号
        self.title_label.rename_requested.connect(self.on_title_rename)
        info_layout.addWidget(self.title_label)
        
        # URL（完整显示，支持自动换行和右键复制）
        full_url = self.record_data.get('url', '')
        self.url_label = CopyableLabel(f"链接: {full_url}")
        self.url_label.setFont(QFont('Microsoft YaHei', 8))
        self.url_label.setStyleSheet("color: #6c757d;")
        self.url_label.setWordWrap(True)  # 启用自动换行
        self.url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)  # 允许选择文本
        info_layout.addWidget(self.url_label)
        
        # 文件路径
        file_path = self.record_data.get('file_path', '')
        if file_path:
            file_name = os.path.basename(file_path)
            path_label = QLabel(f"文件: {file_name}")
        else:
            path_label = QLabel("文件: 未找到")
        path_label.setFont(QFont('Microsoft YaHei', 8))
        path_label.setStyleSheet("color: #495057;")
        info_layout.addWidget(path_label)
        
        # 详细信息行
        details_layout = QHBoxLayout()
        details_layout.setSpacing(15)
        
        # 下载时间
        download_time = self.record_data.get('download_time', '')
        if download_time:
            try:
                dt = datetime.fromisoformat(download_time.replace('Z', '+00:00'))
                time_str = dt.strftime('%Y-%m-%d %H:%M')
            except:
                time_str = download_time
        else:
            time_str = '未知时间'
        time_label = QLabel(f"时间: {time_str}")
        time_label.setFont(QFont('Microsoft YaHei', 7))
        time_label.setStyleSheet("color: #868e96;")
        details_layout.addWidget(time_label)
        
        # 文件大小
        file_size = self.record_data.get('file_size', 0)
        if file_size and file_size > 0:
            size_str = self.format_file_size(file_size)
        else:
            size_str = '未知大小'
        size_label = QLabel(f"大小: {size_str}")
        size_label.setFont(QFont('Microsoft YaHei', 7))
        size_label.setStyleSheet("color: #868e96;")
        details_layout.addWidget(size_label)
        
        # 平台
        platform = self.record_data.get('platform', '未知')
        platform_label = QLabel(f"平台: {platform}")
        platform_label.setFont(QFont('Microsoft YaHei', 7))
        platform_label.setStyleSheet("color: #868e96;")
        details_layout.addWidget(platform_label)
        
        # 状态
        status = self.record_data.get('status', 'unknown')
        status_text = {'success': '成功', 'failed': '失败', 'downloading': '下载中'}.get(status, '未知')
        status_color = {'success': '#28a745', 'failed': '#dc3545', 'downloading': '#ffc107'}.get(status, '#6c757d')
        status_label = QLabel(f"状态: {status_text}")
        status_label.setFont(QFont('Microsoft YaHei', 7))
        status_label.setStyleSheet(f"color: {status_color}; font-weight: bold;")
        details_layout.addWidget(status_label)
        
        details_layout.addStretch()
        info_layout.addLayout(details_layout)
        
        info_layout.addStretch()
        main_layout.addLayout(info_layout, 1)
        
        # 右侧：操作按钮区域
        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(6)
        buttons_layout.setContentsMargins(0, 0, 0, 0)  # 移除上下边距
        buttons_layout.setAlignment(Qt.AlignTop)  # 顶部对齐
        
        # 打开文件夹按钮
        open_folder_btn = QPushButton("📁")
        open_folder_btn.setFixedSize(35, 35)
        open_folder_btn.setToolTip("打开文件夹")  # 悬浮提示
        open_folder_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 16px;
            }
            QPushButton:hover {
                font-size: 18px;
            }
        """)
        open_folder_btn.clicked.connect(self.open_folder)
        buttons_layout.addWidget(open_folder_btn, 0, Qt.AlignCenter)
        
        # 删除文件按钮
        delete_file_btn = QPushButton("🗑️")
        delete_file_btn.setFixedSize(35, 35)
        delete_file_btn.setToolTip("删除文件")  # 悬浮提示
        delete_file_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 16px;
            }
            QPushButton:hover {
                font-size: 18px;
            }
        """)
        delete_file_btn.clicked.connect(self.delete_file)
        buttons_layout.addWidget(delete_file_btn, 0, Qt.AlignCenter)
        
        # 重新下载按钮
        redownload_btn = QPushButton("🔄")
        redownload_btn.setFixedSize(35, 35)
        redownload_btn.setToolTip("重新下载")  # 悬浮提示
        redownload_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 16px;
            }
            QPushButton:hover {
                font-size: 18px;
            }
        """)
        redownload_btn.clicked.connect(self.redownload)
        buttons_layout.addWidget(redownload_btn, 0, Qt.AlignCenter)
        
        # 删除记录按钮
        delete_record_btn = QPushButton("❌")
        delete_record_btn.setFixedSize(35, 35)
        delete_record_btn.setToolTip("删除记录")  # 悬浮提示
        delete_record_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 16px;
            }
            QPushButton:hover {
                font-size: 18px;
            }
        """)
        delete_record_btn.clicked.connect(self.delete_record)
        buttons_layout.addWidget(delete_record_btn, 0, Qt.AlignCenter)
        
        main_layout.addLayout(buttons_layout)
        
    def load_thumbnail(self):
        """加载缩略图 - 以容器高度为标准等比缩放"""
        thumbnail_path = self.record_data.get('thumbnail_path', '')
        status = self.record_data.get('status', 'success')
        
        if thumbnail_path and os.path.exists(thumbnail_path):
            pixmap = QPixmap(thumbnail_path)
            if not pixmap.isNull():
                # 获取缩略图标签的实际尺寸
                label_size = self.thumbnail_label.size()
                
                # 以高度为标准进行等比缩放，确保图片高度占满容器
                scaled_pixmap = pixmap.scaledToHeight(
                    label_size.height(),
                    Qt.SmoothTransformation
                )
                
                # 如果缩放后宽度超过容器宽度，则以宽度为标准缩放
                if scaled_pixmap.width() > label_size.width():
                    scaled_pixmap = pixmap.scaledToWidth(
                        label_size.width(),
                        Qt.SmoothTransformation
                    )
                
                # 如果文件已删除，应用灰度滤镜
                if status == 'file_deleted':
                    # 转换为灰度图像
                    gray_image = scaled_pixmap.toImage().convertToFormat(QImage.Format_Grayscale8)
                    gray_pixmap = QPixmap.fromImage(gray_image)
                    
                    # 创建半透明效果
                    painter = QPainter(gray_pixmap)
                    painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)
                    painter.fillRect(gray_pixmap.rect(), QColor(255, 255, 255, 100))
                    painter.end()
                    
                    self.thumbnail_label.setPixmap(gray_pixmap)
                else:
                    self.thumbnail_label.setPixmap(scaled_pixmap)
                return
        
        # 显示默认图标
        if status == 'file_deleted':
            self.thumbnail_label.setText("🎬")
            self.thumbnail_label.setStyleSheet("""
                QLabel {
                    border: 1px solid #868e96;
                    border-radius: 4px;
                    background-color: #ced4da;
                    font-size: 24px;
                    color: #868e96;
                }
            """)
        else:
            self.thumbnail_label.setText("🎬")
            self.thumbnail_label.setStyleSheet("""
                QLabel {
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                    background-color: #f8f9fa;
                    font-size: 24px;
                }
            """)
        
    def format_file_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
        
    def open_folder(self):
        """打开文件夹"""
        file_path = self.record_data.get('file_path', '')
        if file_path:
            self.open_folder_requested.emit(file_path)
        
    def delete_file(self):
        """删除文件"""
        record_id = self.record_data.get('id')
        file_path = self.record_data.get('file_path', '')
        if record_id and file_path:
            self.delete_file_requested.emit(record_id, file_path)
            
    def delete_record(self):
        """删除记录"""
        record_id = self.record_data.get('id')
        if record_id:
            self.delete_record_requested.emit(record_id)
            
    def redownload(self):
        """重新下载"""
        url = self.record_data.get('url', '')
        record_id = self.record_data.get('id')
        if url and record_id:
            self.redownload_requested.emit(url, record_id)
    
    def on_title_rename(self):
        """处理标题重命名"""
        record_id = self.record_data.get('id')
        if record_id:
            # 弹出重命名对话框
            current_file_path = self.record_data.get('file_path', '')
            if not current_file_path or not os.path.exists(current_file_path):
                QMessageBox.warning(self, "错误", "文件不存在，无法重命名")
                return
                
            # 获取当前文件名（不含扩展名）
            current_name = os.path.splitext(os.path.basename(current_file_path))[0]
            
            # 弹出输入对话框
            new_name, ok = QInputDialog.getText(
                self, "重命名文件", 
                "请输入新的文件名（不含扩展名）:", 
                QLineEdit.Normal, 
                current_name
            )
            
            if ok and new_name.strip():
                # 发出重命名信号，让父组件处理文件重命名逻辑
                print(f"[DEBUG] 发出重命名信号: record_id={record_id}, new_name={new_name.strip()}")
                self.rename_requested.emit(record_id, new_name.strip())
                print(f"[DEBUG] 重命名信号已发出")


class HistoryWidget(QWidget):
    """历史记录主界面组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history_manager = HistoryManager()
        self.current_page = 1
        self.page_size = 20
        self.current_records = []
        self.setup_ui()
        self.load_history()
        
    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 顶部控制区域
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)
        
        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索标题、URL或平台...")
        self.search_input.setFixedHeight(32)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #ced4da;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #007bff;
                outline: none;
            }
        """)
        self.search_input.textChanged.connect(self.on_search_changed)
        control_layout.addWidget(QLabel("搜索:"))
        control_layout.addWidget(self.search_input, 1)
        
        # 排序选择
        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            "按时间降序", "按时间升序", 
            "按大小降序", "按大小升序",
            "按标题A-Z", "按标题Z-A",
            "按平台分组"
        ])
        self.sort_combo.setFixedHeight(32)
        self.sort_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #ced4da;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                background-color: white;
            }
            QComboBox:focus {
                border-color: #007bff;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
            }
        """)
        self.sort_combo.currentTextChanged.connect(self.on_sort_changed)
        control_layout.addWidget(QLabel("排序:"))
        control_layout.addWidget(self.sort_combo)
        
        # 平台筛选
        self.platform_combo = QComboBox()
        self.platform_combo.addItem("所有平台")
        self.platform_combo.setFixedHeight(32)
        self.platform_combo.setStyleSheet(self.sort_combo.styleSheet())
        self.platform_combo.currentTextChanged.connect(self.on_platform_changed)
        control_layout.addWidget(QLabel("平台:"))
        control_layout.addWidget(self.platform_combo)
        
        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setFixedSize(80, 32)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_history)
        control_layout.addWidget(refresh_btn)
        
        # 清空记录按钮
        clear_btn = QPushButton("🗑️ 清空")
        clear_btn.setFixedSize(80, 32)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:pressed {
                background-color: #a71e2a;
            }
        """)
        clear_btn.clicked.connect(self.clear_all_history)
        control_layout.addWidget(clear_btn)
        
        layout.addLayout(control_layout)
        
        # 统计信息
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-size: 11px;
                padding: 4px 0px;
            }
        """)
        layout.addWidget(self.stats_label)
        
        # 历史记录列表区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                background-color: white;
            }
        """)
        
        # 列表容器
        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(5, 5, 5, 5)
        self.list_layout.setSpacing(5)
        self.list_layout.setAlignment(Qt.AlignTop)  # 设置顶部对齐
        
        self.scroll_area.setWidget(self.list_widget)
        layout.addWidget(self.scroll_area, 1)
        
        # 加载更多按钮
        self.load_more_btn = QPushButton("加载更多")
        self.load_more_btn.setFixedHeight(36)
        self.load_more_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #545b62;
            }
            QPushButton:pressed {
                background-color: #3d4147;
            }
        """)
        self.load_more_btn.clicked.connect(self.load_more_history)
        layout.addWidget(self.load_more_btn)
        
        # 初始化平台列表
        self.update_platform_list()
        
    def update_platform_list(self):
        """更新平台筛选列表"""
        try:
            platforms = self.history_manager.get_platforms()
            current_text = self.platform_combo.currentText()
            
            self.platform_combo.clear()
            self.platform_combo.addItem("所有平台")
            
            for platform in platforms:
                if platform and platform.strip():
                    self.platform_combo.addItem(platform)
            
            # 恢复之前的选择
            index = self.platform_combo.findText(current_text)
            if index >= 0:
                self.platform_combo.setCurrentIndex(index)
                
        except Exception as e:
            print(f"更新平台列表失败: {e}")
            
    def load_history(self, reset_page=True):
        """加载历史记录"""
        if reset_page:
            self.current_page = 1
            self.clear_list()
            
        try:
            # 获取搜索和筛选条件
            keyword = self.search_input.text().strip()
            platform = self.platform_combo.currentText()
            if platform == "所有平台":
                platform = None
                
            # 获取排序条件
            sort_text = self.sort_combo.currentText()
            sort_by, sort_order = self.parse_sort_option(sort_text)
            
            # 查询历史记录
            offset = (self.current_page - 1) * self.page_size
            records = self.history_manager.get_records(
                limit=self.page_size,
                offset=offset,
                search_keyword=keyword if keyword else None,
                platform=platform,
                sort_by=sort_by,
                sort_order=sort_order
            )
            
            if reset_page:
                self.current_records = records
            else:
                self.current_records.extend(records)
                
            # 添加记录到界面并检查缩略图
            for record in records:
                # 检查并重新提取缺失的缩略图
                self.check_and_extract_thumbnail(record)
                self.add_history_item(record)
                
            # 更新统计信息
            self.update_stats()
            
            # 更新加载更多按钮状态
            self.load_more_btn.setVisible(len(records) == self.page_size)
            
        except Exception as e:
            print(f"加载历史记录失败: {e}")
            QMessageBox.warning(self, "错误", f"加载历史记录失败: {e}")
            
    def parse_sort_option(self, sort_text):
        """解析排序选项"""
        sort_map = {
            "按时间降序": ("download_time", "DESC"),
            "按时间升序": ("download_time", "ASC"),
            "按大小降序": ("file_size", "DESC"),
            "按大小升序": ("file_size", "ASC"),
            "按标题A-Z": ("title", "ASC"),
            "按标题Z-A": ("title", "DESC"),
            "按平台分组": ("platform", "ASC")
        }
        return sort_map.get(sort_text, ("download_time", "DESC"))
        
    def add_history_item(self, record):
        """添加历史记录项到界面"""
        item_widget = HistoryItemWidget(record)
        
        # 连接信号
        item_widget.open_folder_requested.connect(self.open_folder)
        item_widget.delete_file_requested.connect(self.delete_file)
        item_widget.delete_record_requested.connect(self.delete_record)
        item_widget.redownload_requested.connect(self.redownload)
        item_widget.rename_requested.connect(self.rename_file)  # 连接重命名信号
        
        # 直接添加到布局末尾
        self.list_layout.addWidget(item_widget)
        
    def clear_list(self):
        """清空列表"""
        while self.list_layout.count():
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
    def update_stats(self):
        """更新统计信息"""
        try:
            stats = self.history_manager.get_statistics()
            total_count = stats['total_count']
            success_count = stats['success_count']
            total_size = stats['total_size']
            
            size_str = self.format_file_size(total_size) if total_size > 0 else "0 B"
            
            stats_text = f"总计: {total_count} 条记录 | 成功: {success_count} 条 | 总大小: {size_str} | 当前显示: {len(self.current_records)} 条"
            self.stats_label.setText(stats_text)
            
        except Exception as e:
            print(f"更新统计信息失败: {e}")
            self.stats_label.setText("统计信息加载失败")
            
    def format_file_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
        
    def on_search_changed(self):
        """搜索内容变化"""
        # 使用定时器延迟搜索，避免频繁查询
        if hasattr(self, 'search_timer'):
            self.search_timer.stop()
        
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(lambda: self.load_history(True))
        self.search_timer.start(500)  # 500ms延迟
        
    def on_sort_changed(self):
        """排序方式变化"""
        self.load_history(True)
        
    def on_platform_changed(self):
        """平台筛选变化"""
        self.load_history(True)
        
    def load_more_history(self):
        """加载更多历史记录"""
        self.current_page += 1
        self.load_history(False)
        
    def refresh_history(self):
        """刷新历史记录"""
        self.update_platform_list()
        self.load_history(True)
        
    def clear_all_history(self):
        """清空所有历史记录"""
        # 询问用户是否要重置ID
        reply = QMessageBox.question(
            self, "确认清空", 
            "确定要清空所有历史记录吗？\n\n选择'Yes'将清空记录并重置ID计数器\n选择'No'取消操作\n\n此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # 使用新的清空并重置ID的方法
                deleted_count = self.history_manager.clear_all_records_and_reset_id()
                self.refresh_history()
                QMessageBox.information(self, "成功", f"已清空所有历史记录({deleted_count}条)并重置ID计数器")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"清空历史记录失败: {e}")
                
    def open_folder(self, file_path):
        """打开文件夹"""
        try:
            if os.path.exists(file_path):
                folder_path = os.path.dirname(file_path)
                if sys.platform == 'win32':
                    os.startfile(folder_path)
                elif sys.platform == 'darwin':
                    os.system(f'open "{folder_path}"')
                else:
                    os.system(f'xdg-open "{folder_path}"')
            else:
                QMessageBox.warning(self, "错误", "文件不存在")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"打开文件夹失败: {e}")
            
    def delete_file(self, record_id, file_path):
        """删除文件"""
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除文件吗？\n{os.path.basename(file_path)}\n\n此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
                # 更新数据库记录状态
                self.history_manager.update_record(record_id, status='file_deleted')
                
                # 刷新界面
                self.refresh_history()
                
                QMessageBox.information(self, "成功", "文件已删除")
                
            except Exception as e:
                QMessageBox.warning(self, "错误", f"删除文件失败: {e}")
                
    def delete_record(self, record_id):
        """删除记录"""
        reply = QMessageBox.question(
            self, "确认删除", 
            "确定要删除此记录吗？\n此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # 删除数据库记录
                self.history_manager.delete_record(record_id)
                
                # 立即刷新界面
                self.refresh_history()
                
                # 强制处理所有待处理的事件，确保界面立即更新
                QApplication.processEvents()
                
                # 使用QTimer延迟显示成功消息，避免阻塞界面刷新
                QTimer.singleShot(100, lambda: QMessageBox.information(self, "成功", "记录已删除"))
                
            except Exception as e:
                QMessageBox.warning(self, "错误", f"删除记录失败: {e}")
                
    def check_and_extract_thumbnail(self, record):
        """检查并重新提取缺失的缩略图"""
        try:
            from thumbnail_extractor import ThumbnailExtractor
            import os
            
            file_path = record.get('file_path', '')
            thumbnail_path = record.get('thumbnail_path', '')
            
            # 检查是否为视频文件
            if not file_path or not os.path.exists(file_path):
                return
                
            video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v']
            if not any(file_path.lower().endswith(ext) for ext in video_extensions):
                return
                
            # 检查缩略图是否存在且有效
            need_extract = False
            if not thumbnail_path or not os.path.exists(thumbnail_path):
                need_extract = True
            else:
                # 检查缩略图文件是否损坏（文件大小为0或无法读取）
                try:
                    if os.path.getsize(thumbnail_path) == 0:
                        need_extract = True
                    else:
                        # 尝试加载图片验证是否有效
                        from PyQt5.QtGui import QPixmap
                        pixmap = QPixmap(thumbnail_path)
                        if pixmap.isNull():
                            need_extract = True
                except Exception:
                    need_extract = True
                    
            # 如果需要重新提取缩略图
            if need_extract:
                print(f"正在重新提取缩略图: {os.path.basename(file_path)}")
                extractor = ThumbnailExtractor()
                new_thumbnail_path = extractor.extract_thumbnail(file_path)
                
                if new_thumbnail_path and os.path.exists(new_thumbnail_path):
                    # 更新数据库中的缩略图路径
                    record_id = record.get('id')
                    if record_id:
                        self.history_manager.update_record(record_id, thumbnail_path=new_thumbnail_path)
                        record['thumbnail_path'] = new_thumbnail_path  # 更新内存中的记录
                        print(f"缩略图重新提取成功: {new_thumbnail_path}")
                else:
                    print(f"缩略图提取失败: {file_path}")
                    
        except Exception as e:
            print(f"检查缩略图时出错: {e}")
    
    def redownload(self, url, record_id):
        """重新下载"""
        try:
            print(f"[DEBUG] 重新下载被调用: URL={url}, Record ID={record_id}")
            
            # 获取主窗口的下载功能
            main_window = self.parent()
            search_count = 0
            while main_window and not hasattr(main_window, 'add_redownload_task') and search_count < 10:
                print(f"[DEBUG] 搜索主窗口，当前组件: {type(main_window).__name__}")
                main_window = main_window.parent()
                search_count += 1
            
            if main_window and hasattr(main_window, 'add_redownload_task'):
                print(f"[DEBUG] 找到主窗口: {type(main_window).__name__}")
                
                # 切换到下载页面
                if hasattr(main_window, 'tab_widget'):
                    print(f"[DEBUG] 切换到下载页面")
                    main_window.tab_widget.setCurrentIndex(0)  # 假设下载页面是第一个标签页
                
                # 添加重新下载任务
                print(f"[DEBUG] 调用 add_redownload_task")
                main_window.add_redownload_task(url, record_id)
                print(f"[DEBUG] 重新下载任务添加成功")
                QMessageBox.information(self, "成功", "已添加到下载队列")
            else:
                print(f"[DEBUG] 无法找到主窗口或add_redownload_task方法")
                QMessageBox.warning(self, "错误", "无法找到下载功能")
                
        except Exception as e:
            print(f"重新下载时出错: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"重新下载失败: {str(e)}")
    
    def rename_file(self, record_id, new_name):
        """重命名文件"""
        print(f"[DEBUG] rename_file被调用: record_id={record_id}, new_name={new_name}")
        try:
            # 从数据库获取记录信息
            target_record = self.history_manager.get_record_by_id(record_id)
            print(f"[DEBUG] 获取到的记录: {target_record}")
            
            if not target_record:
                QMessageBox.warning(self, "错误", "找不到对应的记录")
                return
                
            old_file_path = target_record.get('file_path', '')
            if not old_file_path or not os.path.exists(old_file_path):
                QMessageBox.warning(self, "错误", "原文件不存在")
                return
            
            # 构建新的文件路径
            file_dir = os.path.dirname(old_file_path)
            file_ext = os.path.splitext(old_file_path)[1]  # 保持原扩展名
            new_file_path = os.path.join(file_dir, new_name + file_ext)
            
            # 检查新文件名是否已存在
            if os.path.exists(new_file_path):
                reply = QMessageBox.question(
                    self, "文件已存在", 
                    f"文件 '{new_name + file_ext}' 已存在，是否覆盖？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return
            
            # 重命名文件
            os.rename(old_file_path, new_file_path)
            
            # 更新数据库中的文件路径
            self.history_manager.update_record(record_id, file_path=new_file_path)
            
            # 刷新界面
            self.refresh_history()
            
            QMessageBox.information(self, "成功", f"文件已重命名为: {new_name + file_ext}")
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"重命名文件失败: {e}")
            print(f"重命名文件时出错: {e}")