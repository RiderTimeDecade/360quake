
import os
import sys

def _append_run_path():
    if getattr(sys, 'frozen', False):
        # 如果是打包后的可执行文件
        application_path = os.path.dirname(sys.executable)
        # 添加 Qt 库路径到系统路径
        qt_bin_path = os.path.join(application_path, 'PyQt6', 'Qt6', 'bin')
        qt_plugins_path = os.path.join(application_path, 'PyQt6', 'Qt6', 'plugins')
        if os.path.exists(qt_bin_path):
            os.environ['PATH'] = qt_bin_path + os.pathsep + os.environ.get('PATH', '')
        if os.path.exists(qt_plugins_path):
            os.environ['QT_PLUGIN_PATH'] = qt_plugins_path
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(qt_plugins_path, 'platforms')

_append_run_path()
