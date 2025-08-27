#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
客户端打包脚本
使用PyInstaller将GUI客户端打包为独立的EXE文件
"""

import os
import sys
import subprocess
import shutil

def build_client():
    """打包客户端为EXE"""
    
    print("🚀 开始打包客户端...")
    
    # 检查PyInstaller是否安装
    try:
        import PyInstaller
        print(f"✅ PyInstaller版本: {PyInstaller.__version__}")
    except ImportError:
        print("❌ PyInstaller未安装，正在安装...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # 打包命令 - 使用onedir模式避免tkinter问题
    cmd = [
        "pyinstaller",
        "--onedir",                     # 打包为目录（避免tkinter问题）
        "--console",                    # 保留控制台窗口以便调试
        "--name=VoiceClient",           # EXE文件名
        "--add-data=client_config.json;.",  # 包含配置文件
        "--hidden-import=numpy",        # 确保numpy被包含
        "--hidden-import=numpy._core",  # numpy核心模块
        "--hidden-import=numpy._core._exceptions",  # numpy异常模块
        "--hidden-import=sounddevice",  # 确保sounddevice被包含
        "--hidden-import=pygame",       # 确保pygame被包含
        "--hidden-import=websockets",   # 确保websockets被包含
        "--hidden-import=tkinter",      # 确保tkinter被包含
        "--hidden-import=tkinter.ttk",  # tkinter主题
        "--hidden-import=audioop",      # 音频操作模块
        "--hidden-import=threading",    # 线程模块
        "--hidden-import=json",         # JSON模块
        "--collect-all=numpy",          # 收集numpy的所有依赖
        "--collect-all=sounddevice",    # 收集sounddevice的所有依赖
        "--collect-all=pygame",         # 收集pygame的所有依赖
        "--collect-all=tkinter",        # 收集tkinter的所有依赖
        "gui_udp_client.py"            # 主程序文件
    ]

    # 如果图标文件存在，添加图标参数
    if os.path.exists("assets/app.ico"):
        cmd.insert(-1, "--icon=assets/app.ico")
    elif os.path.exists("icon.ico"):
        cmd.insert(-1, "--icon=icon.ico")
    
    print(f"🔨 执行打包命令: {' '.join(cmd)}")
    
    try:
        # 执行打包
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ 打包成功！")
        
        # 检查输出文件（onedir模式）
        exe_path = os.path.join("dist", "VoiceClient", "VoiceClient.exe")
        dist_dir = os.path.join("dist", "VoiceClient")

        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"📦 EXE文件: {exe_path}")
            print(f"📏 文件大小: {size_mb:.1f} MB")

            # 复制配置文件到dist目录
            config_src = "client_config.json"
            config_dst = os.path.join(dist_dir, "client_config.json")
            if os.path.exists(config_src):
                shutil.copy2(config_src, config_dst)
                print(f"📋 配置文件已复制: {config_dst}")

            print("\n🎉 打包完成！")
            print(f"📁 可执行文件位置: {os.path.abspath(exe_path)}")
            print(f"📁 完整应用目录: {os.path.abspath(dist_dir)}")
            print("💡 使用说明:")
            print("   1. 进入dist/VoiceClient目录")
            print("   2. 双击VoiceClient.exe启动客户端")
            print("   3. 确保服务器地址配置正确")

        else:
            print("❌ 未找到生成的EXE文件")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 打包失败: {e}")
        print(f"错误输出: {e.stderr}")
        return False
    
    return True

def clean_build():
    """清理构建文件"""
    dirs_to_clean = ["build", "dist", "__pycache__"]
    files_to_clean = ["*.spec"]
    
    print("🧹 清理构建文件...")
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"🗑️ 删除目录: {dir_name}")
    
    import glob
    for pattern in files_to_clean:
        for file_path in glob.glob(pattern):
            os.remove(file_path)
            print(f"🗑️ 删除文件: {file_path}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="客户端打包工具")
    parser.add_argument("--clean", action="store_true", help="清理构建文件")
    parser.add_argument("--build", action="store_true", help="打包客户端")
    
    args = parser.parse_args()
    
    if args.clean:
        clean_build()
    
    if args.build or (not args.clean):
        # 默认执行打包
        success = build_client()
        if not success:
            sys.exit(1)
    
    print("✅ 完成！")
