# -*- coding: utf-8 -*-
"""
项目启动器：自动检查并安装缺失依赖，然后启动 Web 演示服务。
用法：
    python run_web.py [--port 8000]
说明：
- 使用当前 Python 解释器调用 pip 安装所需依赖
- 安装完成后通过 `python -m uvicorn whisper.web_server:app --reload` 启动
- Windows 上建议从 run_web.bat 调用本脚本
"""

import sys
import os
import subprocess
import importlib
from argparse import ArgumentParser

# 需要检测的模块 -> 对应要安装的包（可含extras/版本约束）
REQUIRED = [
    ("faster_whisper", "faster-whisper"),
    ("dotenv", "python-dotenv"),
    ("httpx", "httpx[http2]>=0.24.0"),
    ("fastapi", "fastapi>=0.110"),
    ("uvicorn", "uvicorn[standard]>=0.23"),
    ("multipart", "python-multipart>=0.0.7"),
    ("aiofiles", "aiofiles>=23.2.1"),
    ("onnxruntime", "onnxruntime>=1.15.0"),
]


def ensure_package(module_name: str, package_spec: str) -> None:
    try:
        importlib.import_module(module_name)
        print(f"✅ 依赖已安装: {module_name}")
    except ImportError:
        print(f"📦 正在安装缺失依赖: {package_spec} (for import '{module_name}')")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_spec])
        # 再试一次导入
        importlib.import_module(module_name)
        print(f"✅ 安装完成: {module_name}")


def ensure_all_packages():
    for mod, pkg in REQUIRED:
        ensure_package(mod, pkg)


def main():
    parser = ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    # 将项目根目录加入 sys.path，避免包导入问题
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    print("🔍 检查并安装依赖...")
    ensure_all_packages()

   
    # 使用子进程启动 uvicorn（支持 --reload）
    cmd = [
        sys.executable, "-m", "uvicorn",
        "whisper.web_server:app",
        "--host", "127.0.0.1",
        "--port", str(args.port),
        "--reload",
    ]
    # 继承当前环境变量，确保 PYTHONPATH 包含项目根
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", project_root)
    subprocess.call(cmd, env=env)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"❌ 命令执行失败: {e}")
        sys.exit(e.returncode if hasattr(e, 'returncode') else 1)

