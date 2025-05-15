"""
Main window for the Quake Query tool.
"""
import os
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                           QLabel, QLineEdit, QPushButton, QTextEdit,
                           QComboBox, QSpinBox, QMessageBox, QFileDialog,
                           QTabWidget, QTableWidget, QTableWidgetItem,
                           QCheckBox, QProgressDialog, QFrame, QMenu,
                           QInputDialog, QDialog, QListWidget, QListWidgetItem,
                           QSizePolicy, QProgressBar, QGridLayout, QApplication)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QFont, QAction
from typing import Dict, Any, Optional, List, Tuple
import re
import json
import concurrent.futures
import threading
from functools import lru_cache

# 屏蔽libpng警告
os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.qpa.*=false'

from ..core.query_manager import QueryManager
from ..core.export_manager import ExportManager
from ..config.settings import settings
from ..utils.logger import logger

class StyledWidget(QFrame):
    """Base styled widget with modern look"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            StyledWidget {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                margin: 3px;
            }
        """)

class CookieManageDialog(QDialog):
    """Cookie管理对话框"""
    def __init__(self, parent=None, cookies: List[Dict] = None):
        super().__init__(parent)
        self.setWindowTitle("Cookie管理")
        self.setMinimumSize(600, 400)
        self.cookies = cookies or []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Cookie列表
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #dcdcdc;
                border-radius: 4px;
                background: white;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #E8F5E9;
                color: #00C250;
            }
        """)
        
        # 添加Cookie到列表
        for cookie in self.cookies:
            item = QListWidgetItem(cookie.get('name', 'Unnamed Cookie'))
            item.setData(Qt.UserRole, cookie)
            self.list_widget.addItem(item)
        
        layout.addWidget(self.list_widget)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        # 添加按钮
        add_button = QPushButton("添加")
        add_button.setStyleSheet("""
            QPushButton {
                background-color: #00C250;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #00A040;
            }
        """)
        add_button.clicked.connect(self.add_cookie)
        
        # 编辑按钮
        edit_button = QPushButton("编辑")
        edit_button.setStyleSheet(add_button.styleSheet())
        edit_button.clicked.connect(self.edit_cookie)
        
        # 删除按钮
        delete_button = QPushButton("删除")
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        delete_button.clicked.connect(self.delete_cookie)
        
        button_layout.addWidget(add_button)
        button_layout.addWidget(edit_button)
        button_layout.addWidget(delete_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)

    def add_cookie(self):
        name, ok = QInputDialog.getText(self, "添加Cookie", "Cookie名称:")
        if ok and name:
            value, ok = QInputDialog.getMultiLineText(self, "添加Cookie", "Cookie值:")
            if ok and value:
                cookie = {'name': name, 'value': value}
                item = QListWidgetItem(name)
                item.setData(Qt.UserRole, cookie)
                self.list_widget.addItem(item)
                self.cookies.append(cookie)

    def edit_cookie(self):
        current_item = self.list_widget.currentItem()
        if current_item:
            cookie = current_item.data(Qt.UserRole)
            name, ok = QInputDialog.getText(self, "编辑Cookie", "Cookie名称:", text=cookie['name'])
            if ok and name:
                value, ok = QInputDialog.getMultiLineText(self, "编辑Cookie", "Cookie值:", text=cookie['value'])
                if ok and value:
                    cookie['name'] = name
                    cookie['value'] = value
                    current_item.setText(name)
                    current_item.setData(Qt.UserRole, cookie)
                    self.cookies[self.list_widget.row(current_item)] = cookie

    def delete_cookie(self):
        current_item = self.list_widget.currentItem()
        if current_item:
            row = self.list_widget.row(current_item)
            self.list_widget.takeItem(row)
            self.cookies.pop(row)

    def get_cookies(self) -> List[Dict]:
        return self.cookies

class QueryWorker(QThread):
    """Worker thread for executing queries"""
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int, int, str)
    status = Signal(str)

    def __init__(self, query_manager, query: str, size: int, max_workers: int = 5):
        super().__init__()
        self.query_manager = query_manager
        self.query = query
        self.size = size
        self.total_pages = (size + 99) // 100
        self.current_results = []
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self._cache = {}

    def _fetch_page(self, page: int) -> Dict:
        """获取单个页面的数据"""
        try:
            start = (page - 1) * 100
            size = min(100, self.size - start)
            data = self.query_manager.build_query_data(self.query, size, start)
            
            # 设置进度回调
            def progress_callback(current, total):
                return not self.isInterruptionRequested()
            
            self.query_manager.progress_callback = progress_callback
            
            # 执行查询
            return self.query_manager.execute_query(self.query, size=size)
            
        except Exception as e:
            logger.error(f"Failed to fetch page {page}: {str(e)}")
            return {}

    def run(self):
        try:
            self.status.emit("正在初始化查询...")
            all_results = {'data': [], 'meta': {}}
            
            # 计算实际需要的页数
            pages_needed = min(self.total_pages, (self.size + 99) // 100)
            
            # 使用线程池进行并发查询
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有页面的查询任务
                future_to_page = {
                    executor.submit(self._fetch_page, page): page 
                    for page in range(1, pages_needed + 1)
                }

                # 收集结果
                for future in concurrent.futures.as_completed(future_to_page):
                    if self.isInterruptionRequested():
                        executor.shutdown(wait=False)
                        return

                    page = future_to_page[future]
                    try:
                        page_result = future.result()
                        if page_result and 'data' in page_result:
                            with self._lock:
                                self.current_results.extend(page_result['data'])
                                current_count = len(self.current_results)
                                self.progress.emit(page, pages_needed, f"已获取 {current_count} 条结果")
                                
                            all_results['data'].extend(page_result['data'])
                            # 更新元数据
                            if 'meta' in page_result:
                                all_results['meta'].update(page_result['meta'])

                    except Exception as e:
                        logger.error(f"Error processing page {page}: {str(e)}")
                        continue

            # 确保结果数量不超过请求的大小
            if len(all_results['data']) > self.size:
                all_results['data'] = all_results['data'][:self.size]

            if not self.isInterruptionRequested():
                self.finished.emit(all_results)

        except Exception as e:
            if not self.isInterruptionRequested():
                self.error.emit(str(e))

class CustomProgressDialog(QProgressDialog):
    """自定义进度对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("查询进度")
        self.setMinimumWidth(400)
        self.setAutoClose(False)
        self.setAutoReset(False)
        
        # 添加状态标签
        self.status_label = QLabel()
        self.status_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 12px;
                margin-top: 5px;
            }
        """)
        
        # 获取进度条布局并添加状态标签
        layout = self.layout()
        if layout:
            layout.addWidget(self.status_label)
    
    def set_status(self, status: str):
        """更新状态信息"""
        self.status_label.setText(status)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.query_manager = None
        self.export_manager = ExportManager()
        self.results = None
        self.query_worker = None
        self.progress_dialog = None
        self.setup_ui()
        self.load_auth_settings()
        self.setup_table_styles()

    def _setup_auth_section(self, layout: QVBoxLayout):
        """Setup authentication section"""
        auth_group = StyledWidget()
        auth_layout = QVBoxLayout(auth_group)
        auth_layout.setSpacing(8)
        auth_layout.setContentsMargins(12, 12, 12, 12)

        # 标题
        title = QLabel("认证设置")
        title.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 8px;
            color: #2e7d32;
        """)
        auth_layout.addWidget(title)

        # Cookie输入区域
        cookie_widget = QWidget()
        cookie_layout = QVBoxLayout(cookie_widget)
        cookie_layout.setContentsMargins(0, 0, 0, 0)
        cookie_layout.setSpacing(6)
        
        cookie_label = QLabel("Cookie:")
        cookie_label.setStyleSheet("font-weight: 500; color: #2e7d32;")
        self.cookie_input = QLineEdit()
        self.cookie_input.setPlaceholderText("输入Cookie")
        self.cookie_input.setMinimumHeight(32)
        
        cookie_layout.addWidget(cookie_label)
        cookie_layout.addWidget(self.cookie_input)
        
        auth_layout.addWidget(cookie_widget)

        # 记住认证信息选项
        remember_widget = QWidget()
        remember_layout = QHBoxLayout(remember_widget)
        remember_layout.setContentsMargins(0, 0, 0, 0)
        
        self.remember_auth = QCheckBox("记住Cookie")
        self.remember_auth.setStyleSheet("color: #2e7d32;")
        remember_layout.addWidget(self.remember_auth)
        remember_layout.addStretch()
        
        auth_layout.addWidget(remember_widget)

        # 保存按钮
        save_widget = QWidget()
        save_layout = QHBoxLayout(save_widget)
        save_layout.setContentsMargins(0, 0, 0, 0)
        
        self.save_auth_button = QPushButton("保存Cookie")
        self.save_auth_button.setMinimumHeight(32)
        self.save_auth_button.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #60ad5e;
            }
        """)
        self.save_auth_button.clicked.connect(self.save_auth_settings)
        save_layout.addWidget(self.save_auth_button)
        save_layout.addStretch()
        
        auth_layout.addWidget(save_widget)
        layout.addWidget(auth_group)

    def load_auth_settings(self):
        """Load authentication settings from config"""
        cookie = settings.get('auth.cookie', '')
        remember = settings.get('auth.remember_auth', False)

        if remember and cookie:
            self.cookie_input.setText(cookie)
            self.remember_auth.setChecked(True)

    def save_auth_settings(self):
        """Save authentication settings to config"""
        try:
            if self.remember_auth.isChecked():
                settings.set('auth.cookie', self.cookie_input.text())
            else:
                settings.set('auth.cookie', '')
            settings.set('auth.remember_auth', self.remember_auth.isChecked())
            
            QMessageBox.information(self, "成功", "Cookie已保存")
            logger.info("Cookie saved successfully")
        except Exception as e:
            logger.error(f"Failed to save cookie: {str(e)}")
            QMessageBox.critical(self, "错误", f"保存Cookie失败: {str(e)}")

    def perform_query(self):
        """Execute the query"""
        try:
            # 验证输入
            if not self.cookie_input.text():
                raise ValueError("请输入Cookie")

            if not self.query_input.text():
                raise ValueError("请输入查询语句")

            # 重置进度显示
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("准备查询...")
            self.status_label.setText("")

            # 禁用查询按钮
            self.query_button.setEnabled(False)
            self.query_button.setText("查询中...")

            # 格式化查询字符串
            query = self._format_query(self.query_input.text().strip())
            logger.debug(f"Formatted query: {query}")

            # 解析Cookie并创建查询管理器
            cookies = self._parse_cookies(self.cookie_input.text())
            self.query_manager = QueryManager(cookies=cookies)

            # 设置进度条范围
            size = self.size_input.value()
            total_pages = (size + 99) // 100
            self.progress_bar.setRange(0, total_pages)

            # 创建并启动查询线程，设置并发数
            max_workers = min(10, total_pages)  # 最大10个并发
            self.query_worker = QueryWorker(self.query_manager, query, size, max_workers)
            self.query_worker.finished.connect(self.handle_query_results)
            self.query_worker.error.connect(self.handle_query_error)
            self.query_worker.progress.connect(self.update_progress)
            self.query_worker.status.connect(self.update_status)
            self.query_worker.start()

        except Exception as e:
            logger.error(f"Query setup failed: {str(e)}")
            QMessageBox.critical(self, "错误", str(e))
            self.reset_query_button()

    def update_progress(self, current: int, total: int, status_msg: str):
        """Update progress display"""
        # 更新进度条
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"正在查询第 {current}/{total} 页")
        
        # 更新状态标签
        self.status_label.setText(status_msg)
        
        # 如果有进度对话框，也更新它
        if self.progress_dialog:
            self.progress_dialog.setValue(current)
            self.progress_dialog.setLabelText(f"正在查询第 {current}/{total} 页")
            self.progress_dialog.set_status(status_msg)

    def update_status(self, status: str):
        """Update status message"""
        self.status_label.setText(status)
        if self.progress_dialog:
            self.progress_dialog.set_status(status)

    def reset_query_button(self):
        """Reset query button state"""
        self.query_button.setEnabled(True)
        self.query_button.setText("执行查询")
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("准备就绪")
        self.status_label.setText("")

    def handle_query_results(self, results):
        """Handle query results"""
        self.results = results
        if self.results:
            # 更新进度显示
            total = len(self.results.get('data', []))
            self.status_label.setText(f"查询完成，共找到 {total} 条结果")
            self.progress_bar.setFormat("查询完成")
            self.progress_bar.setValue(self.progress_bar.maximum())
            
            # 更新视图
            self._update_views()
            
            # 显示结果统计
            QMessageBox.information(self, "查询完成", f"共找到 {total} 条结果")
        else:
            self.status_label.setText("未找到任何结果")
            QMessageBox.warning(self, "提示", "未找到任何结果")

        self.reset_query_button()
        if self.progress_dialog:
            self.progress_dialog.close()

    def handle_query_error(self, error_msg: str):
        """Handle query error"""
        self.status_label.setText(f"错误: {error_msg}")
        QMessageBox.critical(self, "错误", error_msg)
        self.reset_query_button()
        if self.progress_dialog:
            self.progress_dialog.close()

    def closeEvent(self, event):
        """Handle window close event"""
        # 取消正在进行的查询
        self.cancel_query()
        super().closeEvent(event)

    def setup_table_styles(self):
        """Setup table styles and dimensions"""
        # 设置表格的默认行高和列宽
        self.table.verticalHeader().setDefaultSectionSize(40)  # 增加行高
        self.table.horizontalHeader().setDefaultSectionSize(200)  # 设置默认列宽
        
        # 设置特定列的宽度
        self.table.horizontalHeader().setMinimumSectionSize(100)
        column_widths = {
            'domain': 300,
            'ip': 150,
            'port': 100,
            'service.name': 150,
            'location.country_cn': 100,
            'location.province_cn': 100,
            'location.city_cn': 100
        }
        
        # 应用宽设置
        for col, field in enumerate(settings.get('export.fields')):
            if field in column_widths:
                self.table.setColumnWidth(col, column_widths[field])

        # 设置表格的选择行为
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        
        # 设置表格的滚动行为
        self.table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("360 Quake 查询工具")
        self.setMinimumSize(1100, 750)
        
        # 设置全局字体
        font = QFont("Microsoft YaHei", 9)
        self.setFont(font)
        
        # 创建主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # 创建左侧容器（认证和查询设置）
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setSpacing(8)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 添加认证和查询部分到左侧容器
        self._setup_auth_section(left_layout)
        self._setup_query_section(left_layout)
        left_layout.addStretch()

        # 创建右侧容器（结果显示）
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setSpacing(8)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self._setup_results_section(right_layout)

        # 创建水平布局来放置左右容器
        content_container = QWidget()
        content_layout = QHBoxLayout(content_container)
        content_layout.setSpacing(10)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # 设置左右容器的大小策略和比例
        left_container.setFixedWidth(380)  # 减小左侧宽度
        right_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # 添加左右容器到水平布局
        content_layout.addWidget(left_container)
        content_layout.addWidget(right_container)

        # 创建底部容器（导出部分）
        bottom_container = QWidget()
        bottom_layout = QHBoxLayout(bottom_container)
        bottom_layout.setSpacing(10)
        bottom_layout.setContentsMargins(10, 0, 10, 10)
        self._setup_export_section(bottom_layout)

        # 添加主要内容和底部容器到主布局
        layout.addWidget(content_container)
        layout.addWidget(bottom_container)
        
        # 添加取消查询方法
        self.cancel_query = self._cancel_query
        
    def _cancel_query(self):
        """取消正在进行的查询"""
        if self.query_worker and self.query_worker.isRunning():
            self.query_worker.requestInterruption()
            self.status_label.setText("查询已取消")
        
    def _setup_query_section(self, layout: QVBoxLayout):
        """Setup query section"""
        query_group = StyledWidget()
        query_layout = QVBoxLayout(query_group)
        query_layout.setSpacing(8)
        query_layout.setContentsMargins(12, 12, 12, 12)

        # 标题
        title = QLabel("查询设置")
        title.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 8px;
            color: #2e7d32;
        """)
        query_layout.addWidget(title)

        # 查询输入区域
        query_input_group = QWidget()
        query_input_layout = QVBoxLayout(query_input_group)
        query_input_layout.setContentsMargins(0, 0, 0, 0)
        query_input_layout.setSpacing(6)
        
        query_label = QLabel("查询语句:")
        query_label.setStyleSheet("font-weight: 500; color: #2e7d32;")
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("输入域名或查询语句")
        self.query_input.setMinimumHeight(32)
        
        query_input_layout.addWidget(query_label)
        query_input_layout.addWidget(self.query_input)
        
        query_layout.addWidget(query_input_group)

        # 查询选项区域
        query_options_group = QWidget()
        query_options_layout = QGridLayout(query_options_group)
        query_options_layout.setContentsMargins(0, 0, 0, 0)
        query_options_layout.setSpacing(8)

        # 结果数量选择
        size_label = QLabel("结果数量:")
        size_label.setStyleSheet("font-weight: 500; color: #2e7d32;")
        self.size_input = QSpinBox()
        self.size_input.setRange(1, 100000)
        self.size_input.setValue(settings.get('query.default_size'))
        self.size_input.setMinimumHeight(32)
        
        # 输出格式选择
        format_label = QLabel("输出格式:")
        format_label.setStyleSheet("font-weight: 500; color: #2e7d32;")
        self.format_combo = QComboBox()
        self.format_combo.addItems(["JSON", "CSV", "URL格式"])
        self.format_combo.setMinimumHeight(32)

        # 添加到网格布局
        query_options_layout.addWidget(size_label, 0, 0)
        query_options_layout.addWidget(self.size_input, 0, 1)
        query_options_layout.addWidget(format_label, 1, 0)
        query_options_layout.addWidget(self.format_combo, 1, 1)

        query_layout.addWidget(query_options_group)

        # 添加进度显示区域
        progress_group = QWidget()
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(6)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("准备就绪")
        self.progress_bar.setMinimumHeight(22)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                background-color: #f5f5f5;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #2e7d32;
                border-radius: 2px;
            }
        """)
        
        # 状态标签
        self.status_label = QLabel()
        self.status_label.setStyleSheet("margin-top: 3px; color: #607d8b; font-size: 12px;")
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)
        
        query_layout.addWidget(progress_group)

        # 查询按钮
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        self.query_button = QPushButton("执行查询")
        self.query_button.setMinimumHeight(32)
        self.query_button.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #60ad5e;
            }
        """)
        self.query_button.clicked.connect(self.perform_query)
        button_layout.addWidget(self.query_button)
        button_layout.addStretch()
        
        query_layout.addWidget(button_widget)
        layout.addWidget(query_group)
        
    def _setup_results_section(self, layout: QVBoxLayout):
        """Setup results section"""
        results_group = StyledWidget()
        results_layout = QVBoxLayout(results_group)
        results_layout.setSpacing(8)
        results_layout.setContentsMargins(12, 12, 12, 12)

        # 标题
        title = QLabel("查询结果")
        title.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 8px;
            color: #2e7d32;
        """)
        results_layout.addWidget(title)

        # 创建选项卡
        self.tab_widget = QTabWidget()
        self.tab_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #d0d0d0;
                border-radius: 3px;
            }
            QTabBar::tab {
                background-color: #f5f5f5;
                border: 1px solid #d0d0d0;
                border-bottom: none;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
                padding: 5px 10px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 1px solid white;
                color: #2e7d32;
                font-weight: bold;
            }
        """)
        
        # 表格视图
        self.table = QTableWidget()
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setColumnCount(len(settings.get('export.fields')))
        self.table.setHorizontalHeaderLabels(settings.get('export.fields'))
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #e0e0e0;
                border: none;
            }
            QHeaderView::section {
                background-color: #f0f7f0;
                color: #2e7d32;
                font-weight: bold;
                border: none;
                border-right: 1px solid #d0d0d0;
                border-bottom: 1px solid #d0d0d0;
                padding: 6px;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 5px;
                border-bottom: 1px solid #f0f0f0;
            }
            QTableWidget::item:selected {
                background-color: #e8f5e9;
                color: #2e7d32;
            }
            QTableWidget::item:alternate {
                background-color: #fafafa;
            }
        """)
        
        # 设置表格属性
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)  # 不显示网格线，使用自定义边框
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)  # 隐藏行号
        self.table.verticalHeader().setDefaultSectionSize(36)  # 设置行高
        
        # 设置表头属性
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionsClickable(True)
        header.setSectionsMovable(True)
        header.setHighlightSections(True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        # 连接双击事件
        self.table.cellDoubleClicked.connect(self._show_item_detail)
        
        # 启用右键菜单
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        
        # JSON视图
        self.json_view = QTextEdit()
        self.json_view.setReadOnly(True)
        self.json_view.setStyleSheet("""
            QTextEdit {
                font-family: Consolas, 'Courier New', monospace;
                font-size: 12px;
                line-height: 1.3;
                padding: 8px;
                background-color: #fafafa;
                border: none;
            }
        """)
        
        # 添加到选项卡
        self.tab_widget.addTab(self.table, "表格视图")
        self.tab_widget.addTab(self.json_view, "JSON视图")

        results_layout.addWidget(self.tab_widget)
        layout.addWidget(results_group)
        
    def _show_item_detail(self, row, col):
        """显示数据项详情"""
        if not self.results or 'data' not in self.results or row >= len(self.results['data']):
            return
        
        # 获取选中行的完整数据
        item_data = self.results['data'][row]
        
        # 创建详情对话框
        detail_dialog = QDialog(self)
        detail_dialog.setWindowTitle("数据详情")
        detail_dialog.setMinimumSize(600, 400)
        
        dialog_layout = QVBoxLayout(detail_dialog)
        
        # 创建文本编辑器显示格式化的JSON
        detail_text = QTextEdit()
        detail_text.setReadOnly(True)
        detail_text.setStyleSheet("""
            QTextEdit {
                font-family: 'Courier New', monospace;
                font-size: 12px;
                line-height: 1.3;
                padding: 8px;
                background-color: #fafafa;
                border: none;
            }
        """)
        
        # 格式化JSON
        json_str = json.dumps(item_data, ensure_ascii=False, indent=2)
        detail_text.setText(json_str)
        
        dialog_layout.addWidget(detail_text)
        
        # 添加关闭按钮
        button_layout = QHBoxLayout()
        close_button = QPushButton("关闭")
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #60ad5e;
            }
        """)
        close_button.clicked.connect(detail_dialog.close)
        
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        dialog_layout.addLayout(button_layout)
        
        # 显示对话框
        detail_dialog.exec()
        
    def _show_table_context_menu(self, position):
        """显示表格右键菜单"""
        if not self.results or not self.table.rowCount():
            return
            
        # 获取当前选中行
        selected_indexes = self.table.selectedIndexes()
        if not selected_indexes:
            return
            
        row = selected_indexes[0].row()
        
        # 创建右键菜单
        context_menu = QMenu(self)
        view_action = QAction("查看详情", self)
        copy_action = QAction("复制行数据", self)
        copy_cell_action = QAction("复制单元格", self)
        
        # 连接动作信号
        view_action.triggered.connect(lambda: self._show_item_detail(row, 0))
        copy_action.triggered.connect(lambda: self._copy_row_data(row))
        copy_cell_action.triggered.connect(lambda: self._copy_cell_data(selected_indexes[0].row(), selected_indexes[0].column()))
        
        # 添加动作到菜单
        context_menu.addAction(view_action)
        context_menu.addAction(copy_action)
        context_menu.addAction(copy_cell_action)
        
        # 显示菜单
        context_menu.exec(self.table.mapToGlobal(position))
        
    def _copy_row_data(self, row):
        """复制行数据到剪贴板"""
        if not self.results or 'data' not in self.results or row >= len(self.results['data']):
            return
            
        # 获取行数据
        row_data = self.results['data'][row]
        
        # 将数据转换为文本
        text = json.dumps(row_data, ensure_ascii=False, indent=2)
        
        # 复制到剪贴板
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        
        # 显示提示
        self.status_label.setText("行数据已复制到剪贴板")
        
    def _copy_cell_data(self, row, col):
        """复制单元格数据到剪贴板"""
        item = self.table.item(row, col)
        if item:
            # 获取单元格文本
            text = item.text()
            
            # 复制到剪贴板
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            
            # 显示提示
            self.status_label.setText("单元格数据已复制到剪贴板")

    def _setup_export_section(self, layout: QHBoxLayout):
        """Setup export section"""
        self.export_button = QPushButton("导出结果")
        self.export_button.setMinimumWidth(100)
        self.export_button.setMinimumHeight(32)
        self.export_button.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #60ad5e;
            }
        """)
        self.export_button.clicked.connect(self.export_results)
        layout.addWidget(self.export_button)
        layout.addStretch()

    def _parse_cookies(self, cookie_str: str) -> Optional[Dict[str, str]]:
        """Parse cookie string into dictionary"""
        try:
            if not cookie_str:
                return None
                
            # 清理 Cookie 字符串
            cookie_str = cookie_str.strip()  # 移除首尾空白字符
            cookie_str = cookie_str.replace('\n', '')  # 移除换行符
            cookie_str = cookie_str.replace('\r', '')  # 移除回车符
            
            # 分割并解析 Cookie
            cookies = {}
            for item in cookie_str.split(';'):
                item = item.strip()
                if '=' in item:
                    key, value = item.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    if key and value:  # 只添加非空的键值对
                        cookies[key] = value
            
            if not cookies:
                raise ValueError("无法解析Cookie")
                
            return cookies
            
        except Exception as e:
            logger.error(f"Cookie parsing failed: {str(e)}")
            raise ValueError(f"Cookie格式错误: {str(e)}")

    def _format_query(self, query: str) -> str:
        """Format query string to match Quake's syntax"""
        # 如果询中没有指定字段，默认添加domain字段
        if ':' not in query:
            query = f'domain: "{query}"'
        
        # 确保域名使用双引号
        def replace_domain(match):
            value = match.group(2)
            # 移除有的引号
            value = value.strip('"\'')
            return f'domain: "{value}"'
        
        query = re.sub(r'(domain\s*:\s*)([^,\s]+)', replace_domain, query)
        
        return query

    def _update_views(self):
        """Update all views with query results"""
        if not self.results:
            return

        # 更新表格视图
        data = self.results.get('data', [])
        self.table.setRowCount(len(data))
        
        for row, item in enumerate(data):
            for col, field in enumerate(settings.get('export.fields')):
                if '.' in field:
                    parts = field.split('.')
                    value = item
                    for part in parts:
                        value = value.get(part, '') if isinstance(value, dict) else ''
                else:
                    value = item.get(field, '')
                
                # 确保值是字符串并正确处理编码
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                elif not isinstance(value, str):
                    value = str(value)
                
                # 创建表格项并设置对齐方式和样式
                table_item = QTableWidgetItem(value)
                table_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                
                # 根据列类型设置不同的样式
                if field == 'ip' or field == 'port':
                    table_item.setForeground(Qt.GlobalColor.darkBlue)
                elif field == 'domain':
                    table_item.setForeground(Qt.GlobalColor.darkGreen)
                    # 设置字体为粗体
                    font = table_item.font()
                    font.setBold(True)
                    table_item.setFont(font)
                    
                self.table.setItem(row, col, table_item)

        # 调整所有列的宽度以适应内容
        self.table.resizeColumnsToContents()
        
        # 确保列宽不小于最小值
        for col in range(self.table.columnCount()):
            if self.table.columnWidth(col) < 100:
                self.table.setColumnWidth(col, 100)
            elif self.table.columnWidth(col) > 300:
                self.table.setColumnWidth(col, 300)  # 设置最大列宽

        # 更新JSON视图，确保使用UTF-8编码
        try:
            json_str = json.dumps(self.results, ensure_ascii=False, indent=2)
            # 直接设置文本内容，不使用高亮功能
            self.json_view.setText(json_str)
        except Exception as e:
            logger.error(f"Failed to format JSON view: {str(e)}")
            self.json_view.setText("Error: 无法显示JSON数据")

    def export_results(self):
        """Export the results"""
        try:
            if not self.results:
                raise ValueError("没有可导出的结果")

            format_type = self.format_combo.currentText()
            file_name = self.export_manager.generate_filename(format_type)

            if format_type == "JSON":
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "导出JSON", file_name, "JSON Files (*.json)")
                if file_path:
                    self.export_manager.export_json(self.results, file_path)
            elif format_type == "CSV":
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "导出CSV", file_name, "CSV Files (*.csv)")
                if file_path:
                    self.export_manager.export_csv(self.results, file_path)
            else:  # URL格式
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "导出URL", file_name, "Text Files (*.txt)")
                if file_path:
                    self._export_url_format(file_path)

            if file_path:
                QMessageBox.information(self, "成功", f"结果已导出到 {file_path}")

        except Exception as e:
            logger.error(f"Export failed: {str(e)}")
            QMessageBox.critical(self, "错误", str(e))

    def _export_url_format(self, file_path: str):
        """Export results in protocol+IP+port format"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                for item in self.results.get('data', []):
                    # 获取必要的字段
                    ip = item.get('ip', '')
                    port = item.get('port', '')
                    service = item.get('service', {})
                    protocol = service.get('name', 'http').lower()  # 默认使用http

                    # 处理协议
                    if protocol in ['http/ssl', 'https']:
                        protocol = 'https'
                    elif protocol == 'http':
                        protocol = 'http'
                    
                    # 生成URL格式
                    if ip and port:
                        url = f"{protocol}://{ip}:{port}"
                        f.write(url + '\n')

        except Exception as e:
            logger.error(f"URL format export failed: {str(e)}")
            raise ValueError(f"导出URL格式失败: {str(e)}") 