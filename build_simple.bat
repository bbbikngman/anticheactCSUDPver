@echo off
echo 🚀 开始打包客户端...

REM 安装PyInstaller（如果未安装）
pip install pyinstaller

REM 打包客户端
pyinstaller --onefile --windowed --name=VoiceClient --add-data=client_config.json;. gui_udp_client.py

REM 复制配置文件
copy client_config.json dist\

echo ✅ 打包完成！
echo 📁 可执行文件: dist\VoiceClient.exe
pause
