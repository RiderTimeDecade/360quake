"""
Build script for creating executables for different platforms.
"""
import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path
import argparse
import site

def get_pyqt6_path():
    """获取 PyQt6 的安装路径"""
    site_packages = site.getsitepackages()[0]
    pyqt6_path = os.path.join(site_packages, 'PyQt6')
    if os.path.exists(pyqt6_path):
        return pyqt6_path
    return None

WINDOWS_SETTINGS = {
    'name': '360Quake查询工具',
    'icon': 'assets/icon.ico',
    'binary_name': '360Quake查询工具.exe',
    'platform_args': [
        '--version-file=version.txt',
        '--uac-admin',
        '--hidden-import=PyQt6',
        '--hidden-import=PyQt6.QtCore',
        '--hidden-import=PyQt6.QtGui',
        '--hidden-import=PyQt6.QtWidgets',
        '--hidden-import=PyQt6.sip',
        '--collect-all=PyQt6',
        '--runtime-hook=runtime_hook.py'
    ]
}

MACOS_SETTINGS = {
    'name': '360Quake查询工具',
    'icon': 'assets/icon.icns',
    'binary_name': '360Quake查询工具.app',
    'platform_args': [
        '--osx-bundle-identifier=com.360.quake.query',
        '--target-architecture=x86_64,arm64',
        '--hidden-import=PyQt6',
        '--hidden-import=PyQt6.QtCore',
        '--hidden-import=PyQt6.QtGui',
        '--hidden-import=PyQt6.QtWidgets'
    ]
}

LINUX_SETTINGS = {
    'name': '360Quake查询工具',
    'icon': 'assets/icon.png',
    'binary_name': '360Quake查询工具',
    'platform_args': [
        '--hidden-import=PyQt6',
        '--hidden-import=PyQt6.QtCore',
        '--hidden-import=PyQt6.QtGui',
        '--hidden-import=PyQt6.QtWidgets'
    ]
}

def clean_build():
    """Clean build directories"""
    print("清理构建目录...")
    dirs_to_clean = ['build', 'dist']
    files_to_clean = ['*.spec']
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"已删除 {dir_name} 目录")
    
    for pattern in files_to_clean:
        for file in Path('.').glob(pattern):
            file.unlink()
            print(f"已删除 {file}")

def ensure_requirements():
    """确保所有依赖都已安装"""
    print("检查并安装依赖...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

def create_default_icon():
    """创建默认图标文件"""
    print("创建默认图标文件...")
    os.makedirs('assets', exist_ok=True)
    
    # 创建一个简单的空图标文件
    if not os.path.exists('assets/icon.ico'):
        with open('assets/icon.ico', 'wb') as f:
            # 写入一个最小的有效ICO文件
            f.write(bytes.fromhex('00 00 01 00 01 00 10 10 00 00 01 00 20 00 68 04 00 00 16 00 00 00'))
            f.write(bytes([0] * 1128))  # 添加空白图标数据
    
    if not os.path.exists('assets/icon.png'):
        shutil.copy('assets/icon.ico', 'assets/icon.png')
    
    if not os.path.exists('assets/icon.icns'):
        shutil.copy('assets/icon.ico', 'assets/icon.icns')

def create_runtime_hook():
    """创建运行时钩子文件"""
    print("创建运行时钩子文件...")
    hook_content = '''
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
'''
    with open('runtime_hook.py', 'w', encoding='utf-8') as f:
        f.write(hook_content)

def build_platform(platform_name: str, settings: dict, output_dir: str):
    """为指定平台构建可执行文件"""
    print(f"\n开始构建 {platform_name} 版本...")
    
    # 确保图标文件存在
    create_default_icon()
    
    # 创建运行时钩子
    create_runtime_hook()
    
    # 获取 PyQt6 路径
    pyqt6_path = get_pyqt6_path()
    if pyqt6_path and platform_name == 'windows':
        # 添加 PyQt6 相关的二进制文件
        qt6_plugins = os.path.join(pyqt6_path, 'Qt6', 'plugins')
        qt6_bin = os.path.join(pyqt6_path, 'Qt6', 'bin')
        
        platform_args = settings['platform_args'].copy()
        if os.path.exists(qt6_plugins):
            platforms_path = os.path.join(qt6_plugins, 'platforms')
            styles_path = os.path.join(qt6_plugins, 'styles')
            if os.path.exists(platforms_path):
                platform_args.append(f'--add-data={platforms_path}/*;PyQt6/Qt6/plugins/platforms')
            if os.path.exists(styles_path):
                platform_args.append(f'--add-data={styles_path}/*;PyQt6/Qt6/plugins/styles')
        
        if os.path.exists(qt6_bin):
            platform_args.append(f'--add-data={qt6_bin}/*;PyQt6/Qt6/bin')
    else:
        platform_args = settings['platform_args']
    
    # 准备构建命令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", settings['name'],
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        *platform_args,
        "main.py"
    ]
    
    # 只在图标文件存在时添加图标参数
    if os.path.exists(settings['icon']):
        cmd.extend(["--icon", settings['icon']])
    
    try:
        # 执行构建
        subprocess.run(cmd, check=True)
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 移动构建结果到输出目录
        src = os.path.join("dist", settings['binary_name'])
        dst = os.path.join(output_dir, settings['binary_name'])
        if os.path.exists(src):
            shutil.move(src, dst)
            print(f"构建成功: {dst}")
        else:
            print(f"警告: 未找到构建结果 {src}")
            
    except subprocess.CalledProcessError as e:
        print(f"构建失败: {str(e)}")
        return False
    except Exception as e:
        print(f"发生错误: {str(e)}")
        return False
        
    return True

def build_all():
    """构建所有平台版本"""
    # 清理旧的构建文件
    clean_build()
    
    # 确保依赖已安装
    ensure_requirements()
    
    # 创建输出目录
    output_base = "releases"
    os.makedirs(output_base, exist_ok=True)
    
    # 获取版本号
    version = "1.0.0"  # 可以从version.txt或其他地方获取
    
    # 构建各平台版本
    platforms = {
        "windows": WINDOWS_SETTINGS,
        "macos": MACOS_SETTINGS,
        "linux": LINUX_SETTINGS
    }
    
    results = {}
    for platform_name, settings in platforms.items():
        output_dir = os.path.join(output_base, f"{platform_name}-{version}")
        success = build_platform(platform_name, settings, output_dir)
        results[platform_name] = success
    
    # 打印构建结果
    print("\n构建结果汇总:")
    for platform_name, success in results.items():
        status = "成功" if success else "失败"
        print(f"{platform_name}: {status}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="360Quake查询工具构建脚本")
    parser.add_argument('--platform', choices=['all', 'windows', 'macos', 'linux'],
                      default='all', help='选择要构建的平台')
    args = parser.parse_args()
    
    if args.platform == 'all':
        build_all()
    else:
        # 清理旧的构建文件
        clean_build()
        
        # 确保依赖已安装
        ensure_requirements()
        
        # 构建指定平台
        settings = {
            'windows': WINDOWS_SETTINGS,
            'macos': MACOS_SETTINGS,
            'linux': LINUX_SETTINGS
        }[args.platform]
        
        output_dir = os.path.join("releases", args.platform)
        success = build_platform(args.platform, settings, output_dir)
        
        if success:
            print(f"\n{args.platform}平台构建成功!")
        else:
            print(f"\n{args.platform}平台构建失败!")
            sys.exit(1)

if __name__ == "__main__":
    main() 