# asr_service.py
import asyncio
import logging
import os
import shutil
from pathlib import Path
from asr_client import ASRClient, convert_audio_to_pcm # 从我们的模块中导入

# --- 配置 ---
# 服务将监听这个文件夹里的新音频文件
TASK_FOLDER = Path("./tasks")
# 处理完的文件会被移动到这里
PROCESSED_FOLDER = Path("./processed")

async def main():
    # --- API 认证信息 ---
    APP_ID = "4833163520"
    ACCESS_TOKEN = "X0ppqGDRAEt3u40zKGxGkKc_lk5vXCX3"

    # 确保文件夹存在
    TASK_FOLDER.mkdir(exist_ok=True)
    PROCESSED_FOLDER.mkdir(exist_ok=True)

    # 1. 创建客户端实例
    client = ASRClient(app_id=APP_ID, access_token=ACCESS_TOKEN)
    try:
        # 2. 在服务启动时建立连接
        await client.connect()
        
        # 3. 【实验性改动】暂时禁用预热，以测试连接是否能因不活动而保持
        # await client.warm_up()
        
        logging.info(f"ASR 服务已启动（无预热），正在监听文件夹: {TASK_FOLDER.resolve()}")
        logging.info("请等待至少30秒后，再发送测试任务以验证连接持久性...")

        # 4. 进入无限循环，等待任务
        while True:
            audio_files = list(TASK_FOLDER.glob("*.mp3")) + list(TASK_FOLDER.glob("*.wav"))
            if not audio_files:
                await asyncio.sleep(2)
                continue

            file_path = audio_files[0]
            logging.info(f"\n--- 发现新任务: {file_path.name} ---")

            try:
                audio_data = convert_audio_to_pcm(str(file_path))
                full_transcript = ""
                async for response in client.transcribe(audio_data):
                    if "error" in response:
                        logging.warning(f"收到错误消息: {response['error']}")
                        continue
                    if 'result' in response and 'text' in response['result']:
                        full_transcript = response['result']['text']
                        print(f"\r[ASR] 识别中: {full_transcript}", end="")
                    if response.get('result', {}).get('utterances') and response['result']['utterances'][-1].get('definite'):
                        print()

                logging.info(f"\n--- 文件 {file_path.name} 最终识别结果 ---\n{full_transcript}\n---------------------------")

            except Exception as e:
                logging.error(f"处理文件 {file_path.name} 时发生错误: {e}")
            finally:
                shutil.move(str(file_path), PROCESSED_FOLDER / file_path.name)
                logging.info(f"任务 {file_path.name} 处理完毕，已移至 processed 文件夹。")
                logging.info(f"--- 等待下一个任务... ---")

    except (KeyboardInterrupt, asyncio.CancelledError):
        logging.info("收到关闭信号...")
    except Exception as e:
        logging.error(f"ASR服务主程序发生致命错误: {e}")
    finally:
        logging.info("服务正在关闭，断开连接。")
        await client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n用户中断了服务。")
