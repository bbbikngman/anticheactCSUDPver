# 加载faster-whisper模型，提供一个方法将完整的音频数据转写成文字。

from faster_whisper import WhisperModel
import numpy as np
import torch

class Transcriber:
    """封装了faster-whisper的转写模块。"""

    def __init__(self, model_size: str, device: str):
        # ***** MODIFIED ***** 添加智能设备检测和回退机制
        try:
            # 检查CUDA是否可用，如果不可用则回退到CPU
            original_device = device
            if device == "cuda":
                if not torch.cuda.is_available():
                    print("警告: CUDA不可用，Whisper模型将使用CPU运行")
                    device = "cpu"
                else:
                    try:
                        # 尝试创建一个简单的CUDA张量来测试CUDA是否真正可用
                        test_tensor = torch.tensor([1.0]).cuda()
                        print(f"CUDA测试成功，Whisper模型将使用CUDA运行")
                    except Exception as cuda_error:
                        print(f"CUDA测试失败 ({cuda_error})，Whisper模型将使用CPU运行")
                        device = "cpu"

            compute_type = "float16" if device == "cuda" else "int8"

            try:
                self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
                print(f"Whisper转写模型 '{model_size}' 加载成功，设备: {device}。")
                self.device = device  # 保存实际使用的设备
            except Exception as model_error:
                # 如果CUDA加载失败，尝试CPU
                if device == "cuda":
                    print(f"CUDA加载失败 ({model_error})，尝试使用CPU...")
                    device = "cpu"
                    compute_type = "int8"
                    self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
                    print(f"Whisper转写模型 '{model_size}' 加载成功，设备: {device}。")
                    self.device = device
                else:
                    raise model_error

        except Exception as e:
            print(f"Whisper模型加载失败: {e}")
            raise

    # ******** 修改此方法 ********
    def transcribe_audio(self, audio_data: np.ndarray, language: str, initial_prompt: str = None) -> str:
        """
        将音频数据转写成文字。
        输入参数:
            audio_data (np.ndarray): float32格式的完整音频数据。
            language (str): 音频的语言代码 (例如 "zh" for Chinese)。
            initial_prompt (str, optional): 提供给模型的初始提示，用于引导风格。
        输出:
            (str): 转写后的文本。
        """
        segments, _ = self.model.transcribe(
            audio_data, 
            language=language,
            initial_prompt=initial_prompt # 将提示传递给模型
        )
        full_text = "".join(segment.text for segment in segments)
        return full_text