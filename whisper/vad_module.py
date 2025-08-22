# 加载VAD模型，并提供一个简单的方法来判断传入的音频块是否包含语音。
import torch
import numpy as np
from typing import Tuple

class VADModule:
    """语音活动检测模块，封装了Silero VAD模型。"""

    def __init__(self, sensitivity: float):
        """
        初始化VAD模块。
        输入参数:
            sensitivity (float): VAD模型的检测阈值 (0到1)。
        """
        try:
            # 从torch.hub加载预训练的silero_vad模型
            self.model, self.utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=True # 使用ONNX版本以获得更好的性能
            )
            (self.get_speech_timestamps, _, self.read_audio, _, _) = self.utils
            self.sensitivity = sensitivity
            print("VAD模型加载成功 (ONNX)。")
        except Exception as e:
            print(f"VAD模型加载失败: {e}")
            raise

    def is_speech(self, chunk: np.ndarray) -> bool:
        """
        判断一个音频块中是否包含语音。
        输入参数:
            chunk (np.ndarray): 格式为float32的音频数据块。
        输出:
            (bool): 如果检测到语音则返回True，否则返回False。
        """
        # 使用VAD模型进行预测
        speech_prob = self.model(torch.from_numpy(chunk), AUDIO_SAMPLE_RATE).item()
        return speech_prob >= self.sensitivity

# 在config.py中定义了AUDIO_SAMPLE_RATE，这里直接使用会报错
# 为了模块独立性，应该在使用时传入，或者在config中定义
from whisper.config import AUDIO_SAMPLE_RATE