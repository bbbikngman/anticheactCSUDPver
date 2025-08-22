#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Edge TTS UDP 适配器
- 复用 edge-tts 合成逻辑，返回 MP3 字节（不做本地播放）
- 供 UDP 服务器调用，将 MP3 下发给客户端
"""

import asyncio
import whisper.config as config

class TTSModuleUDPAdapter:
    def __init__(self):
        pass

    async def _edge_tts_bytes_async(self, text: str) -> bytes:
        import edge_tts
        voice = config.TTS_VOICE_ZH if config.LANGUAGE_CODE == "zh" else config.TTS_VOICE_EN
        communicate = edge_tts.Communicate(text, voice, rate=config.TTS_RATE, volume=config.TTS_VOLUME)
        out = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                out += chunk["data"]
        return out

    def generate_mp3_from_stream(self, text_stream) -> bytes:
        # 将生成器拼接为完整文本（与现有 TTS 聚合一致，最小改动）
        text = "".join(part for part in text_stream)
        if not text.strip():
            return b""
        return asyncio.run(self._edge_tts_bytes_async(text))

