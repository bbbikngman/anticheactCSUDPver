@echo off
echo 🚀 开始打包客户端...

REM 安装PyInstaller（如果未安装）
pip install pyinstaller

REM 打包客户端（排除tkinter依赖）
pyinstaller --onefile --windowed --name=VoiceClient --exclude-module=tkinter --exclude-module=_tkinter --exclude-module=tcl --exclude-module=tk gui_udp_client.py

REM 复制配置文件
copy client_config.json dist\

echo ✅ 打包完成！
echo 📁 可执行文件: dist\VoiceClient.exe
pause
