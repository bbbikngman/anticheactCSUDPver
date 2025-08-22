# 智能TTS模块 - 支持Edge TTS和pyttsx3
import torch
import numpy as np
from typing import Generator
import config
import os
import time
import tempfile
import subprocess
import threading
try:
    import sounddevice as sd
except ImportError:
    sd = None

class TTSModule:
    """
    智能TTS模块
    支持Edge TTS (高质量) 和 pyttsx3 (备用)
    支持语音打断功能，所有参数可通过.env配置
    """

    def __init__(self, device: str):
        """
        初始化Fish Speech TTS模块。
        """
        try:
            print("正在初始化Fish Speech OpenAudio S1-mini TTS模块...")

            # 重新检测CUDA可用性
            cuda_available = torch.cuda.is_available()
            print(f"PyTorch版本: {torch.__version__}")
            print(f"CUDA可用性: {cuda_available}")

            if device == "cuda" and cuda_available:
                print(f"使用CUDA设备运行Fish Speech")
                device = "cuda"
            else:
                print("使用CPU运行Fish Speech")
                device = "cpu"

            self.device = device
            self.sample_rate = 44100  # Fish Speech默认采样率
            self.model = None
            self.processor = None

            # 语音播放控制
            self.is_playing = False
            self.should_stop = False
            self.play_thread = None

            # 初始化TTS引擎
            self._init_tts_engine()

            print(f"Fish Speech TTS模块初始化成功。设备: {device}")

        except Exception as e:
            print(f"Fish Speech TTS模块初始化失败: {e}")
            print("将使用备用TTS方案...")
            self.model = None
            self.processor = None
            self.is_playing = False
            self.should_stop = False

    def _init_tts_engine(self):
        """根据配置初始化TTS引擎"""
        try:
            if config.TTS_ENGINE == "edge":
                print("正在初始化Edge TTS...")
                self._init_edge_tts()
            else:
                print("正在初始化pyttsx3 TTS...")
                self._init_pyttsx3_tts()

        except Exception as e:
            print(f"TTS初始化失败: {e}")
            print("使用基础备用TTS方案...")
            self._init_pyttsx3_tts()

    def _init_edge_tts(self):
        """初始化Edge TTS"""
        try:
            import edge_tts
            self.edge_tts = edge_tts
            self.tts_type = "edge"
            print(f"Edge TTS初始化成功 - 语速:{config.TTS_RATE}, 音量:{config.TTS_VOLUME}")
        except ImportError:
            print("Edge TTS不可用，尝试安装...")
            try:
                subprocess.check_call(["pip", "install", "edge-tts", "--quiet"])
                import edge_tts
                self.edge_tts = edge_tts
                self.tts_type = "edge"
                print(f"Edge TTS安装成功 - 语速:{config.TTS_RATE}, 音量:{config.TTS_VOLUME}")
            except Exception as e:
                print(f"Edge TTS安装失败: {e}")
                self._init_pyttsx3_tts()

    def _init_pyttsx3_tts(self):
        """初始化pyttsx3 TTS"""
        try:
            import pyttsx3
            self.backup_tts = pyttsx3.init()

            # 使用配置文件中的参数
            self.backup_tts.setProperty('rate', config.PYTTSX3_RATE)
            self.backup_tts.setProperty('volume', config.PYTTSX3_VOLUME)

            # 尝试设置更权威的声音
            voices = self.backup_tts.getProperty('voices')
            if voices:
                # 优先选择男声（通常更权威）
                for voice in voices:
                    if 'male' in voice.name.lower() or 'man' in voice.name.lower():
                        self.backup_tts.setProperty('voice', voice.id)
                        print(f"使用男声: {voice.name}")
                        break
                else:
                    # 如果没有明确的男声，选择第一个可用的声音
                    self.backup_tts.setProperty('voice', voices[0].id)
                    print(f"使用默认声音: {voices[0].name}")

            self.tts_type = "pyttsx3"
            print(f"pyttsx3初始化成功 - 语速:{config.PYTTSX3_RATE}, 音量:{config.PYTTSX3_VOLUME}")
        except Exception as e:
            print(f"pyttsx3初始化失败: {e}")
            self.backup_tts = None
            self.tts_type = "none"

    def speak_stream(self, text_stream: Generator[str, None, None], speaker_wav: str = None):
        """
        接收一个文本流，使用Fish Speech进行语音合成并播放。
        支持语音打断功能。

        输入参数:
            text_stream (Generator): 从Kimi AI传来的实时文本块生成器。
            speaker_wav (str): 用于声音克隆的参考.wav文件路径（可选）。
        """
        try:
            # 如果正在播放，先停止当前播放
            self.stop_current_speech()

            # 将文本流合并成完整句子
            full_text = "".join(text for text in text_stream)
            if not full_text.strip():
                print("收到的文本为空，不进行语音合成。")
                return

            print(f"\n--- Fish Speech 语音合成 ---")
            print(f"文本: {full_text}")

            # 重置停止标志
            self.should_stop = False

            # 根据TTS类型选择合成方法
            if hasattr(self, 'tts_type'):
                if self.tts_type == "edge":
                    self._synthesize_with_edge_tts(full_text)
                elif self.tts_type == "pyttsx3":
                    self._fallback_tts_interruptible(full_text)
                else:
                    print(f"[语音内容]: {full_text}")
            else:
                # 默认使用备用TTS
                self._fallback_tts_interruptible(full_text)

        except Exception as e:
            print(f"语音合成或播放时出错: {e}")
            # 作为备用方案，输出文本
            print(f"[语音内容]: {full_text}")

    def stop_current_speech(self):
        """停止当前正在播放的语音"""
        if self.is_playing:
            print("检测到新的语音请求，停止当前播放...")
            self.should_stop = True

            # 停止sounddevice播放
            try:
                sd.stop()
            except:
                pass

            # 等待播放线程结束
            if self.play_thread and self.play_thread.is_alive():
                self.play_thread.join(timeout=1.0)

            self.is_playing = False
            print("当前语音播放已停止")

    def interrupt_speech_after_delay(self, delay: float = None):
        """在指定延迟后打断语音播放"""
        if delay is None:
            delay = config.SPEECH_INTERRUPT_DELAY

        def delayed_interrupt():
            time.sleep(delay)
            if self.is_playing:
                print(f"检测到用户说话，{delay}秒后打断语音播放")
                self.stop_current_speech()

        interrupt_thread = threading.Thread(target=delayed_interrupt)
        interrupt_thread.daemon = True
        interrupt_thread.start()

    def speak(self, text: str, speaker_wav: str = None):
        """
        直接播放文本（非流式）
        为了兼容性添加的方法
        """
        def text_generator():
            yield text

        self.speak_stream(text_generator(), speaker_wav)

    def _synthesize_with_edge_tts(self, text: str):
        """使用Edge TTS合成语音"""
        def edge_tts_thread():
            try:
                self.is_playing = True
                print("使用Edge TTS合成语音...")

                import asyncio

                async def synthesize():
                    # 根据配置选择语音
                    if config.LANGUAGE_CODE == "zh":
                        voice = config.TTS_VOICE_ZH
                    else:
                        voice = config.TTS_VOICE_EN

                    # 使用配置文件中的参数
                    communicate = self.edge_tts.Communicate(
                        text,
                        voice,
                        rate=config.TTS_RATE,
                        volume=config.TTS_VOLUME
                    )
                    audio_data = b""

                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            audio_data += chunk["data"]
                        if self.should_stop:
                            break

                    return audio_data

                # 运行异步函数
                audio_bytes = asyncio.run(synthesize())

                if audio_bytes and not self.should_stop:
                    # 播放音频
                    self._play_audio_bytes(audio_bytes, text)

            except Exception as e:
                print(f"Edge TTS合成失败: {e}")
                print(f"[语音内容]: {text}")
            finally:
                self.is_playing = False

        # 在新线程中运行Edge TTS
        self.play_thread = threading.Thread(target=edge_tts_thread)
        self.play_thread.daemon = True
        self.play_thread.start()

    def _play_audio_bytes(self, audio_bytes, fallback_text=""):
        """播放音频字节数据"""
        try:
            # 保存到临时文件并播放
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_file_path = tmp_file.name

            try:
                # 尝试使用pygame播放
                import pygame
                pygame.mixer.init()
                pygame.mixer.music.load(tmp_file_path)
                pygame.mixer.music.play()

                # 等待播放完成，但支持打断
                while pygame.mixer.music.get_busy():
                    if self.should_stop:
                        pygame.mixer.music.stop()
                        print("Edge TTS播放被打断")
                        break
                    time.sleep(config.AUDIO_CHUNK_DURATION)

                if not self.should_stop:
                    print("Edge TTS播放完成")

            except ImportError:
                print("pygame不可用，尝试安装...")
                subprocess.check_call(["pip", "install", "pygame", "--quiet"])
                # 重新尝试
                self._play_audio_bytes(audio_bytes, fallback_text)

            finally:
                # 清理临时文件
                try:
                    os.unlink(tmp_file_path)
                except:
                    pass

        except Exception as e:
            print(f"Edge TTS播放失败: {e}")
            # 回退到pyttsx3
            if hasattr(self, 'backup_tts') and self.backup_tts and fallback_text:
                print("回退到pyttsx3播放...")
                self.backup_tts.say(fallback_text)
                self.backup_tts.runAndWait()



    def _fallback_tts_interruptible(self, text: str):
        """可打断的备用TTS方案"""
        def fallback_tts_thread():
            try:
                self.is_playing = True
                if hasattr(self, 'backup_tts') and self.backup_tts:
                    print("使用备用TTS引擎...")

                    # 分句播放，以便可以被打断
                    sentences = text.split('。')
                    for sentence in sentences:
                        if self.should_stop:
                            print("备用TTS播放被打断")
                            break
                        if sentence.strip():
                            self.backup_tts.say(sentence + '。')
                            self.backup_tts.runAndWait()

                    if not self.should_stop:
                        print("备用TTS播放完成")
                else:
                    print("TTS引擎不可用，输出文本内容:")
                    print(f"[语音内容]: {text}")
            except Exception as e:
                print(f"备用TTS失败: {e}")
                print(f"[语音内容]: {text}")
            finally:
                self.is_playing = False

        # 在新线程中运行备用TTS
        self.play_thread = threading.Thread(target=fallback_tts_thread)
        self.play_thread.daemon = True
        self.play_thread.start()