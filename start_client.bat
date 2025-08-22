@echo off
chcp 65001 >nul
title 反作弊语音客户端

echo.
echo ========================================
echo    反作弊语音客户端启动器
echo ========================================
echo.

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python未安装或未添加到PATH
    echo 请安装Python 3.7+
    pause
    exit /b 1
)

REM 检查配置文件
if not exist "client_config.json" (
    echo ❌ 配置文件不存在
    echo 正在创建默认配置...
    python update_server_ip.py 47.239.226.21
)

REM 显示当前配置
echo 📋 当前配置:
python -c "import json; config=json.load(open('client_config.json')); print(f'   服务器: {config[\"server\"][\"ip\"]}:{config[\"server\"][\"port\"]}')"
echo.

REM 启动客户端
echo 🚀 启动客户端...
python gui_udp_client.py

echo.
echo 客户端已退出
pause
