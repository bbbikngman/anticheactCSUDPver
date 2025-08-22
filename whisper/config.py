# 安全地从 .env 文件加载所有参数，进行类型转换，并提供给其他模块使用。
import os
from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv()

# --- Audio Stream Configuration ---
AUDIO_SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", 16000))
AUDIO_CHUNK_SAMPLES = int(os.getenv("AUDIO_CHUNK_SAMPLES", 512))

# --- VAD & Trigger Configuration ---
VAD_SENSITIVITY = float(os.getenv("VAD_SENSITIVITY", 0.5))
SILENCE_THRESHOLD_S = float(os.getenv("SILENCE_THRESHOLD_S", 1.5))
MAX_SPEECH_S = float(os.getenv("MAX_SPEECH_S", 15.0))

# --- Whisper Transcription Configuration ---
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
DEVICE = os.getenv("DEVICE", "cuda")
MAX_WORDS_TRIGGER = int(os.getenv("MAX_WORDS_TRIGGER", 999))
LANGUAGE_CODE = os.getenv("LANGUAGE_CODE", "zh")

# --- Derived Parameters ---
# 计算出静音阈值对应的音频块数量
SILENCE_CHUNKS = int(SILENCE_THRESHOLD_S * AUDIO_SAMPLE_RATE / AUDIO_CHUNK_SAMPLES)

# 文件: config.py (在末尾追加)

# --- TTS (Text-to-Speech) Configuration ---
TTS_ENGINE = os.getenv("TTS_ENGINE", "edge")
TTS_VOICE_ZH = os.getenv("TTS_VOICE_ZH", "zh-CN-YunxiNeural")
TTS_VOICE_EN = os.getenv("TTS_VOICE_EN", "en-US-ChristopherNeural")
TTS_RATE = os.getenv("TTS_RATE", "+30%")
TTS_VOLUME = os.getenv("TTS_VOLUME", "+20%")
TTS_PITCH = os.getenv("TTS_PITCH", "+5%")

# pyttsx3备用TTS设置
PYTTSX3_RATE = int(os.getenv("PYTTSX3_RATE", 220))
PYTTSX3_VOLUME = float(os.getenv("PYTTSX3_VOLUME", 0.9))

# --- 语音打断配置 ---
SPEECH_INTERRUPT_DELAY = float(os.getenv("SPEECH_INTERRUPT_DELAY", 0.5))
AUDIO_CHUNK_DURATION = float(os.getenv("AUDIO_CHUNK_DURATION", 0.1))

# --- Kimi Large Language Model Configuration ---
MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY")
KIMI_MODEL_NAME = os.getenv("KIMI_MODEL_NAME", "kimi-k2-turbo-preview")
KIMI_TEMPERATURE = float(os.getenv("KIMI_TEMPERATURE", 0.6))
KIMI_MAX_TOKENS = int(os.getenv("KIMI_MAX_TOKENS", 256))