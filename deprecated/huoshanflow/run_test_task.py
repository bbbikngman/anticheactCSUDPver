# run_test_task.py
import sys
import shutil
from pathlib import Path
import time

# 任务文件夹必须与 asr_service.py 中的定义一致
TASK_FOLDER = Path("./tasks")

def dispatch_task(file_path: str):
    source_file = Path(file_path)
    if not source_file.exists():
        print(f"错误：文件不存在 -> {file_path}")
        return

    # 为了确保文件名唯一，避免覆盖，我们加上时间戳
    timestamp = int(time.time() * 1000)
    destination_file = TASK_FOLDER / f"{timestamp}_{source_file.name}"
    
    TASK_FOLDER.mkdir(exist_ok=True)
    
    print(f"正在分发任务：将 {source_file.name} 复制到任务文件夹...")
    shutil.copy(source_file, destination_file)
    print(f"任务 '{destination_file.name}' 已成功分发！ASR服务将自动处理。")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python run_test_task.py <音频文件路径>")
        sys.exit(1)
    
    audio_file_path = sys.argv[1]
    dispatch_task(audio_file_path)
