import torch

# 检查PyTorch版本
print(f"PyTorch Version: {torch.__version__}")

# 检查CUDA是否可用
is_available = torch.cuda.is_available()
print(f"CUDA Available: {is_available}")

if is_available:
    # 查看可用的GPU数量
    print(f"Device Count: {torch.cuda.device_count()}")
    # 查看当前GPU的名称
    print(f"Current Device Name: {torch.cuda.get_device_name(0)}")