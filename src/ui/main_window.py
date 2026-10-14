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
                           QSizePolicy, QProgressBar, QGridLayout, QApplication,
                           QTreeWidget, QTreeWidgetItem, QHeaderView)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QFont, QAction, QColor, QBrush
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
from .theme import get_theme, build_qss, Theme

class StyledWidget(QFrame):
    """卡片式容器，样式由 theme.py 的全局 QSS 的 StyledWidget 选择器统一控制"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

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
        
        # Cookie列表（样式由全局 QSS 的 QListWidget 选择器统一控制）
        self.list_widget = QListWidget()

        # 添加Cookie到列表
        for cookie in self.cookies:
            item = QListWidgetItem(cookie.get('name', 'Unnamed Cookie'))
            item.setData(Qt.UserRole, cookie)
            self.list_widget.addItem(item)
        
        layout.addWidget(self.list_widget)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        # 添加按钮（主按钮样式）
        add_button = QPushButton("添加")
        add_button.setObjectName("primaryButton")
        add_button.setMinimumWidth(80)
        add_button.clicked.connect(self.add_cookie)

        # 编辑按钮（主按钮样式）
        edit_button = QPushButton("编辑")
        edit_button.setObjectName("primaryButton")
        edit_button.setMinimumWidth(80)
        edit_button.clicked.connect(self.edit_cookie)

        # 删除按钮（危险操作样式）
        delete_button = QPushButton("删除")
        delete_button.setObjectName("dangerButton")
        delete_button.setMinimumWidth(80)
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
        
        # 添加状态标签（次要文本样式）
        self.status_label = QLabel()
        self.status_label.setObjectName("statusLabel")
        
        # 获取进度条布局并添加状态标签
        layout = self.layout()
        if layout:
            layout.addWidget(self.status_label)
    
    def set_status(self, status: str):
        """更新状态信息"""
        self.status_label.setText(status)

class DataDetailDialog(QDialog):
    """数据详情对话框：结构化展示单条资产数据

    相比直接罗列原始 JSON 文本，本对话框提供：
    - 摘要区：置顶展示域名/IP/端口/服务等关键字段，便于快速浏览
    - 树形区：递归呈现完整嵌套结构（dict/list 可展开折叠），叶子值按数据类型着色
    - 搜索框：按关键字过滤字段名或字段值，父节点命中子节点时保留
    - 复制能力：支持复制单个字段值与完整 JSON
    """
    # 摘要区展示的关键字段：点分路径 -> 中文标签
    SUMMARY_FIELDS = [
        ('domain', '域名'),
        ('ip', 'IP'),
        ('port', '端口'),
        ('service.name', '服务'),
        ('service.http.title', '标题'),
        ('location.country_cn', '国家'),
        ('location.province_cn', '省份'),
        ('location.city_cn', '城市'),
    ]
    # 每行摘要展示的字段对数（过多则换行）
    SUMMARY_COLUMNS = 3

    def __init__(self, data: Dict[str, Any], theme: Theme, parent=None):
        super().__init__(parent)
        self.data = data
        self.theme = theme
        self.setWindowTitle("数据详情")
        self.setMinimumSize(760, 560)
        self._setup_ui()

    def _setup_ui(self):
        """构建对话框整体布局：搜索 -> 摘要 -> 树 -> 操作按钮"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 搜索框：输入关键字即时过滤树节点
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索字段名或字段值...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_tree)
        layout.addWidget(self.search_input)

        # 摘要区：快速浏览关键信息
        layout.addWidget(self._build_summary())

        # 树形数据区：完整嵌套结构
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["字段", "值"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self._populate(self.tree.invisibleRootItem(), self.data)
        self.tree.expandToDepth(1)  # 默认展开前两层，深层按需展开

        # 值列自动占满剩余空间；字段列宽度在首次显示时设置（见 showEvent）
        header = self.tree.header()
        header.setMinimumSectionSize(80)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.tree, 1)

        # 底部操作按钮
        button_layout = QHBoxLayout()

        # 复制反馈提示（次要文本，短暂显示后清空）
        self.hint_label = QLabel()
        self.hint_label.setObjectName("statusLabel")

        expand_button = QPushButton("展开全部")
        expand_button.clicked.connect(self.tree.expandAll)
        collapse_button = QPushButton("折叠全部")
        collapse_button.clicked.connect(self.tree.collapseAll)
        copy_value_button = QPushButton("复制字段值")
        copy_value_button.clicked.connect(self._copy_current_value)

        close_button = QPushButton("关闭")
        close_button.setObjectName("primaryButton")
        close_button.setMinimumWidth(80)
        close_button.clicked.connect(self.close)

        button_layout.addWidget(expand_button)
        button_layout.addWidget(collapse_button)
        button_layout.addWidget(copy_value_button)
        button_layout.addWidget(self.hint_label)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

    def showEvent(self, event):
        """首次显示后设置字段列宽

        Qt 在布局激活时会重置尚未显示的表头列宽，故须在 show 之后再设置，
        否则字段列会退回默认宽度并截断较长的键名（如 country_cn）。
        """
        super().showEvent(event)
        if not getattr(self, '_columns_sized', False):
            self._columns_sized = True
            self.tree.header().resizeSection(0, 280)

    def _build_summary(self) -> QWidget:
        """构建关键字段摘要区，按 SUMMARY_COLUMNS 列排布键值对"""
        card = StyledWidget()
        grid = QGridLayout(card)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(6)

        shown = 0
        for path, label in self.SUMMARY_FIELDS:
            value = self._get_by_path(self.data, path)
            if value is None or value == '':  # 缺失或空值不展示
                continue
            row, col = divmod(shown, self.SUMMARY_COLUMNS)

            key_label = QLabel(label)
            key_label.setObjectName("summaryKey")
            value_label = QLabel(str(value))
            value_label.setObjectName("summaryValue")
            # 允许鼠标选中复制
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            grid.addWidget(key_label, row, col * 2)
            grid.addWidget(value_label, row, col * 2 + 1)
            shown += 1

        if shown == 0:  # 无关键字段时给出提示
            empty_label = QLabel("无关键字段信息，请查看下方完整数据")
            empty_label.setObjectName("statusLabel")
            grid.addWidget(empty_label, 0, 0)

        return card

    @staticmethod
    def _get_by_path(data: Any, path: str) -> Any:
        """按点分路径（如 location.city_cn）从嵌套字典取值，缺失返回 None"""
        current = data
        for part in path.split('.'):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def _populate(self, parent: QTreeWidgetItem, data: Any):
        """递归将 dict/list 数据填充为树节点"""
        if isinstance(data, dict):
            for key, value in data.items():
                self._add_node(parent, str(key), value)
        elif isinstance(data, list):
            for index, value in enumerate(data):
                self._add_node(parent, f'[{index}]', value)

    def _add_node(self, parent: QTreeWidgetItem, key: str, value: Any) -> QTreeWidgetItem:
        """新增一个树节点：容器类型显示条目数量并可展开，叶子值按类型着色"""
        node = QTreeWidgetItem(parent, [key, ''])
        node.setToolTip(0, key)

        if isinstance(value, (dict, list)):
            # 容器节点：值列显示数量摘要，键列加粗以示层级
            count = len(value)
            unit = '个字段' if isinstance(value, dict) else '项'
            node.setText(1, f'{count} {unit}')
            node.setForeground(1, QBrush(QColor(self.theme.text_secondary)))
            font = node.font(0)
            font.setBold(True)
            node.setFont(0, font)
            self._populate(node, value)
        else:
            # 叶子节点：显示值并按数据类型着色
            node.setText(1, self._format_value(value))
            node.setForeground(1, QBrush(QColor(self._value_color(value))))
            node.setToolTip(1, str(value))

        # 保存原始值，供"复制字段值"使用
        node.setData(0, Qt.ItemDataRole.UserRole, value)
        return node

    @staticmethod
    def _format_value(value: Any) -> str:
        """将 Python 值格式化为与 JSON 一致的展示文本"""
        if value is None:
            return 'null'
        if isinstance(value, bool):
            return 'true' if value else 'false'
        return str(value)

    def _value_color(self, value: Any) -> str:
        """按数据类型返回对应的主题前景色令牌"""
        if value is None:
            return self.theme.value_null
        if isinstance(value, bool):
            return self.theme.value_bool
        if isinstance(value, (int, float)):
            return self.theme.value_number
        return self.theme.value_string

    def _filter_tree(self, text: str):
        """搜索框变动时过滤树节点"""
        keyword = text.strip().lower()
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            self._filter_item(root.child(i), keyword)

    def _filter_item(self, item: QTreeWidgetItem, keyword: str) -> bool:
        """递归过滤：自身命中或任一子节点命中即保留显示

        返回该节点是否可见，供父节点判断是否需要保留。
        """
        matched = keyword in item.text(0).lower() or keyword in item.text(1).lower()
        child_matched = False
        for i in range(item.childCount()):
            if self._filter_item(item.child(i), keyword):
                child_matched = True

        visible = (not keyword) or matched or child_matched
        item.setHidden(not visible)
        if keyword and visible and child_matched:
            item.setExpanded(True)  # 命中结果自动展开，便于查看
        return visible

    def _show_context_menu(self, position):
        """树节点右键菜单：复制字段值 / 复制完整 JSON"""
        item = self.tree.itemAt(position)
        if not item:
            return

        menu = QMenu(self)
        copy_value_action = menu.addAction("复制该字段值")
        copy_json_action = menu.addAction("复制完整 JSON")
        action = menu.exec(self.tree.mapToGlobal(position))

        if action == copy_value_action:
            self._copy_item_value(item)
        elif action == copy_json_action:
            self._copy_json()

    def _copy_current_value(self):
        """复制当前选中节点的字段值"""
        item = self.tree.currentItem()
        if item:
            self._copy_item_value(item)
        else:
            self._set_hint("请先在树中选择一个字段")

    def _copy_item_value(self, item: QTreeWidgetItem):
        """复制指定节点的原始值：容器转为 JSON，叶子取原始值文本"""
        value = item.data(0, Qt.ItemDataRole.UserRole)
        text = json.dumps(value, ensure_ascii=False, indent=2) \
            if isinstance(value, (dict, list)) else self._format_value(value)
        QApplication.clipboard().setText(text)
        self._set_hint(f"已复制：{item.text(0)}")

    def _copy_json(self):
        """复制整条数据的格式化 JSON"""
        QApplication.clipboard().setText(json.dumps(self.data, ensure_ascii=False, indent=2))
        self._set_hint("已复制完整 JSON")

    def _set_hint(self, message: str):
        """在底部显示操作反馈提示"""
        self.hint_label.setText(message)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.query_manager = None
        self.export_manager = ExportManager()
        self.results = None
        self.query_worker = None
        self.progress_dialog = None
        # 初始化主题：读取用户设置（浅色/深色/跟随系统）并应用全局 QSS
        self._init_theme()
        self.setup_ui()
        self.load_auth_settings()
        self.setup_table_styles()

    def _init_theme(self):
        """读取主题设置并应用，同时监听系统深浅色变化"""
        self.theme_mode = settings.get('ui.theme', 'system')  # system / light / dark
        self._apply_theme()
        # Qt 6.5+ 支持监听系统主题变化，仅在"跟随系统"模式下动态切换
        try:
            QApplication.instance().styleHints().colorSchemeChanged.connect(
                lambda *_: self._apply_theme() if self.theme_mode == 'system' else None)
        except (AttributeError, RuntimeError):
            pass

    def _apply_theme(self):
        """按当前模式解析主题并应用全局样式表"""
        from PySide6.QtGui import QPalette
        mode = self.theme_mode
        if mode == 'system':
            # 跟随系统：通过调色板窗口底色亮度判断深浅色
            base = QApplication.instance().palette().color(QPalette.ColorRole.Window)
            mode = 'dark' if base.lightness() < 128 else 'light'
        self.theme = get_theme(mode)
        QApplication.instance().setStyleSheet(build_qss(self.theme))

    def _on_theme_changed(self, index: int):
        """主题下拉框切换：保存设置并立即生效"""
        self.theme_mode = ['system', 'light', 'dark'][index]
        settings.set('ui.theme', self.theme_mode)
        settings.save_config()
        self._apply_theme()

    def _setup_auth_section(self, layout: QVBoxLayout):
        """Setup authentication section"""
        auth_group = StyledWidget()
        auth_layout = QVBoxLayout(auth_group)
        auth_layout.setSpacing(8)
        auth_layout.setContentsMargins(12, 12, 12, 12)

        # 标题
        title = QLabel("认证设置")
        title.setObjectName("sectionTitle")
        auth_layout.addWidget(title)

        # Cookie输入区域
        cookie_widget = QWidget()
        cookie_layout = QVBoxLayout(cookie_widget)
        cookie_layout.setContentsMargins(0, 0, 0, 0)
        cookie_layout.setSpacing(6)
        
        cookie_label = QLabel("Cookie:")
        cookie_label.setObjectName("fieldLabel")
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
        self.remember_auth.setObjectName("accentText")
        remember_layout.addWidget(self.remember_auth)
        remember_layout.addStretch()
        
        auth_layout.addWidget(remember_widget)

        # 保存按钮
        save_widget = QWidget()
        save_layout = QHBoxLayout(save_widget)
        save_layout.setContentsMargins(0, 0, 0, 0)
        
        self.save_auth_button = QPushButton("保存Cookie")
        self.save_auth_button.setMinimumHeight(32)
        self.save_auth_button.setObjectName("primaryButton")
        self.save_auth_button.clicked.connect(self.save_auth_settings)
        save_layout.addWidget(self.save_auth_button)
        save_layout.addStretch()

        auth_layout.addWidget(save_widget)

        # 主题切换（跟随系统/浅色/深色），立即生效并持久化
        theme_widget = QWidget()
        theme_layout = QHBoxLayout(theme_widget)
        theme_layout.setContentsMargins(0, 0, 0, 0)
        theme_label = QLabel("主题:")
        theme_label.setObjectName("fieldLabel")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["跟随系统", "浅色", "深色"])
        self.theme_combo.setCurrentIndex(['system', 'light', 'dark'].index(self.theme_mode))
        self.theme_combo.setMinimumHeight(32)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()

        auth_layout.addWidget(theme_widget)
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
        title.setObjectName("sectionTitle")
        query_layout.addWidget(title)

        # 查询输入区域
        query_input_group = QWidget()
        query_input_layout = QVBoxLayout(query_input_group)
        query_input_layout.setContentsMargins(0, 0, 0, 0)
        query_input_layout.setSpacing(6)
        
        query_label = QLabel("查询语句:")
        query_label.setObjectName("fieldLabel")
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
        size_label.setObjectName("fieldLabel")
        self.size_input = QSpinBox()
        self.size_input.setRange(1, 100000)
        self.size_input.setValue(settings.get('query.default_size'))
        self.size_input.setMinimumHeight(32)
        
        # 输出格式选择
        format_label = QLabel("输出格式:")
        format_label.setObjectName("fieldLabel")
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

        # 状态标签
        self.status_label = QLabel()
        self.status_label.setObjectName("statusLabel")
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)
        
        query_layout.addWidget(progress_group)

        # 查询按钮
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        self.query_button = QPushButton("执行查询")
        self.query_button.setMinimumHeight(32)
        self.query_button.setObjectName("primaryButton")
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
        title.setObjectName("sectionTitle")
        results_layout.addWidget(title)

        # 创建选项卡（样式由全局 QSS 统一控制）
        self.tab_widget = QTabWidget()
        self.tab_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # 表格视图（样式由全局 QSS 统一控制）
        self.table = QTableWidget()
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setColumnCount(len(settings.get('export.fields')))
        self.table.setHorizontalHeaderLabels(settings.get('export.fields'))

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
        
        # JSON视图（等宽字体样式由全局 QSS 统一控制）
        self.json_view = QTextEdit()
        self.json_view.setReadOnly(True)

        # 添加到选项卡
        self.tab_widget.addTab(self.table, "表格视图")
        self.tab_widget.addTab(self.json_view, "JSON视图")

        results_layout.addWidget(self.tab_widget)
        layout.addWidget(results_group)
        
    def _show_item_detail(self, row, _col):
        """显示数据项详情：以结构化树形视图呈现（见 DataDetailDialog）"""
        if not self.results or 'data' not in self.results or row >= len(self.results['data']):
            return

        # 获取选中行的完整数据并交给结构化详情对话框展示
        item_data = self.results['data'][row]
        DataDetailDialog(item_data, self.theme, self).exec()
        
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
        self.export_button.setObjectName("primaryButton")
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
        # 已包含字段符（field: 或 field= 语法）或逻辑运算符时，视为完整查询语句，原样透传，
        # 避免 icp="xxx" 这类语句被错误包裹成 domain: "icp="xxx""（issue #7）
        if re.search(r'\w+\s*[:=]', query) or re.search(r'\b(AND|OR|NOT)\b', query, re.IGNORECASE):
            return query

        # 仅裸关键词（如 example.com）默认按 domain 查询，统一剥掉用户自带引号后用双引号包裹
        return f'domain: "{query.strip("\"\'")}"'

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
                
                # 根据列类型设置不同的样式（颜色取自当前主题令牌，适配深浅色）
                if field == 'ip' or field == 'port':
                    table_item.setForeground(QBrush(QColor(self.theme.ip_text)))
                elif field == 'domain':
                    table_item.setForeground(QBrush(QColor(self.theme.domain_text)))
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