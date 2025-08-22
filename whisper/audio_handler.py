# 文件: audio_handler.py

import numpy as np
import time
from typing import Optional # ***** NEW *****
from . import config

class AudioHandler:
    """处理音频流，管理录音状态和触发逻辑。"""

    def __init__(self, silence_chunks_threshold: int, max_speech_seconds: float, sample_rate: int):
        self.silence_threshold = silence_chunks_threshold
        self.max_speech_samples = int(max_speech_seconds * sample_rate)
        
        self.audio_buffer = []
        self.is_recording = False
        self.silent_chunks_count = 0

    # ***** MODIFIED ***** 方法的输出类型和内部逻辑都已改变
    def process_chunk(self, chunk: np.ndarray, is_speech: bool) -> Optional[np.ndarray]:
        """
        处理新的音频块，如果达到触发条件，则返回完整的音频数据。
        输出:
            (Optional[np.ndarray]): 如果触发，返回np.ndarray；否则返回None。
        """
        triggered_audio = None

        if is_speech:
            if not self.is_recording:
                print("\n检测到语音，开始录音...")
                self.is_recording = True
            
            # 只要是语音，就加入缓冲区并重置静音计数
            self.audio_buffer.append(chunk)
            self.silent_chunks_count = 0
        else:
            if self.is_recording:
                # 即使不是语音，也先加入缓冲区，以保留完整的句末静音
                self.audio_buffer.append(chunk)
                self.silent_chunks_count += 1
                
                # 触发条件1：长静音
                if self.silent_chunks_count > self.silence_threshold:
                    print(f"检测到长静音 ({config.SILENCE_THRESHOLD_S}秒)，触发。")
                    triggered_audio = self._trigger()

        # 触发条件2：达到最大录音时长
        # 检查是否在录音，并且缓冲区内音频超过最大值
        if self.is_recording and sum(len(c) for c in self.audio_buffer) > self.max_speech_samples:
            print(f"达到最大录音时长 ({config.MAX_SPEECH_S}秒)，强制触发。")
            triggered_audio = self._trigger()
            
        return triggered_audio

    # ***** NEW ***** 新的内部触发方法，用于打包和重置
    def _trigger(self) -> np.ndarray:
        """内部方法，用于打包音频、重置状态，并返回音频数据。"""
        # 1. 从缓冲区复制数据
        audio_to_process = np.concatenate(self.audio_buffer)
        
        # 2. 重置所有状态，为下一句话做准备
        self.audio_buffer = []
        self.is_recording = False
        self.silent_chunks_count = 0
        
        # 3. 返回打包好的音频
        return audio_to_process