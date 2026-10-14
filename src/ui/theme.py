"""
设计令牌与全局 QSS 主题生成器。

集中管理应用的全部视觉样式：
- Theme 数据类定义一套设计令牌（色板、语义化颜色），内置浅色/深色两套主题
- build_qss() 根据令牌生成覆盖全部组件的全局 QSS，替代原先散落在各组件中的 26+ 处内联样式
- get_theme() 按用户设置解析主题（支持跟随系统）

组件通过 objectName 挂接语义化样式：
- #sectionTitle   分区标题（认证设置/查询设置/查询结果）
- #fieldLabel     字段标签（Cookie/查询语句等，品牌绿色）
- #accentText     强调文本（记住Cookie 复选框）
- #statusLabel    次要状态文本
- #primaryButton  主按钮（绿底白字）
- #dangerButton   危险操作按钮（红底白字）
- #summaryKey     数据详情摘要区的字段名
- #summaryValue   数据详情摘要区的字段值

树形组件（QTreeWidget，用于数据详情的嵌套数据展示）样式也在此统一生成；
详情树中每个值的颜色按数据类型在运行时从令牌取用（value_string/value_number/value_bool/value_null）。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    """一套主题的完整设计令牌（颜色均为十六进制字符串）"""
    name: str            # 主题标识：light / dark
    window_bg: str       # 窗口底色
    card_bg: str         # 卡片（StyledWidget）背景
    card_border: str     # 卡片边框
    text_primary: str    # 主要文字
    text_secondary: str  # 次要/辅助文字
    primary: str         # 品牌主色（绿）
    primary_hover: str   # 主色悬停态
    primary_pressed: str # 主色按压态
    on_primary: str      # 主色之上的文字色
    danger: str          # 危险色（删除按钮）
    danger_hover: str
    input_bg: str        # 输入控件背景
    input_border: str    # 输入控件边框
    header_bg: str       # 表头背景
    header_text: str     # 表头文字
    selection_bg: str    # 选中行背景
    selection_text: str  # 选中行文字
    alt_row_bg: str      # 表格交替行背景
    grid_line: str       # 表格分隔线
    mono_bg: str         # 等宽文本视图（JSON）背景
    ip_text: str         # 表格中 IP/端口 字段文字色
    domain_text: str     # 表格中域名字段文字色
    # 数据详情树：按值的数据类型区分的前景色
    value_string: str    # 字符串值
    value_number: str    # 数值
    value_bool: str      # 布尔值
    value_null: str      # 空值


# 浅色主题：延续原有绿色品牌风格
LIGHT = Theme(
    name='light',
    window_bg='#f5f6f7', card_bg='#ffffff', card_border='#e0e0e0',
    text_primary='#212121', text_secondary='#607d8b',
    primary='#2e7d32', primary_hover='#43a047', primary_pressed='#1b5e20',
    on_primary='#ffffff', danger='#dc3545', danger_hover='#c82333',
    input_bg='#ffffff', input_border='#d0d0d0',
    header_bg='#f0f7f0', header_text='#2e7d32',
    selection_bg='#e8f5e9', selection_text='#2e7d32',
    alt_row_bg='#fafafa', grid_line='#f0f0f0', mono_bg='#fafafa',
    ip_text='#1565c0', domain_text='#2e7d32',
    # 值类型配色（参考代码编辑器配色，浅底可读）
    value_string='#22863a', value_number='#0550ae',
    value_bool='#b31d28', value_null='#6a737d',
)

# 深色主题：提高主色亮度保证暗底对比度
DARK = Theme(
    name='dark',
    window_bg='#202124', card_bg='#2a2b2e', card_border='#3c4043',
    text_primary='#e8eaed', text_secondary='#9aa0a6',
    primary='#4caf50', primary_hover='#66bb6a', primary_pressed='#388e3c',
    on_primary='#ffffff', danger='#e53935', danger_hover='#ef5350',
    input_bg='#303134', input_border='#4a4d51',
    header_bg='#263326', header_text='#81c784',
    selection_bg='#1b3a24', selection_text='#81c784',
    alt_row_bg='#26272a', grid_line='#3a3d40', mono_bg='#26272a',
    ip_text='#64b5f6', domain_text='#81c784',
    # 值类型配色（暗底提亮，保证对比度）
    value_string='#7ee787', value_number='#79c0ff',
    value_bool='#ff7b72', value_null='#8b949e',
)

_THEMES = {'light': LIGHT, 'dark': DARK}


def get_theme(name: str) -> Theme:
    """按名称取主题，未知名称回退浅色"""
    return _THEMES.get(name, LIGHT)


def build_qss(t: Theme) -> str:
    """根据主题令牌生成全局 QSS（在 QApplication 上一次设置，弹窗亦生效）"""
    return f"""
/* ===== 基础：窗口与卡片 ===== */
QMainWindow, QDialog {{
    background-color: {t.window_bg};
}}
StyledWidget {{
    background-color: {t.card_bg};
    border: 1px solid {t.card_border};
    border-radius: 8px;
}}

/* ===== 文字 ===== */
QLabel {{
    background: transparent;
    color: {t.text_primary};
}}
QLabel#sectionTitle {{
    font-size: 14px;
    font-weight: bold;
    color: {t.primary};
    padding-bottom: 4px;
}}
QLabel#fieldLabel {{
    font-weight: 500;
    color: {t.primary};
}}
QLabel#statusLabel {{
    color: {t.text_secondary};
    font-size: 12px;
}}
/* 数据详情摘要区的键/值标签 */
QLabel#summaryKey {{
    color: {t.text_secondary};
    font-size: 12px;
}}
QLabel#summaryValue {{
    color: {t.text_primary};
    font-weight: bold;
    font-size: 13px;
}}
QCheckBox {{
    color: {t.text_primary};
    background: transparent;
}}
QCheckBox#accentText {{
    color: {t.primary};
}}

/* ===== 输入控件 ===== */
QLineEdit, QSpinBox, QComboBox {{
    background-color: {t.input_bg};
    border: 1px solid {t.input_border};
    border-radius: 4px;
    padding: 6px 8px;
    color: {t.text_primary};
    selection-background-color: {t.selection_bg};
    selection-color: {t.selection_text};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {t.primary};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {t.card_bg};
    color: {t.text_primary};
    border: 1px solid {t.card_border};
    selection-background-color: {t.selection_bg};
    selection-color: {t.selection_text};
}}

/* ===== 按钮：默认描边 / 主按钮 / 危险按钮 ===== */
QPushButton {{
    background: transparent;
    border: 1px solid {t.input_border};
    border-radius: 4px;
    padding: 6px 14px;
    color: {t.text_primary};
}}
QPushButton:hover {{
    border-color: {t.primary};
    color: {t.primary};
}}
QPushButton#primaryButton {{
    background-color: {t.primary};
    color: {t.on_primary};
    border: none;
}}
QPushButton#primaryButton:hover {{
    background-color: {t.primary_hover};
}}
QPushButton#primaryButton:pressed {{
    background-color: {t.primary_pressed};
}}
QPushButton#primaryButton:disabled {{
    background-color: {t.input_border};
    color: {t.text_secondary};
}}
QPushButton#dangerButton {{
    background-color: {t.danger};
    color: #ffffff;
    border: none;
}}
QPushButton#dangerButton:hover {{
    background-color: {t.danger_hover};
}}

/* ===== 进度条 ===== */
QProgressBar {{
    border: 1px solid {t.card_border};
    border-radius: 4px;
    background-color: {t.input_bg};
    text-align: center;
    color: {t.text_primary};
}}
QProgressBar::chunk {{
    background-color: {t.primary};
    border-radius: 3px;
}}

/* ===== 选项卡 ===== */
QTabWidget::pane {{
    border: 1px solid {t.card_border};
    border-radius: 4px;
}}
QTabBar::tab {{
    background-color: {t.input_bg};
    color: {t.text_secondary};
    border: 1px solid {t.card_border};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 6px 12px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {t.card_bg};
    color: {t.primary};
    font-weight: bold;
}}

/* ===== 表格 ===== */
QTableWidget {{
    background-color: {t.card_bg};
    alternate-background-color: {t.alt_row_bg};
    gridline-color: {t.grid_line};
    border: none;
    color: {t.text_primary};
    selection-background-color: {t.selection_bg};
    selection-color: {t.selection_text};
}}
QTableWidget::item {{
    padding: 5px;
    border-bottom: 1px solid {t.grid_line};
}}
QHeaderView::section {{
    background-color: {t.header_bg};
    color: {t.header_text};
    font-weight: bold;
    border: none;
    border-right: 1px solid {t.card_border};
    border-bottom: 1px solid {t.card_border};
    padding: 6px;
}}

/* ===== 树形视图（数据详情） ===== */
QTreeWidget {{
    background-color: {t.card_bg};
    alternate-background-color: {t.alt_row_bg};
    border: 1px solid {t.card_border};
    border-radius: 4px;
    color: {t.text_primary};
    selection-background-color: {t.selection_bg};
    selection-color: {t.selection_text};
}}
QTreeWidget::item {{
    padding: 4px 2px;
    border-bottom: 1px solid {t.grid_line};
}}
QTreeWidget::item:selected {{
    background-color: {t.selection_bg};
    color: {t.selection_text};
}}

/* ===== 文本视图（JSON 等宽）与列表 ===== */
QTextEdit {{
    background-color: {t.mono_bg};
    border: none;
    border-radius: 4px;
    color: {t.text_primary};
    font-family: Consolas, 'Courier New', monospace;
    font-size: 12px;
    padding: 8px;
}}
QListWidget {{
    background-color: {t.card_bg};
    border: 1px solid {t.card_border};
    border-radius: 4px;
    color: {t.text_primary};
    font-size: 13px;
}}
QListWidget::item {{
    padding: 8px;
    border-bottom: 1px solid {t.grid_line};
}}
QListWidget::item:selected {{
    background-color: {t.selection_bg};
    color: {t.selection_text};
}}

/* ===== 右键菜单与滚动条 ===== */
QMenu {{
    background-color: {t.card_bg};
    border: 1px solid {t.card_border};
}}
QMenu::item {{
    padding: 6px 20px;
    color: {t.text_primary};
}}
QMenu::item:selected {{
    background-color: {t.selection_bg};
    color: {t.selection_text};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background-color: {t.input_border};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {t.text_secondary};
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background-color: {t.input_border};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {t.text_secondary};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
}}
QToolTip {{
    background-color: {t.card_bg};
    color: {t.text_primary};
    border: 1px solid {t.card_border};
    padding: 4px;
}}
"""
