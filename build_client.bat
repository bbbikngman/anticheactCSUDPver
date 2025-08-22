@echo off
REM 一键构建 AntiFraudClient 可执行文件（onedir）
SET VENV=whisper\venv_antifraud\Scripts

REM 安装依赖（避免使用全局Python带来的typing冲突）
"%VENV%\pip.exe" install --upgrade pip
"%VENV%\pip.exe" install -r whisper\requirements.txt

REM 创建图标文件
"%VENV%\python.exe" create_icons.py

REM 运行 PyInstaller 打包（onedir，保留控制台日志为False）
"%VENV%\pyinstaller.exe" --noconsole --onedir --name AntiFraudClient gui_udp_client.py

IF %ERRORLEVEL% NEQ 0 (
  echo Build failed.
  exit /b 1
)

echo Build succeeded. Check dist\AntiFraudClient\
exit /b 0

