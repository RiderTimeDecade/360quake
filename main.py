"""
Main entry point for the application.
"""
import sys
import os
import traceback

def main():
    """Main entry point"""
    try:
        # 设置环境变量以启用 PyQt6 调试输出
        os.environ['QT_DEBUG_PLUGINS'] = '1'
        
        # 添加 Qt 库路径到系统路径
        import site
        site_packages = site.getsitepackages()[0]
        qt_bin_path = os.path.join(site_packages, 'PyQt6', 'Qt6', 'bin')
        if os.path.exists(qt_bin_path):
            os.environ['PATH'] = qt_bin_path + os.pathsep + os.environ.get('PATH', '')
            print(f"Added Qt bin path: {qt_bin_path}")
        
        # 设置工作目录为程序所在目录
        if getattr(sys, 'frozen', False):
            # 如果是打包后的可执行文件
            application_path = os.path.dirname(sys.executable)
        else:
            # 如果是直接运行 Python 脚本
            application_path = os.path.dirname(os.path.abspath(__file__))
        
        os.chdir(application_path)
        print(f"Working directory: {application_path}")
        
        # 导入 Qt 模块
        print("Importing PyQt6...")
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QCoreApplication
        print("PyQt6 imported successfully")
        
        # 设置应用程序属性
        QCoreApplication.setOrganizationName("360")
        QCoreApplication.setApplicationName("360 Quake Query Tool")
        
        # 创建应用实例
        print("Creating application instance...")
        app = QApplication(sys.argv)
        
        # 导入主窗口
        print("Importing MainWindow...")
        from src.ui.main_window import MainWindow
        
        # 创建主窗口
        print("Creating main window...")
        window = MainWindow()
        window.show()
        
        # 运行应用
        print("Starting application...")
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Traceback:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 