"""
Build script for creating executables for different platforms.
"""
import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path

WINDOWS_SETTINGS = {
    'name': '360Quake查询工具',
    'icon': 'assets/icon.ico',
    'binary_name': '360Quake查询工具.exe',
    'platform_args': [
        '--version-file=version.txt',
        '--uac-admin'
    ]
}

MACOS_SETTINGS = {
    'name': '360Quake查询工具',
    'icon': 'assets/icon.icns',
    'binary_name': '360Quake查询工具.app',
    'platform_args': [
        '--osx-bundle-identifier=com.360.quake.query',
        '--target-architecture=x86_64,arm64'
    ]
}

LINUX_SETTINGS = {
    'name': '360Quake查询工具',
    'icon': 'assets/icon.png',
    'binary_name': '360Quake查询工具',
    'platform_args': []
}

def clean_build():
    """Clean build directories"""
    dirs_to_clean = ['build', 'dist']
    files_to_clean = ['*.spec']
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
    
    for pattern in files_to_clean:
        for file in Path('.').glob(pattern):
            file.unlink()

def ensure_directory_exists(path):
    """确保目录存在，如果不存在则创建"""
    os.makedirs(os.path.dirname(path), exist_ok=True)

def get_platform_settings():
    """获取当前平台的设置"""
    system = platform.system().lower()
    if system == 'windows':
        return WINDOWS_SETTINGS
    elif system == 'darwin':
        return MACOS_SETTINGS
    else:
        return LINUX_SETTINGS

def build_executable(target_platform=None):
    """Build executable using PyInstaller"""
    # 获取当前工作目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 设置文件路径
    main_file = os.path.join(current_dir, 'main.py')
    settings_file = os.path.join(current_dir, 'src', 'config', 'settings.json')

    # 确保配置目录存在
    ensure_directory_exists(settings_file)

    # 检查必要文件是否存在
    if not os.path.exists(main_file):
        raise FileNotFoundError(f"找不到主程序文件: {main_file}")

    # 获取平台设置
    platform_settings = get_platform_settings()
    
    # 设置数据文件路径分隔符
    separator = ';' if platform.system().lower() == 'windows' else ':'
    
    # 构建数据文件路径列表
    data_files = [
        (settings_file, 'src/config'),  # 配置文件
        (os.path.join(current_dir, 'src'), 'src')  # 整个src目录
    ]
    
    # 构建--add-data参数
    data_args = [f'--add-data={src}{separator}{dst}' for src, dst in data_files]

    # PyInstaller 命令行参数
    cmd = [
        'pyinstaller',
        f'--name={platform_settings["name"]}',
        '--windowed',  # 无控制台窗口
        '--noconfirm',  # 覆盖现有文件
        '--clean',  # 清理临时文件
        '--hidden-import=PyQt6.QtCore',
        '--hidden-import=PyQt6.QtGui',
        '--hidden-import=PyQt6.QtWidgets',
        '--onefile',  # 生成单个可执行文件
    ]

    # 添加图标（如果存在）
    icon_path = os.path.join(current_dir, platform_settings['icon'])
    if os.path.exists(icon_path):
        cmd.append(f'--icon={icon_path}')

    # 添加数据文件参数
    cmd.extend(data_args)

    # 添加平台特定参数
    cmd.extend(platform_settings['platform_args'])

    # 添加主程序文件
    cmd.append(main_file)

    print(f"为 {platform.system()} 平台构建...")
    print("执行命令:", ' '.join(cmd))
    
    # 执行打包命令
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # 打印命令输出
    if result.stdout:
        print("标准输出:", result.stdout)
    if result.stderr:
        print("错误输出:", result.stderr)
    
    # 检查命令执行结果
    if result.returncode != 0:
        raise RuntimeError(f"打包失败，返回码: {result.returncode}")
    
    # 重命名输出文件（如果需要）
    dist_dir = os.path.join(current_dir, 'dist')
    platform_suffix = f"_{platform.system().lower()}"
    if platform.system().lower() == 'darwin':
        platform_suffix += f"_{platform.machine()}"
    
    output_path = os.path.join(dist_dir, platform_settings['binary_name'])
    if os.path.exists(output_path):
        new_name = os.path.splitext(platform_settings['binary_name'])[0] + platform_suffix + os.path.splitext(platform_settings['binary_name'])[1]
        new_path = os.path.join(dist_dir, new_name)
        shutil.move(output_path, new_path)
        print(f"已重命名输出文件为: {new_name}")

def create_version_file():
    """Create version file for Windows executable"""
    version_info = """
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'360'),
         StringStruct(u'FileDescription', u'360 Quake Query Tool'),
         StringStruct(u'FileVersion', u'1.0.0'),
         StringStruct(u'InternalName', u'360quake'),
         StringStruct(u'LegalCopyright', u'Copyright (c) 2024'),
         StringStruct(u'OriginalFilename', u'360Quake查询工具.exe'),
         StringStruct(u'ProductName', u'360 Quake Query Tool'),
         StringStruct(u'ProductVersion', u'1.0.0')])
    ]),
    VarFileInfo([VarStruct(u'Translation', [0x0409, 0x04B0])])
  ]
)
"""
    with open('version.txt', 'w', encoding='utf-8') as f:
        f.write(version_info)

def create_assets_directory():
    """创建资源目录并添加默认图标"""
    assets_dir = 'assets'
    if not os.path.exists(assets_dir):
        os.makedirs(assets_dir)
        print(f"创建资源目录: {assets_dir}")

def main():
    """Main build process"""
    try:
        print("开始构建应用...")
        
        # 创建资源目录
        create_assets_directory()
        
        # 清理旧的构建文件
        print("清理旧的构建文件...")
        clean_build()
        
        # 创建版本信息文件（仅Windows）
        if platform.system().lower() == 'windows':
            print("创建版本信息文件...")
            create_version_file()
        
        # 构建可执行文件
        print("正在构建可执行文件...")
        build_executable()
        
        print("构建完成！")
        
        # 显示输出文件位置
        dist_dir = os.path.abspath('dist')
        print(f"\n可执行文件位置: {dist_dir}")
        print("文件列表:")
        for file in os.listdir(dist_dir):
            print(f"- {file}")
            
    except Exception as e:
        print(f"构建失败: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main() 