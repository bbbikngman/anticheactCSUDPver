@echo off
echo ========================================
echo 反诈AI电话专员 - 自动安装脚本
echo ========================================
echo.

echo 1. 检查Python环境...
python --version
if %errorlevel% neq 0 (
    echo 错误：未找到Python，请先安装Python 3.8或更高版本
    pause
    exit /b 1
)

echo.
echo 2. 创建虚拟环境...
if not exist "venv_antifraud" (
    python -m venv venv_antifraud
    echo 虚拟环境创建成功
) else (
    echo 虚拟环境已存在
)

echo.
echo 3. 激活虚拟环境...
call venv_antifraud\Scripts\activate

echo.
echo 4. 升级pip...
python -m pip install --upgrade pip

echo.
echo 5. 安装基础依赖...
pip install -r requirements.txt

echo.
echo 6. 安装CUDA版本的PyTorch（推荐）...
echo 正在卸载现有的PyTorch...
pip uninstall torch torchvision torchaudio -y

echo 正在安装CUDA版本的PyTorch...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

echo.
echo 7. 测试CUDA可用性...
python -c "import torch; print(f'PyTorch版本: {torch.__version__}'); print(f'CUDA可用: {torch.cuda.is_available()}'); print(f'CUDA版本: {torch.version.cuda if torch.cuda.is_available() else \"N/A\"}')"

echo.
echo 8. 检查配置文件...
if not exist ".env" (
    echo 警告：未找到.env配置文件
    echo 请确保设置MOONSHOT_API_KEY
) else (
    echo 配置文件存在
)

echo.
echo ========================================
echo 安装完成！
echo ========================================
echo.
echo 使用方法：
echo 1. 确保在.env文件中设置了MOONSHOT_API_KEY
echo 2. 运行：python main.py
echo.
echo 如果遇到问题，请查看README.md文档
echo.
pause
