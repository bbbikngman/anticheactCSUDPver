# 文件: main.py

import sounddevice as sd
import numpy as np
import sys
import time
import queue

import config
from vad_module import VADModule
from audio_handler import AudioHandler
from transcriber_module import Transcriber
from brain_ai_module import KimiAI
from tts_module import TTSModule # ***** NEW ***** 导入TTS模块

def main():
    print("--- 反诈AI电话专员 Demo 启动 ---")
    
    transcription_queue = queue.Queue()

    try:
        vad = VADModule(config.VAD_SENSITIVITY)
        handler = AudioHandler(config.SILENCE_CHUNKS, config.MAX_SPEECH_S, config.AUDIO_SAMPLE_RATE)
        transcriber = Transcriber(config.WHISPER_MODEL_SIZE, config.DEVICE)
        kimi_ai = KimiAI()
        tts = TTSModule(config.DEVICE) # ***** NEW ***** 实例化TTS模块
        # 定义用于克隆的声音文件路径，如果不存在则设为None
        speaker_voice_path = "anticheat_example.wav" 
    except Exception as e:
        print(f"初始化模块失败: {e}")
        return

    def audio_callback(indata, frames, time, status):
        if status:
            print(status, file=sys.stderr)
        chunk = indata.flatten().astype(np.float32)
        is_speech = vad.is_speech(chunk)

        # ***** NEW ***** 如果检测到语音且TTS正在播放，触发打断
        if is_speech and tts.is_playing:
            tts.interrupt_speech_after_delay()  # 使用配置文件中的延迟时间

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
            # 主动生成并播报开场白
            print("\n--- 反诈卫士 (Kimi) ---")
            print("正在生成动态开场白...")
            time.sleep(1.0)

            # ***** FIXED ***** 只调用一次开场白生成
            opening_text_stream = kimi_ai.generate_opening_statement()
            tts.speak_stream(opening_text_stream, speaker_wav=speaker_voice_path)
            
            print("\n(状态: 等待用户回应...)")
            while True:
                try:
                    full_audio = transcription_queue.get(timeout=1)
                    
                    print("\n队列中获取到新任务，开始转写...")
                    start_time = time.time()
                    
                    from prompts import WHISPER_PROMPT
                    simplified_chinese_prompt = WHISPER_PROMPT
                    transcribed_text = transcriber.transcribe_audio(
                        full_audio, 
                        config.LANGUAGE_CODE,
                        initial_prompt=simplified_chinese_prompt
                    )
                    
                    duration = time.time() - start_time
                    print(f"转写完成 ({duration:.2f}s): '{transcribed_text}'")
                    
                    if transcribed_text:
                        # ***** MODIFIED ***** 将文本流交给TTS模块处理并播放
                        response_stream = kimi_ai.get_response_stream(transcribed_text)
                        tts.speak_stream(response_stream, speaker_wav=speaker_voice_path)
                    
                    if transcription_queue.empty():
                         print("\n(状态: 等待用户回应...)")

                except queue.Empty:
                    time.sleep(0.1)
                    continue

    except KeyboardInterrupt:
        print("\n程序被用户中断，正在退出...")
    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        print("程序已关闭。")

if __name__ == "__main__":
    main()