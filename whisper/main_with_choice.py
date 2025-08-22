# -*- coding: utf-8 -*-
"""
反诈AI电话专员 - 支持HTTP和WebSocket模式选择的主程序
"""

import sounddevice as sd
import numpy as np
import sys
import time
import queue

import config
from vad_module import VADModule
from audio_handler import AudioHandler
from transcriber_module import Transcriber
from tts_module import TTSModule

def choose_ai_mode():
    """选择AI模式"""
    print("\n" + "="*50)
    print("🛡️ 反诈AI电话专员 Demo")
    print("="*50)
    print("请选择AI连接模式：")
    print("1. HTTP流式模式 (当前默认，稳定)")
    print("2. WebSocket流式模式 (新版本，测试中)")
    print("="*50)
    
    while True:
        try:
            choice = input("请输入选择 (1 或 2): ").strip()
            if choice == "1":
                print("✅ 选择: HTTP流式模式")
                return "http"
            elif choice == "2":
                print("✅ 选择: WebSocket流式模式")
                return "websocket"
            else:
                print("❌ 无效选择，请输入 1 或 2")
        except KeyboardInterrupt:
            print("\n程序被用户中断")
            sys.exit(0)

def main():
    # 选择AI模式
    ai_mode = choose_ai_mode()
    
    print(f"\n--- 反诈AI电话专员 Demo 启动 ({ai_mode.upper()}模式) ---")
    
    transcription_queue = queue.Queue()

    try:
        # 初始化基础模块
        vad = VADModule(config.VAD_SENSITIVITY)
        handler = AudioHandler(config.SILENCE_CHUNKS, config.MAX_SPEECH_S, config.AUDIO_SAMPLE_RATE)
        transcriber = Transcriber(config.WHISPER_MODEL_SIZE, config.DEVICE)
        tts = TTSModule(config.DEVICE)
        
        # 根据选择初始化AI模块
        if ai_mode == "http":
            from brain_ai_module import BrainAIModule
            kimi_ai = BrainAIModule()
            print("🔗 使用HTTP流式API连接")
        else:
            from brain_ai_websocket import BrainAIWebSocketModule
            kimi_ai = BrainAIWebSocketModule()
            print("🔗 使用WebSocket流式API连接")
        
        # 定义用于克隆的声音文件路径
        speaker_voice_path = "anticheat_example.wav"
        
    except Exception as e:
        print(f"初始化模块失败: {e}")
        return

    def audio_callback(indata, frames, time, status):
        if status:
            print(status, file=sys.stderr)
        chunk = indata.flatten().astype(np.float32)
        is_speech = vad.is_speech(chunk)

        # 语音打断检测
        if is_speech and tts.is_playing:
            tts.interrupt_speech_after_delay()

        triggered_audio = handler.process_chunk(chunk, is_speech)
        if triggered_audio is not None:
            print("音频段已捕获，放入转写队列。")
            transcription_queue.put(triggered_audio)

    try:
        with sd.InputStream(
            callback=audio_callback,
            dtype='float32',
            channels=1,
            samplerate=config.AUDIO_SAMPLE_RATE,
            blocksize=config.AUDIO_CHUNK_SAMPLES
        ):
            # 生成并播报开场白
            print(f"\n--- 反诈卫士 ({ai_mode.upper()}模式) ---")
            print("正在生成动态开场白...")
            time.sleep(1.0)

            # 记录开场白生成时间
            opening_start_time = time.time()
            opening_text_stream = kimi_ai.generate_opening_statement()
            tts.speak_stream(opening_text_stream, speaker_wav=speaker_voice_path)
            opening_end_time = time.time()
            print(f"📊 开场白生成耗时: {opening_end_time - opening_start_time:.2f}秒")
            
            print(f"\n(状态: 等待用户回应... - {ai_mode.upper()}模式)")
            
            # 统计信息
            response_times = []
            
            while True:
                try:
                    full_audio = transcription_queue.get(timeout=1)
                    
                    print("\n队列中获取到新任务，开始转写...")
                    transcribe_start_time = time.time()
                    
                    from prompts import WHISPER_PROMPT
                    simplified_chinese_prompt = WHISPER_PROMPT
                    transcribed_text = transcriber.transcribe_audio(
                        full_audio, 
                        config.LANGUAGE_CODE,
                        initial_prompt=simplified_chinese_prompt
                    )
                    
                    transcribe_end_time = time.time()
                    transcribe_duration = transcribe_end_time - transcribe_start_time
                    print(f"转写完成 ({transcribe_duration:.2f}s): '{transcribed_text}'")
                    
                    if transcribed_text:
                        # 记录AI回复生成时间
                        ai_start_time = time.time()
                        response_stream = kimi_ai.get_response_stream(transcribed_text)
                        tts.speak_stream(response_stream, speaker_wav=speaker_voice_path)
                        ai_end_time = time.time()
                        
                        ai_duration = ai_end_time - ai_start_time
                        total_duration = ai_end_time - transcribe_start_time
                        
                        response_times.append(total_duration)
                        avg_response_time = sum(response_times) / len(response_times)
                        
                        print(f"📊 性能统计 ({ai_mode.upper()}模式):")
                        print(f"   转写耗时: {transcribe_duration:.2f}s")
                        print(f"   AI回复耗时: {ai_duration:.2f}s")
                        print(f"   总响应时间: {total_duration:.2f}s")
                        print(f"   平均响应时间: {avg_response_time:.2f}s")
                    
                    if transcription_queue.empty():
                        print(f"\n(状态: 等待用户回应... - {ai_mode.upper()}模式)")

                except queue.Empty:
                    time.sleep(0.1)
                    continue

    except KeyboardInterrupt:
        print(f"\n程序被用户中断，正在退出... ({ai_mode.upper()}模式)")
        
        # 显示最终统计
        if response_times:
            print(f"\n📊 最终性能统计 ({ai_mode.upper()}模式):")
            print(f"   总对话轮数: {len(response_times)}")
            print(f"   平均响应时间: {sum(response_times) / len(response_times):.2f}s")
            print(f"   最快响应: {min(response_times):.2f}s")
            print(f"   最慢响应: {max(response_times):.2f}s")
        
    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        print("程序已关闭。")

if __name__ == "__main__":
    main()
